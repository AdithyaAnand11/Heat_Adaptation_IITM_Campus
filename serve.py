"""Local server for the Campus UTCI dashboard. Works fully offline in demo mode.

  python serve.py --export data/IITM_GEE_5Zones_Microclimate_Complete_2013_2026.csv

Demo mode holds back the last few scenes of the export. Each click on "Replay next scene" adds one of them
to the data, refits the Kalman model, issues the next forecast and scores the previous one, exactly as the
live loop would when a new Landsat scene arrives.

  python serve.py --live      fetches real scenes from Earth Engine instead (needs internet and `earthengine authenticate`)
"""
import argparse, json, os, shutil, subprocess, sys, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--export", default=os.path.join(HERE, "data", "IITM_GEE_5Zones_Microclimate_Complete_2013_2026.csv"))
ap.add_argument("--results", default=os.path.join(HERE, "results"), help="outputs of the last full notebook run")
ap.add_argument("--hold", type=int, default=3, help="demo: about this many of the latest scenes are held back and replayed (the first must be clear and follow the last kept scene closely)")
ap.add_argument("--live", action="store_true", help="fetch from Earth Engine instead of replaying")
ap.add_argument("--port", type=int, default=8765)
a = ap.parse_args()

MODE = "live" if a.live else "demo"
WORK = os.path.join(HERE, "work")
NB = os.path.join(HERE, "model", "IITM_UTCI_forecast_v5.ipynb")
P = {k: os.path.join(WORK, k) for k in ("data", "results", "queue")}
BASE, FETCHED = os.path.join(P["data"], "base.csv"), os.path.join(P["data"], "fetched_scenes.csv")
HTML = os.path.join(WORK, "dashboard.html")
LOCK = threading.Lock()
STATE = {"running": False, "last": None}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pending():
    return len(sorted(os.listdir(P["queue"]))) if os.path.isdir(P["queue"]) else 0


def run(cmd, env=None):
    r = subprocess.run(cmd, cwd=HERE, env={**os.environ, **(env or {})}, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1][:300] if (r.stderr or r.stdout).strip() else "failed")
    return r.stdout


def refit(extra_env):
    env = {"UTCI_MODE": "quick", "CI": "true", "UTCI_DATA_PATH": BASE if MODE == "demo" else a.export,
           "UTCI_FETCHED_PATH": FETCHED, "UTCI_OUT_DIR": P["results"], **extra_env}
    out = run([sys.executable, os.path.join(HERE, "run_notebook.py"), NB], env)
    run([sys.executable, os.path.join(HERE, "dashboard", "generate_dashboard.py"), "--outputs", P["results"],
         "--html", HTML, "--mode", MODE])
    return out


def prepare():
    """Fresh working copy: export minus the last --hold scenes, an empty forecast log, then one refit to issue the first forecast."""
    shutil.rmtree(WORK, ignore_errors=True)
    for d in P.values():
        os.makedirs(d)
    shutil.copytree(a.results, P["results"], dirs_exist_ok=True)
    for f in ("forecast_log.csv", "realtime_scorecard.csv", "gee_fetch_log.csv"):
        if os.path.exists(os.path.join(P["results"], f)):
            os.remove(os.path.join(P["results"], f))
    shutil.copy(os.path.join(HERE, "dashboard", "dashboard.html"), HTML)
    if MODE == "live":
        refit({"UTCI_GEE_FETCH": "1", "UTCI_GEE_DRY_RUN": "0"})
        return
    raw = pd.read_csv(a.export, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    raw["Date"] = pd.to_datetime(raw["Observation_Date"].astype(str).str.strip(), dayfirst=True).dt.normalize()
    dates = sorted(raw["Date"].unique())
    held = []
    if a.hold > 0:
        n_pts = raw.groupby("Date").size()
        j0 = len(dates) - a.hold
        ok = lambda j: (dates[j] - dates[j - 1]).days <= 10 and n_pts[dates[j]] >= 400
        order = list(range(j0, j0 - 4, -1)) + list(range(j0 + 1, len(dates) - 1)) + list(range(j0 - 4, j0 - 9, -1))
        j = next((k for k in order if ok(k)), j0)   # first replayed scene: clear, and one slot after the last kept scene
        held = dates[j:]
    raw[~raw["Date"].isin(held)].drop(columns=["Date"]).to_csv(BASE, index=False)
    for d in held:
        sc = raw[raw["Date"] == d].drop(columns=["Observation_Date", "Campus_Zone"], errors="ignore").copy()
        sc["Zone"] = sc["Point_ID"].str[:2]
        sc["Scene"], sc["Source"] = "REPLAY_" + pd.Timestamp(d).strftime("%Y%m%d"), "replay"
        sc.to_csv(os.path.join(P["queue"], f"scene_{pd.Timestamp(d).date()}.csv"), index=False)
    refit({"UTCI_GEE_FETCH": "0"})


def job(kind):
    t0 = time.time()
    try:
        if kind == "reset":
            prepare()
            msg = f"Demo reset · {pending()} scenes queued"
        elif MODE == "demo":
            nxt = sorted(os.listdir(P["queue"]))[0]
            sc = pd.read_csv(os.path.join(P["queue"], nxt), parse_dates=["Date"])
            if os.path.exists(FETCHED):
                sc = pd.concat([pd.read_csv(FETCHED, parse_dates=["Date"]), sc], ignore_index=True)
            sc.to_csv(FETCHED, index=False)
            os.remove(os.path.join(P["queue"], nxt))
            refit({"UTCI_GEE_FETCH": "0"})
            msg = f"Added scene {nxt[6:-4]} · forecast updated in {time.time() - t0:.0f}s"
        else:
            before = len(open(FETCHED).readlines()) if os.path.exists(FETCHED) else 0
            refit({"UTCI_GEE_FETCH": "1", "UTCI_GEE_DRY_RUN": "0"})
            after = len(open(FETCHED).readlines()) if os.path.exists(FETCHED) else 0
            msg = "New scene added, forecast updated" if after > before else "No new scene yet, forecast refreshed"
        STATE["last"] = {"ok": True, "message": msg, "finished_utc": now()}
    except Exception as e:
        STATE["last"] = {"ok": False, "message": str(e), "finished_utc": now()}
    finally:
        STATE["running"] = False


def start(kind):
    with LOCK:
        if STATE["running"]:
            return False
        STATE["running"] = True
    threading.Thread(target=job, args=(kind,), daemon=True).start()
    return True


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        body = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send(200, open(HTML, "rb").read(), "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self.send(200, json.dumps({"mode": MODE, "pending": pending(), **STATE}))
        else:
            self.send(404, "{}")

    def do_POST(self):
        if self.path in ("/api/rerun", "/api/reset"):
            kind = "reset" if self.path.endswith("reset") else "rerun"
            if kind == "reset" and MODE != "demo":
                return self.send(400, "{}")
            if kind == "rerun" and MODE == "demo" and pending() == 0:
                return self.send(409, '{"error":"queue empty"}')
            self.send(202 if start(kind) else 409, "{}")
        else:
            self.send(404, "{}")


if __name__ == "__main__":
    if not os.path.exists(a.export) and MODE == "demo":
        sys.exit(f"Export not found: {a.export}\nPut the raw GEE export in data/ or pass --export PATH.")
    print(f"Preparing ({MODE} mode)... this takes about 30 seconds.")
    prepare()
    STATE["last"] = {"ok": True, "message": f"Ready · {pending()} scenes queued" if MODE == "demo" else "Ready", "finished_utc": now()}
    print(f"\nDashboard: http://localhost:{a.port}\nPress Ctrl+C to stop.")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
