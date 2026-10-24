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


def cohort_levers(n=300, seed=21) -> dict:
    """Lever effect on the time to eGFR < 30 across simulated patients who start between eGFR 30 and 60 (2 years of quarterly history)."""
    import pandas as pd

    import progression as pg
    df = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv").dropna(subset=["age", "male", "diabetes", "sbp", "hba1c", "acr", "egfr", "hgb"])
    df = df[(df.egfr >= 30) & (df.egfr <= 60) & (df.age >= 30)].sample(n, random_state=seed).reset_index(drop=True)
    rng = np.random.default_rng(seed)
    gains = {k: [] for k in list(tj.LEVERS) + ["all"]}
    changed = {k: 0 for k in gains}
    used = 0
    for _, r in df.iterrows():
        sim = pg.simulate_patient(rng, r.age, int(r.male), int(r.diabetes), r.sbp, r.hba1c, r.acr, r.egfr, years=2.0, visit_gap_months=3)
        p = dict(age=float(r.age), male=int(r.male), diabetes=bool(r.diabetes), sbp=float(r.sbp), hba1c=float(r.hba1c), acr=float(r.acr), egfr0=float(sim["egfr"][-1]), hgb=float(r.hgb),
                 history_t=[float(x) for x in sim["t"]], history_egfr=[float(x) for x in sim["egfr"]])
        if p["egfr0"] <= 30:
            continue
        base = milestone(tj.build_journey(dict(p), levers=[], today=TODAY)["current"], "g4")["median"]
        if base is None:
            continue
        used += 1
        for lev in gains:
            lv = list(tj.LEVERS) if lev == "all" else [lev]
            m = milestone(tj.build_journey(dict(p), levers=lv, today=TODAY)["with_levers"], "g4")["median"]
            m = 15.0 if m is None else m                  # beyond the 15-year horizon counts as 15
            g = m - base
            gains[lev].append(g)
            changed[lev] += int(g > 0.01)
    out = {"n": used}
    for lev, g in gains.items():
        g = np.array(g)
        out[lev] = {"share_changed": round(changed[lev] / used, 3), "median_gain": round(float(np.median(g)), 2), "q25": round(float(np.percentile(g, 25)), 2), "q75": round(float(np.percentile(g, 75)), 2)}
    return out


if __name__ == "__main__":
    R = {"levers": lever_table(), "mc": mc_sensitivity(), "cohort_levers": cohort_levers()}
    (OUT / "results_extra.json").write_text(json.dumps(R, indent=1))
    print(json.dumps(R, indent=1))
