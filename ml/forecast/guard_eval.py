"""Labelled evaluation of the guard layer (TRUST criterion 'honest abstention').

Normal patients come from the simulated world; four kinds of bad input are generated with known labels:
unit errors (creatinine in the wrong unit), stale history, patients far outside the training covariates, and missing covariates.
Reported: abstention rate per class, false-abstention rate on normal patients, and 80%-band coverage among issued versus all forecasts.

    python -m forecast.guard_eval [out.json]
"""
from __future__ import annotations

import json
import sys
import warnings

import numpy as np

import forecast  # noqa: F401
from forecast import benchmark as bm
from forecast.guard import OODDetector, check_filter, check_input
from forecast.filtering import run_filter
from forecast.simulator import World


def corrupt(pt: dict, kind: str, rng: np.random.Generator) -> dict:
    q = dict(pt)
    q["x"] = dict(pt["x"])
    q["visits_y"] = np.array(pt["visits_y"], float)
    q["visits_t"] = np.array(pt["visits_t"], float)
    if kind == "unit error":
        q["visits_y"] = q["visits_y"] * (10.0 if rng.random() < 0.5 else 0.1)          # eGFR values off by a factor of ten (unit mix-up)
    elif kind == "stale history":
        q["T0"] = float(q["visits_t"][-1] + rng.uniform(2.0, 4.0))
    elif kind == "far outside population":
        q["x"].update(age=float(rng.uniform(95, 105)), sbp=float(rng.uniform(205, 240)), hba1c=float(rng.uniform(12, 16)), acr=float(rng.uniform(8000, 15000)))
    elif kind == "missing covariate":
        q["x"][rng.choice(["age", "sbp", "hba1c", "acr"])] = float("nan")
    return q


def decide(pt: dict, ood: OODDetector) -> tuple[bool, list[str]]:
    d = check_input(pt["x"], pt["visits_t"], pt["visits_y"], ood=ood, t_origin=pt["T0"])
    return d.forecast, d.reasons


def main(path: str = "forecast/results/guard_eval.json", n: int = 300):
    warnings.filterwarnings("ignore")
    df = bm.load_cohort()
    train = bm.generate(World(), df, 2.0, 600, 91)
    ood = OODDetector().fit([p["x"] for p in train])
    test = bm.generate(World(), df, 2.0, n, 92)
    rng = np.random.default_rng(3)
    out = {"n_per_class": n, "ood_threshold": ood.threshold, "classes": {}}
    issued = [decide(p, ood)[0] for p in test]
    out["classes"]["normal"] = {"abstain_rate": float(1 - np.mean(issued))}
    for kind in ("unit error", "stale history", "far outside population", "missing covariate"):
        res = [decide(corrupt(p, kind, rng), ood) for p in test]
        out["classes"][kind] = {"abstain_rate": float(np.mean([not r[0] for r in res])), "top_reason": max(set(" | ".join(r[1]) for r in res if not r[0]) or {""}, key=lambda s: sum(" | ".join(x[1]) == s for x in res))}
    # coverage among issued vs all forecasts, for a mixed stream (normal + corrupted); the guard should remove the bad ones
    fg = bm.FG(__import__("forecast.realdata", fromlist=["x"]).load_params(), "FG K=3", 300)
    mixed = [(p, "normal") for p in test[:150]] + [(corrupt(p, k, rng), k) for p, k in zip(test[150:], rng.choice(["unit error", "stale history", "far outside population"], size=len(test) - 150))]
    cov_all, cov_issued, n_issued = [], [], 0
    for pt, kind in mixed:
        try:
            Y, _ = fg.run(dict(pt), np.random.default_rng(1))
        except Exception:
            Y = None
        ok, _ = decide(pt, ood)
        y_true = np.array([pt["eval_y"][h] for h in bm.EVAL_H]) if "eval_y" in pt else None
        if Y is None or y_true is None or pt["d_c"] <= bm.EVAL_H[0]:
            continue
        lo, hi = np.quantile(Y, 0.1, axis=0), np.quantile(Y, 0.9, axis=0)
        cov = float(np.mean((y_true >= lo) & (y_true <= hi)))
        cov_all.append(cov)
        if ok:
            cov_issued.append(cov); n_issued += 1
    out["stream"] = {"n": len(cov_all), "issued": n_issued, "abstained": len(cov_all) - n_issued, "coverage_all_raw": float(np.mean(cov_all)), "coverage_issued_raw": float(np.mean(cov_issued))}
    json.dump(out, open(path, "w"), indent=1, default=float)
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "forecast/results/guard_eval.json")
