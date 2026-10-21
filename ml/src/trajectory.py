"""Kidney Journey: a full trajectory model built on the eGFR progression engine.

For one patient it simulates thousands of possible futures and turns them into:
  * eGFR bands by year (10th / 50th / 90th percentile)
  * milestone timing: when eGFR is likely to fall below 60, 45, 30, 20 (transplant evaluation window), 15 (kidney failure), 10 (dialysis usually needed),
    as a probability by year, a median, a fast and a slow case, and the matching calendar year and age
  * "where people like you end up": for each year, the share still doing well, in kidney failure, or who died
    (death is modelled with the NHANES Cox model using each simulated path's own age and eGFR, so it is a GROUP outcome)
  * a life-style 'levers' what-if (blood pressure, blood sugar, ACE/ARB, SGLT2 inhibitor) that changes the decline rate

It never predicts an individual date of death: it reports shares of simulated people ("out of 100 like you").
Everything is simulation-based from published decline-rate ranges and a survival model fitted on US NHANES, and must be labelled as an estimate.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

from progression import GOOD_CARE_REDUCTION, SLOPE_SD, VISIT_NOISE_SD, posterior_slope, prior_slope

STEP = 0.25                      # years between simulated points
MAX_SURV_YEARS = 10.0            # the survival model is fitted on <= ~14 years of follow-up; stay well inside it
N_PATHS = 2500
COX_MIN_EGFR = 10.0

# eGFR milestones, highest first. "dialysis" is the usual range where kidney replacement starts (often eGFR 5-10 or symptoms).
MILESTONES = [
    ("g3a", "Stage 3a", 60.0),
    ("g3b", "Stage 3b", 45.0),
    ("g4", "Stage 4", 30.0),
    ("tx_window", "Transplant evaluation window", 20.0),
    ("g5", "Kidney failure (stage 5)", 15.0),
    ("dialysis", "Dialysis likely needed", 10.0),
]

# Levers: what each change does to the inputs of the decline model. Effects are typical trial / guideline ranges, shown as estimates.
LEVERS = {
    "bp_control": {"label": "Blood pressure under 130", "how": "Sets systolic BP to 125 if it is higher", "needs": "sbp>130"},
    "sugar_control": {"label": "Blood sugar control (HbA1c under 7)", "how": "Sets HbA1c to 7.0 if it is higher", "needs": "diabetes and hba1c>7"},
    "protein_drug": {"label": "ACE inhibitor / ARB for urine protein", "how": "Lowers urine ACR by about 35% (typical range 30-40%)", "needs": "acr>=30"},
    "sglt2": {"label": "SGLT2 inhibitor (if your doctor agrees)", "how": "Slows the excess decline by about 30% (trials: roughly 30-40%)", "needs": "egfr>=20"},
}
SGLT2_REDUCTION = 0.30
ACR_REDUCTION = 0.35
BASE_AGEING = -0.8


def apply_levers(p: dict, levers: list[str]) -> tuple[dict, float]:
    """Return modified covariates and an extra multiplier on the *excess* decline."""
    q = dict(p)
    mult = 1.0
    if "bp_control" in levers and q.get("sbp") is not None:
        q["sbp"] = min(q["sbp"], 125.0)
    if "sugar_control" in levers and q.get("diabetes") and q.get("hba1c") is not None:
        q["hba1c"] = min(q["hba1c"], 7.0)
    if "protein_drug" in levers and q.get("acr") is not None and q["acr"] >= 30:
        q["acr"] = max(q["acr"] * (1 - ACR_REDUCTION), 10.0)
    if "sglt2" in levers and q["egfr0"] >= 20:
        mult *= 1 - SGLT2_REDUCTION
    return q, mult


def _slope_dist(p: dict, levers: list[str]):
    q, mult = apply_levers(p, levers)
    mu0 = prior_slope(q["age"], q["diabetes"], q["sbp"], q["hba1c"], q["acr"])
    ht, he = p.get("history_t"), p.get("history_egfr")
    if ht is not None and len(ht) >= 3:
        mu, sd = posterior_slope(mu0, ht, he)
        # own history reflects today's care; a lever shifts it by the same relative change the covariates would give
        shift = mu0 - prior_slope(p["age"], p["diabetes"], p["sbp"], p["hba1c"], p["acr"])
        mu = mu + shift
    else:
        mu, sd = mu0, SLOPE_SD
    excess = min(mu - BASE_AGEING, 0.0)
    mu = mu - excess * (1 - mult)                         # remove (1-mult) of the excess decline
    return mu, sd


def _brownian(rng, n, times, sigma=1.2):
    dt_ = np.diff(times, prepend=0.0)
    return np.cumsum(rng.normal(0, 1, size=(n, len(times))) * sigma * np.sqrt(dt_), axis=1)


def _q(a, p):
    return None if a.size == 0 else float(np.quantile(a, p))


def _timing(first: np.ndarray, horizon: float, today: dt.date, age: float) -> dict:
    """first = first-crossing time (years) for each path (inf = never within horizon)."""
    reached_by = lambda y: float((first <= y).mean())
    out = {"already": bool((first <= 0).mean() > 0.9), "p_by": {str(y): round(reached_by(y), 3) for y in (1, 2, 3, 5, 10, 15) if y <= horizon}}
    def pick(p):
        v = _q(first, p) if (first <= horizon).mean() > p else None
        return None if v is None or not np.isfinite(v) else round(v, 1)
    out["fast"], out["median"], out["slow"] = pick(0.10), pick(0.50), pick(0.90)
    for k in ("fast", "median", "slow"):
        v = out[k]
        out[k + "_year"] = None if v is None else today.year + int(math.floor(v + (today.timetuple().tm_yday / 365.25)))
        out[k + "_age"] = None if v is None else int(round(age + v))
    out["chance_within_horizon"] = round(float((first <= horizon).mean()), 3)
    return out


def _simulate(p: dict, levers: list[str], horizon: float, seed: int, today: dt.date, cox: dict | None):
    rng = np.random.default_rng(seed)
    n = N_PATHS
    mu, sd = _slope_dist(p, levers)
    slopes = rng.normal(mu, sd, size=n)
    t = np.arange(0, horizon + 1e-9, STEP)
    paths = p["egfr0"] + np.outer(slopes, t) + _brownian(rng, n, t)
    meas = np.maximum(paths + rng.normal(0, VISIT_NOISE_SD, size=paths.shape), 2.0)            # what a future lab would show
    true_ = np.maximum(paths, 2.0)

    # ---- milestone timing (first time the underlying eGFR is below each threshold)
    miles = []
    for key, label, thr in MILESTONES:
        below = true_ < thr
        first = np.where(below.any(axis=1), t[below.argmax(axis=1)], np.inf)
        if p["egfr0"] < thr:
            first = np.zeros(n)
        miles.append({"key": key, "label": label, "egfr": thr, **_timing(first, horizon, today, p["age"])})
    kf_first = np.where((true_ < 15).any(axis=1), t[(true_ < 15).argmax(axis=1)], np.inf)
    if p["egfr0"] < 15:
        kf_first = np.zeros(n)

    # ---- bands
    bands = {"years": [round(float(x), 2) for x in t], "p10": np.percentile(meas, 10, axis=0).round(1).tolist(),
             "p50": np.percentile(meas, 50, axis=0).round(1).tolist(), "p90": np.percentile(meas, 90, axis=0).round(1).tolist()}

    # ---- group outcomes with the Cox model (death as a competing event)
    outcomes = survival = None
    if cox is not None:
        ts = int(round(min(horizon, MAX_SURV_YEARS) / STEP))
        tt = t[: ts + 1]
        model, feats = cox["model"], cox["features"]
        age_t = p["age"] + tt
        rows = pd.DataFrame({
            "age": float(p["age"]),                                   # the Cox baseline hazard already carries ageing over follow-up: keep age at its starting value
             "male": p["male"], "egfr": np.clip(true_[:, : ts + 1], COX_MIN_EGFR, 130).ravel(),           # the survival data are thin below eGFR 10: do not extrapolate
            
            "log_acr": math.log(max(p["acr_for_cox"], 0.5)), "diabetes": float(p["diabetes"]), "sbp": p["sbp_for_cox"], "hba1c": p["hba1c_for_cox"], "hgb": p["hgb_for_cox"],
        })[feats]
        lp = model.predict_partial_hazard(rows).values.reshape(n, ts + 1)
        h0 = model.baseline_cumulative_hazard_
        H0 = np.interp(tt * 12.0, h0.index.values.astype(float), h0.iloc[:, 0].values.astype(float))
        dH0 = np.diff(H0, prepend=H0[0])
        cum = np.cumsum(dH0[None, :] * lp, axis=1)                                   # cumulative hazard per path
        surv_path = np.exp(-cum)
        e = rng.exponential(1.0, size=n)
        dead = cum >= e[:, None]                                                      # dead by step k
        death_step = np.where(dead.any(axis=1), dead.argmax(axis=1), ts + 1)
        kf_step = np.minimum(np.round(np.where(np.isfinite(kf_first), kf_first, (ts + 1) * STEP * 10) / STEP), ts + 1).astype(int)
        outcomes = {"years": [round(float(x), 2) for x in tt], "ok": [], "kidney_failure": [], "died_before_kf": [], "died_after_kf": []}
        for k in range(ts + 1):
            is_dead = death_step <= k
            has_kf = kf_step <= k
            outcomes["ok"].append(round(float((~is_dead & ~has_kf).mean()) * 100, 1))
            outcomes["kidney_failure"].append(round(float((~is_dead & has_kf).mean()) * 100, 1))
            outcomes["died_before_kf"].append(round(float((is_dead & (death_step < kf_step)).mean()) * 100, 1))
            outcomes["died_after_kf"].append(round(float((is_dead & (death_step >= kf_step) & has_kf).mean()) * 100, 1))
        s_mean = surv_path.mean(axis=0)
        survival = {"years": [round(float(x), 2) for x in tt], "alive_pct": (s_mean * 100).round(1).tolist(),
                    "p10": (np.percentile(surv_path, 10, axis=0) * 100).round(1).tolist(), "p90": (np.percentile(surv_path, 90, axis=0) * 100).round(1).tolist()}
        at = {}
        for y in (1, 3, 5, 10):
            if y <= min(horizon, MAX_SURV_YEARS):
                at[str(y)] = round(float(s_mean[int(round(y / STEP))]) * 100, 1)
        survival["at"] = at
        below_half = np.where(s_mean < 0.5)[0]
        survival["group_median_years"] = None if below_half.size == 0 else round(float(tt[below_half[0]]), 1)

    return {"bands": bands, "milestones": miles, "outcomes": outcomes, "survival": survival, "slope": {"mean": round(float(mu), 2), "sd": round(float(sd), 2)},
            "kf": {"p_by": {str(y): round(float((kf_first <= y).mean()), 3) for y in (2, 5, 10) if y <= horizon}}}


def stage_of(egfr: float) -> str:
    return "G1" if egfr >= 90 else "G2" if egfr >= 60 else "G3a" if egfr >= 45 else "G3b" if egfr >= 30 else "G4" if egfr >= 15 else "G5"


# What typically goes on at each stage, in plain language, plus what to do. Rule-based guidance from KDIGO-style summaries; a doctor decides.
STAGE_GUIDE = {
    "G1": {"title": "Normal filtering", "happens": ["Few or no symptoms", "Protein in urine or high blood pressure may be the only sign"], "do": ["Check kidney tests once a year", "Keep blood pressure and sugar in range", "Avoid regular pain-killers (ibuprofen, diclofenac)"]},
    "G2": {"title": "Mildly reduced", "happens": ["Usually no symptoms", "Risk of heart disease is already higher"], "do": ["Kidney tests every 6 to 12 months", "Treat high blood pressure and diabetes", "Keep salt low"]},
    "G3a": {"title": "Mild to moderate loss", "happens": ["Often no symptoms", "Anaemia and bone changes can begin"], "do": ["See a doctor every 3 to 6 months", "Ask about ACE inhibitor / ARB and SGLT2 inhibitor", "Check dose of every medicine"]},
    "G3b": {"title": "Moderate to severe loss", "happens": ["Tiredness, swelling and anaemia become more common", "Blood potassium and phosphate may rise"], "do": ["Nephrologist (kidney specialist) review", "Blood tests every 3 months", "Plan diet with a dietitian"]},
    "G4": {"title": "Severe loss", "happens": ["Tiredness, poor appetite, swelling, itching are common", "High potassium, acidity, anaemia and bone disease need treatment"], "do": ["Nephrologist follow-up every 1 to 3 months", "Learn about dialysis and transplant now", "Protect your arm veins (no needles in the non-dominant arm)", "Start thinking about donors and tissue typing"]},
    "G5": {"title": "Kidney failure range", "happens": ["Kidneys cannot clear enough waste and fluid", "Dialysis or a transplant is usually needed, often when symptoms appear"], "do": ["Be under a nephrologist's care now", "Plan dialysis access or a transplant", "Know the danger signs: breathlessness, very little urine, confusion, vomiting"]},
}


def build_journey(p: dict, levers: list[str] | None = None, horizon: float = 15.0, today: dt.date | None = None, cox: dict | None = None, seed: int = 11) -> dict:
    """p: age, male(bool), diabetes, sbp, hba1c, acr, egfr0, hgb, history_t, history_egfr. Returns the full journey for 'current care' and 'with levers'."""
    today = today or dt.date.today()
    horizon = float(min(max(horizon, 5.0), 20.0))
    p = dict(p)
    p["male"] = int(bool(p.get("male")))
    p["acr_for_cox"] = p["acr"] if p.get("acr") is not None else 10.0
    p["sbp_for_cox"] = p["sbp"] if p.get("sbp") is not None else 125.0
    p["hba1c_for_cox"] = p["hba1c"] if p.get("hba1c") is not None else (7.0 if p["diabetes"] else 5.5)
    p["hgb_for_cox"] = p["hgb"] if p.get("hgb") is not None else 13.0
    p["sbp"] = p["sbp"] if p.get("sbp") is not None else 125.0
    p["hba1c"] = p["hba1c"] if p.get("hba1c") is not None else (7.0 if p["diabetes"] else 5.5)
    p["acr"] = p["acr"] if p.get("acr") is not None else 10.0
    levers = [l for l in (levers or []) if l in LEVERS]
    if not levers:
        levers = list(LEVERS)                                      # default comparison: everything that applies
    cur = _simulate(p, [], horizon, seed, today, cox)
    imp = _simulate(p, levers, horizon, seed, today, cox)
    p50 = cur["bands"]["p50"]
    stage_now = stage_of(p["egfr0"])
    timeline = []
    for y in range(0, int(horizon) + 1, 1):
        i = int(round(y / STEP))
        e = p50[i]
        e2 = imp["bands"]["p50"][i]
        timeline.append({"year": today.year + y, "age": int(round(p["age"] + y)), "t": y, "egfr_current": e, "egfr_levers": e2, "stage_current": stage_of(e), "stage_levers": stage_of(e2)})
    return {
        "today": today.isoformat(), "age": p["age"], "egfr_now": round(p["egfr0"], 1), "stage_now": stage_now, "horizon": horizon,
        "current": cur, "with_levers": imp, "levers_used": levers,
        "levers_info": {k: v for k, v in LEVERS.items()}, "timeline": timeline, "stage_guide": STAGE_GUIDE,
        "assumptions": [
            "Decline rate starts from published ranges (faster with urine protein, diabetes, high blood pressure, older age) and is blended with the patient's own lab trend when there are 3 or more results.",
            "Lever effects use typical trial ranges (SGLT2 about 30%, ACE/ARB about 35% less urine protein) and are estimates, not promises.",
            "Survival comes from a Cox model fitted on US NHANES adults (2005-2014) with follow-up to 2019. It is a group statistic and is applied to each simulated path's own age and eGFR.",
            "The model never predicts when any one person will die. Numbers read 'out of 100 people like you'.",
        ],
    }
