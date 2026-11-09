"""Write the latest model state into dashboard.html.

Usage: python generate_dashboard.py --outputs ../results [--repo owner/name]

Reads zone_utci_grid.csv, climatology_coefficients.csv, kalman_params.csv, run_summary.json,
metrics_overall.csv and realtime_scorecard.csv. The page computes any 7-day window itself.
Put iitm_logo.svg / .png / .jpg next to this script to embed the logo.
"""
import argparse, base64, glob, json, os, re
from datetime import datetime, timezone
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--outputs", default=os.path.join(HERE, "..", "results"))
ap.add_argument("--html", default=os.path.join(HERE, "dashboard.html"))
ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/name, enables the Re-run button")
ap.add_argument("--workflow", default="refresh.yml")
ap.add_argument("--mode", choices=["static", "demo", "live"], default="static",
                help="static: GitHub/disabled button; demo: local server replaying held-back scenes; live: local server fetching from Earth Engine")
ap.add_argument("--step", type=int, default=8)
ap.add_argument("--z", type=float, default=1.6449)
a = ap.parse_args()

NAMES = {"AC": "Academic Zone", "HZ": "Hostel Zone", "LW": "Lake + Watsa Ground",
         "NV": "Near Velachery Gate", "SQ": "Staff Quarters"}
path = lambda f: os.path.join(a.outputs, f)
read = lambda f, **k: pd.read_csv(path(f), **k) if os.path.exists(path(f)) else None

grid = read("zone_utci_grid.csv", index_col=0, parse_dates=True)
coef = read("climatology_coefficients.csv", index_col=0)
kp = read("kalman_params.csv", index_col=0)
T0 = grid.index[0]

def baseline(d, z):
    t = (d - T0).days / 365.25
    w = 2 * np.pi * d.dayofyear / 365.25
    c = coef.loc[z]
    return float(c["intercept"] + c["trend"] * t + c["sin1"] * np.sin(w) + c["cos1"] * np.cos(w)
                 + c["sin2"] * np.sin(2 * w) + c["cos2"] * np.cos(2 * w))

zones = {}
for z in grid.columns:
    s = grid[z].dropna()
    d0 = s.index[-1]
    zones[z] = {"name": NAMES.get(z, z), "coef": {k: float(v) for k, v in coef.loc[z].items()},
                "phi": float(kp.loc[z, "ar.L1"]), "sigma2": float(kp.loc[z, "sigma2"]),
                "anom": float(s.iloc[-1] - baseline(d0, z)), "last_obs": str(d0.date())}

summary = json.load(open(path("run_summary.json"))) if os.path.exists(path("run_summary.json")) else {}
metrics = read("metrics_overall.csv", index_col=0)
score = read("realtime_scorecard.csv")
kal = metrics.loc["kalman"] if metrics is not None and "kalman" in metrics.index else None
live = {"n": 0}
if score is not None and len(score):
    sk = score[(score["model"] == "kalman") & score["error"].notna()]
    if len(sk):
        live = {"n": int(len(sk)), "targets": int(sk["target_date"].nunique()),
                "rmse": round(float(np.sqrt((sk["error"] ** 2).mean())), 2),
                "inside": round(float(sk["inside_interval"].mean()), 2) if "inside_interval" in sk else None}

logo = ""
search = {os.path.dirname(os.path.abspath(a.html)), HERE}
for p in sorted(f for d in search for f in glob.glob(os.path.join(d, "iitm_logo.*")) if f.rsplit(".", 1)[-1].lower() in ("svg", "png", "jpg", "jpeg", "webp")):
    ext = p.rsplit(".", 1)[1].lower()
    mime = {"svg": "image/svg+xml", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
    logo = f"data:{mime};base64," + base64.b64encode(open(p, "rb").read()).decode()
    break

data = {
    "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "model": "Kalman AR(1) on climatology + trend", "pi": 90, "z": a.z, "step": a.step, "t0": str(T0.date()),
    "last_obs": max(v["last_obs"] for v in zones.values()), "next_scene": summary.get("next_forecast_date"),
    "runtime": a.mode, "repo": a.repo, "workflow": a.workflow, "logo": logo, "zones": zones,
    "accuracy": None if kal is None else {"rmse": round(float(kal["RMSE"]), 2), "mae": round(float(kal["MAE"]), 2),
                                          "coverage": (summary.get("kalman_interval") or {}).get("empirical_coverage"),
                                          "n": (summary.get("test_window") or {}).get("n_predictions"),
                                          "window": summary.get("test_window")},
    "live": live, "last_full_run": summary.get("last_full_run_utc") or summary.get("run_utc"),
}
html = open(a.html, encoding="utf-8").read()
block = "/*DATA_START*/\nconst DATA = " + json.dumps(data) + ";\n/*DATA_END*/"
html = re.sub(r"/\*DATA_START\*/.*?/\*DATA_END\*/", lambda m: block, html, flags=re.S)
open(a.html, "w", encoding="utf-8").write(html)
print(f"updated {a.html} | last usable scene {data['last_obs']} | repo {a.repo or '(none: Re-run disabled)'}")
