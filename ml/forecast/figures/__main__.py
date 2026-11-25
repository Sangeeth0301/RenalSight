"""Regenerate every result figure and table: python -m forecast.figures  (run `python -m forecast.datasets` first for the real-data and image figures)."""
from . import calibration, comparison, diagnostics, kidney, readme, tables, trajectories, whatif

if __name__ == "__main__":
    for m in (trajectories, calibration, comparison, whatif, diagnostics, kidney, tables, readme):
        out = m.main()
        print(m.__name__.split(".")[-1], len(out) if hasattr(out, "__len__") else out)
