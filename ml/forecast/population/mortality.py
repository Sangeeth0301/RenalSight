"""Death hazard calibrated on real data: NHANES 2005-2014 adults linked to the National Death Index (up to 15 years of follow-up).

log hazard = b0 + b_age (age - 50) + b_male + b_dm + b_acr (log ACR - log 15) + stage effect of current eGFR
Weighted Poisson regression (person-years as weight on the rate). Fitted on a random half of people; validated on the other half
against weighted Kaplan-Meier survival by baseline eGFR stage.

    python -m forecast.population.mortality
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from sklearn.linear_model import PoissonRegressor

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "ml" / "forecast" / "results" / "population"
EDGES = [(90.0, "egfr>=90"), (60.0, "egfr 60-90"), (45.0, "egfr 45-60"), (30.0, "egfr 30-45"), (15.0, "egfr 15-30"), (0.0, "egfr<15")]      # reference = 90+
LOG_ACR0 = np.log(15.0)


def stage_index(egfr: np.ndarray) -> np.ndarray:
    e = np.asarray(egfr, float)
    return np.select([e >= 90, e >= 60, e >= 45, e >= 30, e >= 15], [0, 1, 2, 3, 4], default=5)


def design(age, male, dm, acr, egfr) -> np.ndarray:
    age, male, dm = np.asarray(age, float), np.asarray(male, float), np.asarray(dm, float)
    la = np.log(np.clip(np.asarray(acr, float), 3.0, 5000.0)) - LOG_ACR0
    st = stage_index(egfr)
    return np.column_stack([age - 50.0, male, dm, la] + [(st == k).astype(float) for k in range(1, 6)])


class Hazard:
    """Callable hazard (per year); coefficients from fit()."""

    def __init__(self, intercept: float, coef: np.ndarray):
        self.b0, self.coef = float(intercept), np.asarray(coef, float)

    def __call__(self, age, male, dm, acr, egfr) -> np.ndarray:
        return np.exp(self.b0 + design(age, male, dm, acr, egfr) @ self.coef)

    def to_dict(self):
        names = ["age (per year)", "male", "diabetes", "log ACR (per unit)"] + [f"stage {n}" for _, n in EDGES[1:]]
        return {"intercept": self.b0, "coef": dict(zip(names, self.coef.tolist()))}


def load() -> pd.DataFrame:
    d = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv")
    d = d.dropna(subset=["months", "event", "age", "male", "diabetes", "acr", "egfr", "weight_2yr"])
    d = d[(d.eligstat == 1) & (d.months > 0)].copy()
    d["years"] = d.months / 12.0
    return d


def fit(d: pd.DataFrame) -> Hazard:
    X = design(d.age.values, d.male.values, d.diabetes.values, d.acr.values, d.egfr.values)
    rate = d.event.values / d.years.values
    w = d.years.values * d.weight_2yr.values / d.weight_2yr.mean()
    m = PoissonRegressor(alpha=1e-6, max_iter=2000).fit(X, rate, sample_weight=w)
    return Hazard(m.intercept_, m.coef_)


def km_by_stage(d: pd.DataFrame, horizons=(5.0, 10.0)) -> dict:
    out = {}
    for k, (_, name) in enumerate(EDGES):
        g = d[stage_index(d.egfr.values) == k]
        if len(g) < 30:
            continue
        km = KaplanMeierFitter().fit(g.years, g.event, weights=g.weight_2yr)
        out[name] = {"n": int(len(g)), **{f"obs_{int(h)}y": float(1 - km.predict(h)) for h in horizons}}
    return out


def predicted_death(d: pd.DataFrame, haz: Hazard, horizon: float, rng: np.random.Generator) -> pd.Series:
    """Expected cumulative mortality at `horizon` if the baseline covariates and eGFR stage stayed fixed (a simple screen; the full engine is checked in engine.py)."""
    lam = haz(d.age.values + 0.0, d.male.values, d.diabetes.values, d.acr.values, d.egfr.values)
    return pd.Series(1 - np.exp(-lam * horizon), index=d.index)


def main():
    RES.mkdir(parents=True, exist_ok=True)
    d = load()
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(d)); a, b = d.iloc[idx[: len(d) // 2]], d.iloc[idx[len(d) // 2:]]
    h_a = fit(a)
    full = fit(d)
    obs = km_by_stage(b)
    rows = {}
    for k, (_, name) in enumerate(EDGES):
        g = b[stage_index(b.egfr.values) == k]
        if len(g) < 30:
            continue
        pr = {int(h): float(np.average(1 - np.exp(-h_a(g.age.values, g.male.values, g.diabetes.values, g.acr.values, g.egfr.values) * h), weights=g.weight_2yr)) for h in (5, 10)}
        rows[name] = {**obs[name], "pred_5y": pr[5], "pred_10y": pr[10]}
    total = {"n_train": int(len(a)), "n_test": int(len(b)), "events_test": int(b.event.sum())}
    # discrimination of the fitted hazard on the held-out half (C-index)
    from lifelines.utils import concordance_index
    lam_b = h_a(b.age.values, b.male.values, b.diabetes.values, b.acr.values, b.egfr.values)
    total["c_index_test"] = float(concordance_index(b.years, -lam_b, b.event))
    json.dump({"hazard": full.to_dict(), "half_fit_validation": rows, "summary": total}, open(RES / "mortality_model.json", "w"), indent=1)
    print(json.dumps(total))
    for k, v in rows.items():
        print(f"{k:12s} n={v['n']:5d}  obs 5y {v['obs_5y']:.3f} pred {v['pred_5y']:.3f} | obs 10y {v['obs_10y']:.3f} pred {v['pred_10y']:.3f}")


def load_hazard() -> Hazard:
    j = json.load(open(RES / "mortality_model.json"))["hazard"]
    return Hazard(j["intercept"], np.array(list(j["coef"].values())))


if __name__ == "__main__":
    main()
