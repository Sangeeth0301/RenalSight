"""Programme scenarios and the projection driver with uncertainty (random draws shared across scenarios within a replicate)."""
from __future__ import annotations

import pickle
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import numpy as np

from forecast.analysis import params_for

from .engine import Levers, Population, Result, draw_noise, load_population, population_params, run
from .mortality import load_hazard

CACHE = Path(__file__).resolve().parents[1] / "results" / "cache"


@dataclass
class Programme:
    name: str
    short: str
    description: str
    build: Callable[[Population, np.ndarray, np.ndarray], Levers]     # (population, uniform1, uniform2) -> who gets which lever


def _lv(pop, **kw):
    z = np.zeros(len(pop), bool)
    return Levers(kw.get("bp", z), kw.get("sugar", z), kw.get("ras", z), kw.get("sglt2", z))


def status_quo(pop, u1, u2):
    return Levers.none(len(pop))


def make_ras_bp(cov):
    return lambda pop, u1, u2: _lv(pop, ras=(pop.acr >= 30) & (u1 < cov), bp=(pop.sbp >= 140) & (u2 < cov))


def make_sglt2(cov):
    return lambda pop, u1, u2: _lv(pop, sglt2=(pop.egfr >= 20) & (pop.egfr < 60) & ((pop.dm > 0) | (pop.acr >= 200)) & (u1 < cov))


def make_screen(cov):
    def f(pop, u1, u2):
        det = pop.ckd & (u1 < cov)
        return _lv(pop, bp=det, sugar=det, ras=det, sglt2=det)
    return f


def make_ambitious(cov_a, cov_b):
    def f(pop, u1, u2):
        return make_ras_bp(cov_a)(pop, u1, u2).union(make_sglt2(cov_b)(pop, u1, u2))
    return f


PROGRAMMES = [
    Programme("Status quo", "S0", "No additional programme: today's care", status_quo),
    Programme("BP control + RAS blockade (60%)", "S1", "ACE inhibitor / ARB for albuminuria (ACR >= 30) and BP target for SBP >= 140, 60% of eligible people", make_ras_bp(0.60)),
    Programme("SGLT2 inhibitors (50%)", "S2", "SGLT2 inhibitor for eGFR 20-60 with diabetes or ACR >= 200, 50% of eligible people", make_sglt2(0.50)),
    Programme("Screening + early care (56%)", "S3", "Detect CKD (eGFR < 60 or ACR >= 30) in 70%, 80% adherence: all four levers where they apply", make_screen(0.56)),
    Programme("Ambitious combined (80% + 70%)", "S4", "RAS + BP at 80% and SGLT2 at 70% of eligible people", make_ambitious(0.80, 0.70)),
]


def project(pop: Population, replicates: int = 10, n: int = 6000, years: int = 20, seed: int = 0, programmes=None, name: str = "base", shift: float | None = None) -> dict:
    programmes = programmes or PROGRAMMES
    cache = CACHE / f"projection_is_s{shift if shift is not None else 'cal'}_{name}_{pop.label.replace(' ', '_')}_{pop.year}_{replicates}_{n}_{years}_{seed}.pkl"
    if cache.exists():
        return pickle.load(open(cache, "rb"))
    haz = load_hazard()
    from .calibrate import load_calibration
    cal = load_calibration()
    P0 = population_params(params_for(2.0), cal["kappa_g"], cal["nu"], cal["excess"])
    if shift is None:
        shift = cal["shift"]
    rng = np.random.default_rng(seed)
    out = {p.short: [] for p in programmes}
    draws = []
    for r in range(replicates):
        P = replace(P0, prior_scale=P0.prior_scale * float(np.exp(rng.normal(0, 0.10))))
        acr_red, sg_red = 0.35 * rng.uniform(0.75, 1.25), 0.30 * rng.uniform(0.75, 1.25)
        hs = float(np.exp(rng.normal(0, 0.15)))
        boost = np.where(pop.ckd | (pop.dm > 0), 6.0, 1.0)
        noise = draw_noise(len(pop), n, years * 4, pop.w, rng, boost)
        u1, u2 = rng.random(len(pop)), rng.random(len(pop))
        draws.append(dict(prior_scale=P.prior_scale, acr_red=acr_red, sglt2_red=sg_red, hazard_scale=hs))
        for prog in programmes:
            lv = prog.build(pop, u1, u2)
            lv.acr_red, lv.sglt2_red = acr_red, sg_red
            out[prog.short].append(run(pop, noise.idx, noise, lv, P, haz, years, hs, track_transitions=(prog.short == "S0"), shift=shift))
    out["_draws"] = draws
    CACHE.mkdir(parents=True, exist_ok=True)
    pickle.dump(out, open(cache, "wb"))
    return out


def summarise(res: dict, key: str, fn) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mean and 10th/90th percentile over replicates of fn(Result)."""
    v = np.array([fn(r) for r in res[key]])
    return v.mean(axis=0), np.quantile(v, 0.1, axis=0), np.quantile(v, 0.9, axis=0)
