"""eGFR progression: prior slope model, individual-slope shrinkage, Monte-Carlo forecast, what-if scenarios.

Everything here is a SIMULATION-BASED estimate built from published decline-rate ranges
(typical CKD decline about 1-5 mL/min/1.73m2 per year; faster with proteinuria, diabetes, high BP).
It is not trained on real longitudinal patient data (none is freely available), and the app must say so.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

KF_EGFR = 15.0          # kidney failure threshold (stage 5)
HORIZON_YEARS = 30.0
EXCESS_SCALE = 0.5      # chosen by calibrate_vs_kfre.py (best agreement with KFRE, r=0.87; slightly conservative)
SLOPE_SD = 1.2          # between-patient SD of true slope around the covariate prior (mL/min/yr)
VISIT_NOISE_SD = 3.0    # measurement + short-term variation of eGFR between visits


# ------------------------------------------------------------------ prior slope
def prior_slope(age, diabetes, sbp, hba1c, acr, **_):
    """Expected annual eGFR change (negative = decline) from covariates. Coefficients: published-range assumptions."""
    acr = max(float(acr) if acr == acr else 10.0, 10.0)
    hba1c = 5.5 if hba1c is None or hba1c != hba1c else float(hba1c)
    sbp = 120.0 if sbp is None or sbp != sbp else float(sbp)
    slope = -0.8                                              # healthy ageing
    slope -= 0.9 * math.log10(acr / 10.0)                     # proteinuria: ACR 100 -> -0.9, 1000 -> -1.8
    slope -= 0.7 * float(diabetes)
    slope -= 0.25 * max(hba1c - 7.0, 0.0) * float(diabetes)   # poor glycaemic control
    slope -= 0.03 * max(sbp - 120.0, 0.0)                     # SBP 160 -> -1.2
    slope -= 0.01 * max(float(age) - 60.0, 0.0)
    return -0.8 + EXCESS_SCALE * (slope + 0.8)


# Assumed effect of guideline therapy (ACEi/ARB, SGLT2 inhibitor, statin, lifestyle): fraction of the
# *excess* decline removed. Trials suggest roughly 25-40%; we use 35% as the 'good care' default.
GOOD_CARE_REDUCTION = 0.35


# ------------------------------------------------------------------ synthetic follow-up generator
def simulate_patient(rng, age, male, diabetes, sbp, hba1c, acr, egfr0, years=5.0, visit_gap_months=3):
    """One simulated eGFR history. Returns dict with true slope and visit arrays."""
    mu = prior_slope(age, diabetes, sbp, hba1c, acr)
    slope = mu + rng.normal(0, SLOPE_SD)
    t = np.arange(0, years * 12 + 1e-9, visit_gap_months) / 12.0
    # random walk component keeps trajectories from being perfectly straight
    drift = np.cumsum(rng.normal(0, 0.6, size=t.size)) * 0.3
    true = egfr0 + slope * t
    obs = np.clip(true + drift + rng.normal(0, VISIT_NOISE_SD, size=t.size), 2.0, 140.0)
    return dict(true_slope=slope, prior_slope=mu, t=t, egfr=obs, true_egfr=true)


# ------------------------------------------------------------------ individual slope + shrinkage
def individual_slope(t_years, egfr):
    """OLS slope and its standard error from a patient's own measurements."""
    t = np.asarray(t_years, float)
    y = np.asarray(egfr, float)
    n = len(t)
    if n < 3 or (t.max() - t.min()) < 0.4:
        return None, None
    tc = t - t.mean()
    sxx = float((tc ** 2).sum())
    b = float((tc * (y - y.mean())).sum() / sxx)
    resid = y - (y.mean() + b * tc)
    s2 = float((resid ** 2).sum() / max(n - 2, 1))
    s2 = max(s2, VISIT_NOISE_SD ** 2 * 0.5)                  # do not trust implausibly tight fits
    return b, math.sqrt(s2 / sxx)


def posterior_slope(prior_mu, t_years, egfr):
    """Precision-weighted blend of covariate prior and the patient's own trend. Returns (mean, sd)."""
    b, se = individual_slope(t_years, egfr)
    if b is None:
        return prior_mu, SLOPE_SD
    w0, w1 = 1 / SLOPE_SD ** 2, 1 / se ** 2
    mean = (w0 * prior_mu + w1 * b) / (w0 + w1)
    return mean, math.sqrt(1 / (w0 + w1))


# ------------------------------------------------------------------ forecast
@dataclass
class Forecast:
    current_egfr: float
    slope_mean: float
    slope_sd: float
    years: list = field(default_factory=list)
    egfr_p10: list = field(default_factory=list)
    egfr_p50: list = field(default_factory=list)
    egfr_p90: list = field(default_factory=list)
    years_to_stage5_p10: float | None = None      # worst case (fast decline)
    years_to_stage5_p50: float | None = None
    years_to_stage5_p90: float | None = None      # best case (slow decline)
    prob_kf_2y: float = 0.0
    prob_kf_5y: float = 0.0
    prob_kf_10y: float = 0.0
    already_stage5: bool = False
    note: str = ""

    def to_dict(self):
        return self.__dict__.copy()


def forecast(current_egfr, slope_mean, slope_sd, horizon=15.0, n=4000, seed=7, step=0.5):
    """Monte-Carlo forecast of eGFR over `horizon` years and time to eGFR < 15."""
    rng = np.random.default_rng(seed)
    slopes = rng.normal(slope_mean, slope_sd, size=n)
    yrs = np.arange(0, horizon + 1e-9, step)
    # trajectories with growing process uncertainty
    paths = current_egfr + np.outer(slopes, yrs) + _brownian(rng, n, yrs)
    paths = np.maximum(paths + rng.normal(0, VISIT_NOISE_SD, size=paths.shape), 2.0)   # band = future *measured* eGFR
    fc = Forecast(current_egfr=float(current_egfr), slope_mean=float(slope_mean), slope_sd=float(slope_sd))
    fc.years = [round(float(y), 2) for y in yrs]
    fc.egfr_p10 = [round(float(v), 1) for v in np.percentile(paths, 10, axis=0)]
    fc.egfr_p50 = [round(float(v), 1) for v in np.percentile(paths, 50, axis=0)]
    fc.egfr_p90 = [round(float(v), 1) for v in np.percentile(paths, 90, axis=0)]
    if current_egfr < KF_EGFR:
        fc.already_stage5 = True
        fc.prob_kf_2y = fc.prob_kf_5y = fc.prob_kf_10y = 1.0
        fc.years_to_stage5_p10 = fc.years_to_stage5_p50 = fc.years_to_stage5_p90 = 0.0
        fc.note = "eGFR is already in the kidney-failure range; please contact a doctor."
        return fc
    # first crossing time using a longer, finer straight-line + noise simulation
    ty = np.arange(0, HORIZON_YEARS + 1e-9, 0.25)
    full = current_egfr + np.outer(slopes, ty) + _brownian(rng, n, ty)
    below = full < KF_EGFR
    crossed = below.any(axis=1)
    first = np.where(crossed, ty[below.argmax(axis=1)], np.inf)
    fc.prob_kf_2y = float((first <= 2).mean())
    fc.prob_kf_5y = float((first <= 5).mean())
    fc.prob_kf_10y = float((first <= 10).mean())
    fin = first[np.isfinite(first)]
    q = lambda p: float(np.quantile(first, p)) if (first <= HORIZON_YEARS).mean() > p else None
    fc.years_to_stage5_p10 = _r(q(0.10))   # fastest 10% of outcomes
    fc.years_to_stage5_p50 = _r(q(0.50))
    fc.years_to_stage5_p90 = _r(q(0.90))   # slowest 10% (None if beyond horizon)
    if fc.years_to_stage5_p50 is None:
        fc.note = "Most simulated paths do not reach kidney failure within %d years." % HORIZON_YEARS
    return fc


def _brownian(rng, n, times, sigma=1.2):
    """Random-walk process noise (sd = sigma*sqrt(t)) so paths wander smoothly instead of jumping."""
    dt = np.diff(times, prepend=0.0)
    steps = rng.normal(0, 1, size=(n, len(times))) * sigma * np.sqrt(dt)
    return np.cumsum(steps, axis=1)


def _r(v):
    return None if v is None or not np.isfinite(v) else round(v, 1)


def forecast_patient(age, male, diabetes, sbp, hba1c, acr, current_egfr, history_t=None, history_egfr=None,
                     scenario="no_change", horizon=15.0):
    """Full pipeline for one patient: prior -> blend with own history -> optional scenario -> forecast."""
    mu0 = prior_slope(age, diabetes, sbp, hba1c, acr)
    if history_t is not None and len(history_t) >= 3:
        mu, sd = posterior_slope(mu0, history_t, history_egfr)
    else:
        mu, sd = mu0, SLOPE_SD
    if scenario == "good_care":
        baseline = -0.8                                       # unavoidable ageing component
        excess = min(mu - baseline, 0.0)                      # extra decline beyond ageing (negative)
        mu = mu - excess * GOOD_CARE_REDUCTION                # remove 35% of the excess
    return forecast(current_egfr, mu, sd, horizon=horizon)


def whatif(base: dict, changes: dict, horizon=15.0):
    """Re-run the forecast after changing inputs (sbp, hba1c, acr, diabetes). Returns (baseline, modified)."""
    b = forecast_patient(**base, horizon=horizon)
    mod = {**base, **{k: v for k, v in changes.items() if k in ("sbp", "hba1c", "acr", "diabetes")}}
    m = forecast_patient(**mod, horizon=horizon)
    return b, m


if __name__ == "__main__":
    fc = forecast_patient(age=62, male=1, diabetes=1, sbp=150, hba1c=8.2, acr=400, current_egfr=38)
    print("no change  : years to stage 5 (fast/median/slow)", fc.years_to_stage5_p10, fc.years_to_stage5_p50, fc.years_to_stage5_p90, "| 5y risk %.2f" % fc.prob_kf_5y)
    fc2 = forecast_patient(age=62, male=1, diabetes=1, sbp=150, hba1c=8.2, acr=400, current_egfr=38, scenario="good_care")
    print("good care  : years to stage 5 (fast/median/slow)", fc2.years_to_stage5_p10, fc2.years_to_stage5_p50, fc2.years_to_stage5_p90, "| 5y risk %.2f" % fc2.prob_kf_5y)
