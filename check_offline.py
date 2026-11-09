"""Run once while you still have internet: checks that everything needed for the offline demo is in place."""
import importlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ok = True
def line(good, text):
    global ok
    ok &= good
    print(("  OK   " if good else "  MISSING  ") + text)

print("Python packages")
for mod, pip in [("pandas", "pandas"), ("numpy", "numpy"), ("scipy", "scipy"), ("matplotlib", "matplotlib"),
                 ("statsmodels", "statsmodels"), ("pythermalcomfort", "pythermalcomfort>=3")]:
    try:
        importlib.import_module(mod); line(True, mod)
    except Exception:
        line(False, f"{mod}   ->  pip install {pip}")
try:
    from pythermalcomfort.models import utci
    utci(tdb=30, tr=30, v=1.0, rh=60); line(True, "pythermalcomfort computes UTCI")
except Exception as e:
    line(False, f"pythermalcomfort UTCI call failed: {e}")

print("Files")
export = os.path.join(HERE, "data", "IITM_GEE_5Zones_Microclimate_Complete_2013_2026.csv")
line(os.path.exists(export), "data/IITM_GEE_5Zones_Microclimate_Complete_2013_2026.csv  (the raw export; copy it here)")
for f in ("model/IITM_UTCI_forecast_v5.ipynb", "dashboard/dashboard.html", "dashboard/generate_dashboard.py",
          "results/metrics_overall.csv", "results/run_summary.json", "results/climatology_coefficients.csv"):
    line(os.path.exists(os.path.join(HERE, f)), f)
print("  OK   " if any(f.startswith("iitm_logo") for f in os.listdir(os.path.join(HERE, "dashboard"))) else "  note ", "dashboard/iitm_logo.svg or .png (add the IIT Madras logo here; a round IITM badge shows without it)")
print("\nReady. Start with:  python serve.py" if ok else "\nFix the MISSING items, then run this again.")
sys.exit(0 if ok else 1)
