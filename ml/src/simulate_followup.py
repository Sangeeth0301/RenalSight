"""Generate SIMULATED longitudinal eGFR follow-up and validate the forecasting machinery on it.

Baselines (age, sex, diabetes, BP, HbA1c, ACR, eGFR) are real NHANES adults with eGFR < 90, so covariate
distributions are realistic. Trajectories are simulated from the published-range slope model in progression.py.
The data are labelled SIMULATED everywhere. Validation therefore checks the estimation / uncertainty machinery
(do the ranges cover the truth?), not clinical truth.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import progression as pg

ROOT = Path(__file__).resolve().parents[2]


def main(n_patients=3000, seed=11):
    rng = np.random.default_rng(seed)
    base = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv")
    base = base[(base.egfr < 90) & (base.egfr >= 15)].dropna(subset=["acr", "sbp"]).copy()
    base["hba1c"] = base["hba1c"].fillna(5.6)
    base = base.sample(n_patients, replace=True, random_state=seed).reset_index(drop=True)

    rows, truth = [], []
    for pid, r in base.iterrows():
        sim = pg.simulate_patient(rng, r.age, r.male, r.diabetes, r.sbp, r.hba1c, r.acr, r.egfr, years=5.0)
        truth.append(dict(patient_id=pid, sim_true_slope=sim["true_slope"], sim_prior_slope=sim["prior_slope"]))
        for t, e in zip(sim["t"], sim["egfr"]):
            rows.append(dict(patient_id=pid, month=int(round(t * 12)), egfr=round(float(e), 1)))
    visits = pd.DataFrame(rows)
    cov = base[["age", "male", "diabetes", "sbp", "hba1c", "acr", "egfr"]].rename(columns={"egfr": "baseline_egfr"}).reset_index(names="patient_id")
    out = visits.merge(cov, on="patient_id").merge(pd.DataFrame(truth), on="patient_id")
    out["SIMULATED"] = True
    path = ROOT / "data" / "processed" / "synthetic_followup.csv"
    out.to_csv(path, index=False)
    print("wrote", path, "rows", len(out), "patients", n_patients)

    # ---------------- validation: use first 12 months, predict years 3 and 5
    cover3 = cover5 = 0
    err3, err5, kf_hits = [], [], []
    test_ids = rng.choice(n_patients, 400, replace=False)
    for pid in test_ids:
        v = out[out.patient_id == pid]
        c = v.iloc[0]
        hist = v[v.month <= 12]
        cur = float(np.mean(hist.egfr.values[-2:]))
        fc = pg.forecast_patient(c.age, c.male, c.diabetes, c.sbp, c.hba1c, c.acr, cur, history_t=hist.month.values / 12.0, history_egfr=hist.egfr.values, horizon=5)
        yrs = np.array(fc.years)
        for yr, store, errs in ((3, "c3", err3), (5, "c5", err5)):
            i = int(np.argmin(abs(yrs - yr)))
            actual_row = v[v.month == yr * 12]
            if actual_row.empty:
                continue
            actual = float(actual_row.egfr.iloc[0])
            inside = fc.egfr_p10[i] <= actual <= fc.egfr_p90[i]
            errs.append(abs(fc.egfr_p50[i] - actual))
            if yr == 3:
                cover3 += inside
            else:
                cover5 += inside
    n = len(err3)
    print("Held-out check (400 simulated patients, 12 months of history):")
    print("  year 3: median abs error %.1f mL/min, 10-90%% band covers %.0f%% of observed values (ideal about 80%%)" % (np.median(err3), 100 * cover3 / n))
    print("  year 5: median abs error %.1f mL/min, 10-90%% band covers %.0f%% of observed values (ideal about 80%%)" % (np.median(err5), 100 * cover5 / n))


if __name__ == "__main__":
    main()
