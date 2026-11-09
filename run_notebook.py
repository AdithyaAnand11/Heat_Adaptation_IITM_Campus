"""Run the notebook's code cells in this Python process, no Jupyter needed.
Usage: python run_notebook.py model/IITM_UTCI_forecast_v5.ipynb   (configuration comes from UTCI_* environment variables)"""
import json, os, sys, traceback

os.environ.setdefault("MPLBACKEND", "Agg")
nb = json.load(open(sys.argv[1], encoding="utf-8"))
ns = {"__name__": "__main__", "display": lambda *a, **k: print(*a)}
for i, cell in enumerate(c for c in nb["cells"] if c["cell_type"] == "code"):
    try:
        exec(compile("".join(cell["source"]), f"<cell {i}>", "exec"), ns)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
