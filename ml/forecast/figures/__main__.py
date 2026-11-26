"""Regenerate every result figure and table: python -m forecast.figures  (run `python -m forecast.datasets` and `python -m forecast.realdata_plus` first for the real-data and image figures)."""
from . import calibration, comparison, diagnostics, hmm, kidney, kidney_cards, readme, real_baselines, real_forecasts, tables, trajectories, whatif

if __name__ == "__main__":
    for m in (trajectories, calibration, comparison, whatif, diagnostics, kidney, real_baselines, real_forecasts, kidney_cards, hmm, tables, readme):
        out = m.main()
        print(m.__name__.split(".")[-1], len(out) if hasattr(out, "__len__") else out)
