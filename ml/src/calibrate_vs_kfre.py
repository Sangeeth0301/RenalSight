"""Calibrate the progression prior so that its 5-year kidney-failure risk matches KFRE on real NHANES CKD patients.

KFRE is a validated clinical equation; matching its average risk keeps our simulated forecast in a realistic range.
Result printed here is copied into progression.EXCESS_SCALE.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import progression as pg
from clinical import kfre_4var

ROOT = Path(__file__).resolve().parents[2]


def main():
    df = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv")
    d = df[(df.egfr >= 15) & (df.egfr < 60) & (df.age >= 30)].dropna(subset=["acr", "egfr"]).sample(500, random_state=1)
    kf = np.array([kfre_4var(r.age, r.male, r.egfr, r.acr, 5) for r in d.itertuples()])
    print("patients", len(d), "| mean KFRE 5y risk %.3f" % kf.mean(), "| mean eGFR %.1f" % d.egfr.mean())
    best = None
    for scale in (1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2):
        pg.EXCESS_SCALE = scale
        ours = []
        for r in d.itertuples():
            mu = pg.prior_slope(r.age, r.diabetes, r.sbp, r.hba1c, r.acr)
            ours.append(pg.forecast(r.egfr, mu, pg.SLOPE_SD, horizon=5, n=600).prob_kf_5y)
        ours = np.array(ours)
        corr = np.corrcoef(ours, kf)[0, 1]
        print("scale %.2f -> mean 5y risk %.3f | correlation with KFRE %.2f" % (scale, ours.mean(), corr))
        gap = abs(ours.mean() - kf.mean())
        if best is None or gap < best[0]:
            best = (gap, scale)
    print("best EXCESS_SCALE =", best[1])


if __name__ == "__main__":
    main()
