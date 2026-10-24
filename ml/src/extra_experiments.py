"""Extra numbers for the RenalSight paper: lever effects on two example patients and Monte-Carlo size sensitivity.

    python ml/src/extra_experiments.py [output_dir]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np

import trajectory as tj

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "paper"
TODAY = dt.date(2026, 10, 22)

PATIENTS = {
    "A": dict(age=62, male=0, diabetes=True, sbp=154, hba1c=8.3, acr=340, egfr0=24.7, hgb=11.3, history_t=[0, 0.5, 1, 1.5, 2], history_egfr=[47.1, 39.6, 33.9, 29.7, 24.7]),
    "B": dict(age=55, male=1, diabetes=True, sbp=146, hba1c=7.9, acr=180, egfr0=51.8, hgb=13.2, history_t=[0, 0.5, 1, 1.5, 2], history_egfr=[58.0, 56.2, 54.9, 53.0, 51.8]),
}
TARGET = {"A": "g5", "B": "g4"}                       # milestone each patient is approaching: eGFR < 15 for A, eGFR < 30 for B


def milestone(block: dict, key: str) -> dict:
    m = next(x for x in block["milestones"] if x["key"] == key)
    return {"median": m["median"], "fast": m["fast"], "slow": m["slow"]}


def lever_table() -> dict:
    out = {}
    for name, p in PATIENTS.items():
        key = TARGET[name]
        base = tj.build_journey(dict(p), levers=[], today=TODAY)
        rows = {"none": milestone(base["current"], key)}
        for lev in list(tj.LEVERS) + ["all"]:
            lv = list(tj.LEVERS) if lev == "all" else [lev]
            j = tj.build_journey(dict(p), levers=lv, today=TODAY)
            rows[lev] = milestone(j["with_levers"], key)
        out[name] = {"milestone": key, "rows": rows}
    return out


def mc_sensitivity() -> list:
    p = PATIENTS["A"]
    res = []
    keep = tj.N_PATHS
    for n in (250, 500, 1000, 2500, 5000):
        tj.N_PATHS = n
        meds, ts = [], []
        for seed in range(10):
            s = time.perf_counter()
            j = tj.build_journey(dict(p), levers=[], today=TODAY, seed=100 + seed)
            ts.append(time.perf_counter() - s)
            meds.append(next(x for x in j["current"]["milestones"] if x["key"] == "g5")["p_by"]["2"])
        res.append({"paths": n, "p2_mean": round(float(np.mean(meds)), 4), "p2_sd": round(float(np.std(meds)), 4), "seconds": round(float(np.mean(ts)), 2)})
    tj.N_PATHS = keep
    return res


if __name__ == "__main__":
    R = {"levers": lever_table(), "mc": mc_sensitivity()}
    (OUT / "results_extra.json").write_text(json.dumps(R, indent=1))
    print(json.dumps(R, indent=1))
