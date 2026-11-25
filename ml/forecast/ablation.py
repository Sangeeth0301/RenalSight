"""Ablation: switch each model component off (or perturb an assumption) and measure the cost, on a fresh simulated test set.

    python -m forecast.ablation [out.json]
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace

import numpy as np

import forecast  # noqa: F401
from forecast import benchmark as bm
from forecast.model import Params
from forecast.realdata import load_params
from forecast.simulator import World


def variants(p: Params) -> dict[str, Params]:
    mean_qb = float(np.mean(p.q_b))
    return {
        "Full model (fitted K=3)": p,
        "No outlier model": replace(p, pi_out=0.0),
        "Regimes disabled": replace(p, g=np.zeros(3), q_b=np.full(3, mean_qb), gamma=np.zeros(3)),
        "No covariate prior": replace(p, prior_scale=0.0),
        "Covariate prior x0.5": replace(p, prior_scale=p.prior_scale * 0.5),
        "Covariate prior x1.5": replace(p, prior_scale=p.prior_scale * 1.5),
        "Visit noise x2 (misspecified)": replace(p, R=p.R * 2.0),
        "Visit noise x0.5 (misspecified)": replace(p, R=p.R * 0.5),
        "Death hazard x2": replace(p, lam0=p.lam0 * 2.0),
        "Death hazard x0.5": replace(p, lam0=p.lam0 * 0.5),
        "Process noise x2": replace(p, q_L=p.q_L * 2.0, q_b=p.q_b * 2.0),
        "Process noise x0.5": replace(p, q_L=p.q_L * 0.5, q_b=p.q_b * 0.5),
    }


def main(path: str = "forecast/results/ablation.json", n: int = 500, seed0: int = 4):
    warnings.filterwarnings("ignore")
    bm.SEED0 = seed0
    df = bm.load_cohort()
    test = bm.generate(World(), df, 2.0, n, 3)
    y, alive, kf5 = bm.truth(test)
    salt_m, salt_r = bm.run_method(bm.Salt(300, True), test, 20)
    salt_cp = bm.crps_all(salt_m, y)
    rows = []
    for name, p in variants(load_params()).items():
        Y, r = bm.run_method(bm.FG(p, name, 300), test, 20)
        s, _ = bm.summarise(name, Y, r, y, alive, kf5, ref_crps=salt_cp)
        rows.append(s)
        print(f"{name:<34} crps {s['crps']:.3f}  cov {s['coverage']:.3f}  brier {s['brier5']:.4f}  auc {s['auc5']:.3f}", flush=True)
    s, _ = bm.summarise("SALT (reference)", salt_m, salt_r, y, alive, kf5)
    rows.append(s)
    json.dump({"n": n, "rows": rows}, open(path, "w"), indent=1, default=float)
    return rows


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "forecast/results/ablation.json")
