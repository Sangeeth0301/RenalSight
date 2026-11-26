"""Vectorised microsimulation of a population with the SALT-FG dynamics (same state equations as forecast.forecast.simulate).

Each person carries level L (eGFR), slope b, regime S, a kidney-failure flag and an alive flag. Covariates set the slope means and the
regime chain (re-evaluated every year as people age); programme levers shift the slope exactly as in the patient-level engine. Death uses the
hazard calibrated on NHANES linked mortality. Scenarios share random numbers within a replicate, so differences between them are paired.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

import progression as pg
from forecast.model import DT, Params

from .mortality import Hazard

BASE = -0.8
STATES = ["eGFR >= 60", "G3a", "G3b", "G4", "Kidney failure", "Dead"]
ACR_REDUCTION, SGLT2_REDUCTION = 0.35, 0.30
AGE_BINS = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 200]
AGE_LABELS = ["20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80+"]


# ----------------------------------------------------------------------------- population
@dataclass
class Population:
    age: np.ndarray
    male: np.ndarray
    dm: np.ndarray
    sbp: np.ndarray
    hba1c: np.ndarray
    acr: np.ndarray
    egfr: np.ndarray
    w: np.ndarray                      # NHANES sampling weight rescaled to persons in the target population
    total: float                       # persons represented
    year: int = 2024
    label: str = ""

    def __len__(self):
        return len(self.age)

    @property
    def ckd(self) -> np.ndarray:
        return (self.egfr < 60) | (self.acr >= 30)


def load_population(year: int = 2024, anchor_prevalence: float | None = None, root=None, country: str = "IND") -> Population:
    from pathlib import Path
    root = Path(root) if root else Path(__file__).resolve().parents[3]
    d = pd.read_csv(root / "data" / "processed" / "nhanes_adults.csv").dropna(subset=["age", "male", "diabetes", "sbp", "hba1c", "acr", "egfr", "weight_2yr"]).reset_index(drop=True)
    d["ag"] = pd.cut(d.age, AGE_BINS, labels=AGE_LABELS, right=False)
    d["sex"] = np.where(d.male == 1, "male", "female")
    if country == "US":                                   # NHANES weights as they are, scaled to about 250 million US adults
        w = d.weight_2yr.values / d.weight_2yr.sum() * 250e6
        return Population(d.age.values.astype(float), d.male.values.astype(float), d.diabetes.values.astype(float), d.sbp.values.astype(float), d.hba1c.values.astype(float), d.acr.values.astype(float), d.egfr.values.astype(float), w, float(w.sum()), 2020, "US NHANES")
    pop = pd.read_csv(root / "data" / "processed" / "population" / "ind_pop_age_sex.csv")
    pop = pop[pop.year == year].set_index(["age_group", "sex"])["pop"]
    w = np.zeros(len(d))
    for (ag, sx), g in d.groupby(["ag", "sex"], observed=True):
        tot = pop.get((ag, sx), 0.0)
        w[g.index] = tot * g.weight_2yr.values / g.weight_2yr.sum()
    ckd = ((d.egfr < 60) | (d.acr >= 30)).values
    if anchor_prevalence is not None:
        cur = w[ckd].sum() / w.sum()
        k = (anchor_prevalence / (1 - anchor_prevalence)) * (w[~ckd].sum() / w[ckd].sum())
        w2 = w.copy(); w2[ckd] *= k; w = w2 * (w.sum() / w2.sum())
    return Population(d.age.values.astype(float), d.male.values.astype(float), d.diabetes.values.astype(float), d.sbp.values.astype(float), d.hba1c.values.astype(float),
                      d.acr.values.astype(float), d.egfr.values.astype(float), w, float(w.sum()), year, "anchored" if anchor_prevalence else "NHANES covariates")


# ----------------------------------------------------------------------------- vectorised covariate factors (same formulas as progression/model)
def prior_slope_v(age, dm, sbp, hba1c, acr) -> np.ndarray:
    acr = np.maximum(acr, 10.0)
    s = -0.8 - 0.9 * np.log10(acr / 10.0) - 0.7 * dm - 0.25 * np.maximum(hba1c - 7.0, 0.0) * dm - 0.03 * np.maximum(sbp - 120.0, 0.0) - 0.01 * np.maximum(age - 60.0, 0.0)
    return BASE + pg.EXCESS_SCALE * (s - BASE)


@dataclass
class Levers:
    """Which levers each person receives (boolean arrays) and their effect scales (replicate-level draws)."""
    bp: np.ndarray
    sugar: np.ndarray
    ras: np.ndarray
    sglt2: np.ndarray
    acr_red: float = ACR_REDUCTION
    sglt2_red: float = SGLT2_REDUCTION

    @staticmethod
    def none(n):
        z = np.zeros(n, bool)
        return Levers(z, z.copy(), z.copy(), z.copy())

    def union(self, o: "Levers") -> "Levers":
        return Levers(self.bp | o.bp, self.sugar | o.sugar, self.ras | o.ras, self.sglt2 | o.sglt2, self.acr_red, self.sglt2_red)


def treated_covariates(pop: Population, age, lv: Levers):
    sbp = np.where(lv.bp, np.minimum(pop.sbp, 125.0), pop.sbp)
    hba = np.where(lv.sugar & (pop.dm > 0), np.minimum(pop.hba1c, 7.0), pop.hba1c)
    acr = np.where(lv.ras & (pop.acr >= 30), np.maximum(pop.acr * (1 - lv.acr_red), 10.0), pop.acr)
    mult = np.where(lv.sglt2 & (pop.egfr >= 20), 1.0 - lv.sglt2_red, 1.0)
    return sbp, hba, acr, mult


def slope_means(pop: Population, age, lv: Levers, P: Params):
    """(N, K) regime slope means and the (N,) risk score, with levers applied (SPEC 2.2)."""
    sbp, hba, acr, mult = treated_covariates(pop, age, lv)
    mu = prior_slope_v(age, pop.dm, sbp, hba, acr)
    excess = np.minimum(mu - BASE, 0.0)
    m = BASE + P.prior_scale * (mult * excess)[:, None] + P.g[None, :]
    return m, np.maximum(-(mu - BASE), 0.0), acr


def transition_v(risk: np.ndarray, P: Params) -> np.ndarray:
    ub = P.up_bias
    W = np.array([[0.0, 0.7, 0.3], [1.0 - ub, 0.0, ub], [0.3, 0.7, 0.0]])
    Pm = (1.0 - P.stay) * W
    np.fill_diagonal(Pm, P.stay)
    T = Pm[None, :, :] * np.exp(P.gamma[None, None, :] * risk[:, None, None])
    return T / T.sum(axis=2, keepdims=True)


# ----------------------------------------------------------------------------- simulation
@dataclass
class Noise:
    idx: np.ndarray
    u_reg0: np.ndarray
    b0: np.ndarray
    ur: np.ndarray
    ew: np.ndarray
    ud: np.ndarray
    q: np.ndarray                  # (n_pop,) sampling probability of each person (importance sampling)


def draw_noise(n_pop: int, n: int, steps: int, w: np.ndarray, rng: np.random.Generator, boost: np.ndarray | None = None) -> Noise:
    """Sample n people. With `boost` (per-person factor), high-risk people are oversampled and every result is re-weighted by w / (q n),
    which keeps totals unbiased while giving many more kidney-failure events per run."""
    p = w * (boost if boost is not None else 1.0)
    p = p / p.sum()
    return Noise(rng.choice(n_pop, size=n, p=p), rng.random(n), rng.standard_normal(n), rng.random((n, steps)), rng.standard_normal((n, steps, 2)), rng.random((n, steps)), p)


@dataclass
class Result:
    counts: np.ndarray             # (years + 1, 6) persons in each state at each year end
    incident_kf: np.ndarray        # (years,) new kidney-failure cases per year
    deaths: np.ndarray             # (years,) all-cause deaths per year
    deaths_kf: np.ndarray          # (years,) deaths among people in kidney failure
    kf_person_years: np.ndarray    # (years,) person-years lived in kidney failure
    candidates: np.ndarray         # (years + 1,) people in kidney failure aged 18-70 (potential transplant candidates)
    kf_by_age: np.ndarray          # (13,) cumulative kidney-failure cases by age band over the horizon
    kf_by_sex: np.ndarray          # (2,) cumulative cases (female, male)
    treated: float                 # persons receiving at least one lever
    state_matrices: np.ndarray | None = None      # (years, 6, 6) transition counts between yearly states
    L_end: np.ndarray | None = None               # (n,) final eGFR of each simulated person
    alive_end: np.ndarray | None = None
    age0: np.ndarray | None = None
    weights: np.ndarray | None = None             # persons represented by each simulated individual


def population_params(P: Params, kappa_g: float = 1.0, nu: float = 1.0, excess: float = 1.0) -> Params:
    """Population-level adjustment of the patient-level parameters (see calibrate.py): regime offsets scaled by kappa_g, process noise by nu,
    covariate-driven excess decline by `excess`."""
    return replace(P, g=P.g * kappa_g, q_L=P.q_L * nu, q_b=P.q_b * nu, prior_scale=P.prior_scale * excess)


def run(pop: Population, idx: np.ndarray, noise: Noise, lv: Levers, P: Params, haz: Hazard, years: int = 20, hazard_scale: float = 1.0, track_transitions: bool = False, shift: float = 0.0) -> Result:
    n = len(idx)
    pw = pop.w[idx] / (noise.q[idx] * n)            # persons represented by each simulated individual
    age0, male, dm = pop.age[idx], pop.male[idx], pop.dm[idx]
    sub = Population(age0, male, dm, pop.sbp[idx], pop.hba1c[idx], pop.acr[idx], pop.egfr[idx], pop.w[idx], pop.total)
    lvs = Levers(lv.bp[idx], lv.sugar[idx], lv.ras[idx], lv.sglt2[idx], lv.acr_red, lv.sglt2_red)
    L = sub.egfr.copy(); kf = L < 15.0; alive = np.ones(n, bool)
    steps_per_year = int(round(1 / DT)); rho = P.rho
    m0, risk0, _ = slope_means(sub, age0, Levers.none(n), P)
    m0 = m0 + shift
    T0 = transition_v(risk0, P)
    init = P.pi_init[None, :] * np.exp(P.gamma[None, :] * risk0[:, None]); init /= init.sum(axis=1, keepdims=True)
    S = np.minimum((noise.u_reg0[:, None] > np.cumsum(init, axis=1)).sum(axis=1), P.K - 1)
    b = m0[np.arange(n), S] + noise.b0 * pg.SLOPE_SD
    counts = np.zeros((years + 1, 6)); inc = np.zeros(years); dth = np.zeros(years); dthk = np.zeros(years); kfpy = np.zeros(years)
    cand = np.zeros(years + 1); kf_age = np.zeros(13); kf_sex = np.zeros(2)
    ag_idx = np.clip(np.digitize(age0, AGE_BINS) - 1, 0, 12)
    mats = np.zeros((years, 6, 6)) if track_transitions else None

    def state(Lc, kfc, al):
        st = np.select([Lc >= 60, Lc >= 45, Lc >= 30, Lc >= 15], [0, 1, 2, 3], default=3)
        st = np.where(kfc, 4, st)
        return np.where(al, st, 5)

    def record(y):
        st = state(L, kf, alive)
        counts[y] = np.bincount(st, weights=pw, minlength=6)
        cand[y] = pw[(kf & alive) & (age0 + y >= 18) & (age0 + y <= 70)].sum()
        return st
    st_prev = record(0)
    mb = mt = Tb = Tt = None
    for t in range(years * steps_per_year):
        y = t // steps_per_year
        if t % steps_per_year == 0:                       # refresh covariate factors yearly as people age
            age = age0 + y
            mb, rb, _ = slope_means(sub, age, Levers.none(n), P)
            mt, rt, acr_t = slope_means(sub, age, lvs, P)
            mb = mb + shift; mt = mt + shift
            delta = mt - mb
            Tt = transition_v(rt, P); cum = np.cumsum(Tt, axis=2)
            acr_eff = acr_t
        cdf = cum[np.arange(n), S]
        S = np.minimum((noise.ur[:, t][:, None] > cdf).sum(axis=1), P.K - 1)
        L = L + DT * (b + delta[np.arange(n), S]) + np.sqrt(P.q_L * DT) * noise.ew[:, t, 0]
        b = rho * b + (1.0 - rho) * mb[np.arange(n), S] + np.sqrt(P.q_b[S] * DT) * noise.ew[:, t, 1]
        L = np.maximum(L, 1.0)
        newkf = (L < 15.0) & ~kf & alive
        inc[y] += pw[newkf].sum(); kf |= newkf
        if kf_age is not None:
            np.add.at(kf_age, ag_idx[newkf], pw[newkf]); kf_sex[0] += pw[newkf & (male == 0)].sum(); kf_sex[1] += pw[newkf & (male == 1)].sum()
        lam = haz(age0 + y + (t % steps_per_year) * DT, male, dm, acr_eff, L) * hazard_scale
        dies = alive & (noise.ud[:, t] < 1.0 - np.exp(-lam * DT))
        kfpy[y] += pw[alive & kf].sum() * DT
        dth[y] += pw[dies].sum(); dthk[y] += pw[dies & kf].sum()
        alive = alive & ~dies
        if (t + 1) % steps_per_year == 0:
            st = record(y + 1)
            if mats is not None:
                np.add.at(mats[y], (st_prev, st), pw)
            st_prev = st
    treated = float(pw[lvs.bp | lvs.sugar | lvs.ras | lvs.sglt2].sum())
    return Result(counts, inc, dth, dthk, kfpy, cand, kf_age, kf_sex, treated, mats, L, alive, age0, pw)
