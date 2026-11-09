# Campus UTCI Outlook: offline demo (Antigravity)

Runs the dashboard and the **Replay next scene** button on one laptop with no internet.

Demo mode holds back the last few Landsat scenes of the export. Each click adds the next one, refits the Kalman model, issues a new forecast and scores the previous forecast against the scene that just arrived. It is the real update loop, replayed on history, and the page is labelled **Demo replay**. It takes about 8 seconds per click.

## Before the presentation (internet needed once)

1. **Open this folder in Antigravity** (File → Open Folder) and open its terminal.
2. **Install the packages** (about 2 minutes, one time):
   ```
   pip install -r requirements-offline.txt
   ```
3. **Add the raw export:** copy `IITM_GEE_5Zones_Microclimate_Complete_2013_2026.csv` into `data/`. Use the newest export (the one running to October 2026).
4. **Logo:** copy the IIT Madras logo into `dashboard/` and name it exactly `iitm_logo.png` (or `.svg`, `.jpg`). It appears at the top left of the dashboard after you start `serve.py`. Without it, a round "IITM" badge is shown.
5. **Check everything:**
   ```
   python check_offline.py
   ```
   Every line should say OK.
6. **Start it and rehearse:**
   ```
   python serve.py
   ```
   Wait about 30 seconds for "Dashboard: http://localhost:8765", then open that address in Antigravity's browser or in Chrome. Click **Replay next scene** until the queue is empty, then **Reset demo**.

## While presenting

- Run `python serve.py` in the Antigravity terminal **before** you start, and leave it running. Open `http://localhost:8765`.
- **Replay next scene** adds one scene. Watch these change: *Data through*, *Next scene*, the forecast cards and chart, and **Live check**, which fills in once a forecast made earlier is scored against the scene that arrived.
- **Reset demo** starts over (about 30 seconds). Use it for a second run-through.
- To stop: Ctrl+C in the terminal.

## What to say about it

- Live check compares each forecast with the scene that arrived afterwards. The first forecast after a reset is scored on the first click.
- Replay accuracy (RMSE, 89% inside the band) comes from the last full run and does not change per click.
- Scenes are replayed from the export, so this demonstrates the update loop, not new satellite data. The real-time path (Earth Engine fetch plus the scheduled GitHub refresh) is the one in the other handover.

## Dashboard limits

The dashboard shows one 7-day window, starting today (in the demo: the day after the latest replayed scene). The calendar only lets you pick a day inside that week, and the arrows step day by day. Beyond about two weeks from the last scene, values are just the seasonal average.

## Options

| Command | What it does |
|---|---|
| `python serve.py --hold 5` | Hold back about 5 scenes instead of 3 |
| `python serve.py --port 9000` | Use another port |
| `python serve.py --export PATH` | Use an export stored elsewhere |
| `python serve.py --live` | Real mode: fetches new scenes from Earth Engine. Needs internet, `pip install earthengine-api`, `earthengine authenticate` and `GEE_PROJECT` set. Not tested here. |

## If something goes wrong

- **Page does not load:** is `python serve.py` still running? Check the terminal for the "Dashboard:" line.
- **"Failed: …" under the button:** run `python check_offline.py`; a package or file is missing.
- **Port in use:** use `--port 9000` and open that address.
- **Backup:** `dashboard/dashboard.html` opens by itself as a static copy, with the Re-run button off. Keep a screenshot too.
- The page works offline, but the Inter font falls back to your system font without internet.

## Files

| File | Purpose |
|---|---|
| `serve.py` | Local server: dashboard, Replay and Reset buttons |
| `run_notebook.py` | Runs the notebook's code in plain Python, no Jupyter needed |
| `check_offline.py` | Checks packages and files |
| `model/IITM_UTCI_forecast_v5.ipynb` | The model (quick mode is used by the server) |
| `dashboard/` | Dashboard page and its generator |
| `results/` | Outputs of the last full run (accuracy numbers, climatology, forecasts) |
| `work/` | Created by `serve.py`; safe to delete |
