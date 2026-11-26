"""Calibrate the population engine to real data with three targets and three parameters.

The patient-level SALT-FG parameters were fitted in a CKD-enriched simulated world where decline is fast. Applied to a whole adult population over
20 years they overstate decline (diagnosed in results/population: 70% of 40-59-year-olds below eGFR 60 twenty years later, against 9-25% in
NHANES at ages 60-79). Three population-level parameters are therefore calibrated:

    shift    common slope shift (mL/min/yr)
    kappa_g  scale of the regime offsets (between-person heterogeneity of decline)
    nu       scale of the process noise
    excess   scale of the covariate-driven excess decline (albuminuria, diabetes, blood pressure): lets the high-risk tail decline faster
             while the general population slows down

Targets (all real):
    1. US kidney-failure incidence, USRDS 2019-2021: 363 to 386 new cases per million population a year (about 124,000 a year)
    2. pseudo-cohort: today's 40-49-year-olds simulated 20 years forward should match NHANES 60-69-year-olds in prevalence of eGFR < 60
    3. pseudo-cohort: today's 50-59-year-olds -> NHANES 70-79-year-olds, prevalence of eGFR < 60, and both cohorts' mean eGFR

Out-of-sample check: India incidence (population studies: about 151 to 232 per million a year).

    python -m forecast.population.calibrate
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from forecast.analysis import params_for

from .engine import Levers, Population, draw_noise, load_population, population_params, run
from .mortality import load_hazard

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "ml" / "forecast" / "results" / "population" / "calibration.json"
US_CASES = (363e-6 * 331e6, 386e-6 * 331e6)


def nhanes_targets() -> dict:
    d = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv").dropna(subset=["egfr", "weight_2yr", "age"])
    out = {}
    for lo, hi in ((60, 70), (70, 80)):
        g = d[(d.age >= lo) & (d.age < hi)]
        out[f"{lo}-{hi - 1}"] = {"prev_lt60": float(np.average(g.egfr < 60, weights=g.weight_2yr)), "mean_egfr": float(np.average(g.egfr.clip(upper=130), weights=g.weight_2yr))}
    return out


def _sub(pop: Population, mask) -> Population:
    return Population(*(getattr(pop, k)[mask] for k in ("age", "male", "dm", "sbp", "hba1c", "acr", "egfr", "w")), total=float(pop.w[mask].sum()))


def evaluate(pop_us, shift, kappa, nu, excess=1.0, n_coh=5000, n_inc=15000, seed=0) -> dict:
    P = population_params(params_for(2.0), kappa, nu, excess)
    haz = load_hazard()
    out = {}
    for lo, key in ((40, "60-69"), (50, "70-79")):
        sub = _sub(pop_us, (pop_us.age >= lo) & (pop_us.age < lo + 10))
        rng = np.random.default_rng(seed + lo)
        nz = draw_noise(len(sub), n_coh, 80, sub.w, rng)
        r = run(sub, nz.idx, nz, Levers.none(len(sub)), P, haz, 20, 1.0, shift=shift)
        L, al = r.L_end, r.alive_end
        out[key] = {"prev_lt60": float(np.mean(L[al] < 60)), "mean_egfr": float(np.mean(np.minimum(L[al], 130)))}
    out["us_cases_per_year"] = incidence(pop_us, P, haz, shift, n_inc, seed + 7)
    return out


def incidence(pop: Population, P, haz, shift, n=15000, seed=0, years=3) -> float:
    """Annual new kidney-failure cases, simulated in the eGFR < 60 subgroup (where nearly all short-term cases arise) to cut sampling noise."""
    sub = _sub(pop, pop.egfr < 60)
    rng = np.random.default_rng(seed)
    nz = draw_noise(len(sub), n, years * 4, sub.w, rng)
    return float(run(sub, nz.idx, nz, Levers.none(len(sub)), P, haz, years, 1.0, shift=shift).incident_kf.mean())


def loss(ev: dict, tg: dict) -> float:
    inc_mid = 0.5 * sum(US_CASES)
    l = ((np.log(max(ev["us_cases_per_year"], 1.0)) - np.log(inc_mid)) / 0.10) ** 2
    for k in ("60-69", "70-79"):
        l += ((ev[k]["prev_lt60"] - tg[k]["prev_lt60"]) / 0.03) ** 2
        l += ((ev[k]["mean_egfr"] - tg[k]["mean_egfr"]) / 3.0) ** 2
    return float(l)


def calibrate():
    tg = nhanes_targets()
    us = load_population(country="US")
    rows = []
    for s, k, v, e in itertools.product((0.25, 0.5, 0.75, 1.0), (0.25, 0.5, 0.75), (0.25, 0.5), (1.0, 1.5, 2.0, 3.0)):
        ev = evaluate(us, s, k, v, e)
        rows.append((loss(ev, tg), s, k, v, e, ev))
    rows.sort(key=lambda r: r[0])
    _, s0, k0, v0, e0, _ = rows[0]
    for s, k, v, e in itertools.product(np.linspace(s0 - 0.15, s0 + 0.15, 4), np.clip(np.linspace(k0 - 0.15, k0 + 0.15, 3), 0, None), (v0 * 0.75, v0, v0 * 1.25), np.linspace(e0 * 0.8, e0 * 1.2, 3)):
        ev = evaluate(us, float(s), float(k), float(v), float(e))
        rows.append((loss(ev, tg), float(s), float(k), float(v), float(e), ev))
    rows.sort(key=lambda r: r[0])
    l, s, k, v, e, _ = rows[0]
    check = evaluate(us, s, k, v, e, seed=100)                               # fresh random numbers for the reported fit
    ind = load_population(2024)
    P = population_params(params_for(2.0), k, v, e); haz = load_hazard()
    ind_cases = incidence(ind, P, haz, s, 20000, 300)
    out = {"shift": s, "kappa_g": k, "nu": v, "excess": e, "loss": l, "targets": {"nhanes": tg, "us_cases_per_year": list(US_CASES)},
           "achieved_fresh_seed": check, "us_pmp_total_population": check["us_cases_per_year"] / 331e6 * 1e6,
           "india_out_of_sample": {"cases_per_year": ind_cases, "pmp_total_population": ind_cases / 1.44e9 * 1e6, "published_range_pmp": [151, 232]},
           "top5": [{"loss": r[0], "shift": r[1], "kappa_g": r[2], "nu": r[3], "excess": r[4]} for r in rows[:5]], "n_evaluated": len(rows)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    return out


def load_calibration() -> dict:
    return json.load(open(OUT))


def load_shift() -> float:
    return load_calibration()["shift"]


if __name__ == "__main__":
    print(json.dumps(calibrate(), indent=1))
