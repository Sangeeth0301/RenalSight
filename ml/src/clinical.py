"""Clinical formulas used across RenalSight (no training needed).

* CKD-EPI 2021 (race-free) eGFR
* KDIGO GFR stage (G1-G5) and albuminuria category (A1-A3)
* Kidney Failure Risk Equation (KFRE), 4-variable version, 2- and 5-year risk

NOTE: KFRE constants below are transcribed from Tangri et al., JAMA 2016
(4-variable, non-North-America and North-America calibrations). They must be
re-checked against the paper before any real clinical use.
"""
from __future__ import annotations

import math

import numpy as np


# ---------------------------------------------------------------- eGFR
def egfr_ckdepi_2021(creatinine_mg_dl, age, female):
    """CKD-EPI 2021 creatinine equation, mL/min/1.73 m2. Works on scalars or numpy arrays."""
    scr = np.asarray(creatinine_mg_dl, dtype=float)
    age = np.asarray(age, dtype=float)
    female = np.asarray(female).astype(bool)
    kappa = np.where(female, 0.7, 0.9)
    alpha = np.where(female, -0.241, -0.302)
    ratio = scr / kappa
    egfr = (
        142.0
        * np.minimum(ratio, 1.0) ** alpha
        * np.maximum(ratio, 1.0) ** -1.200
        * 0.9938 ** age
        * np.where(female, 1.012, 1.0)
    )
    return egfr


# ---------------------------------------------------------------- staging
def gfr_stage(egfr):
    """KDIGO G stage as string: G1, G2, G3a, G3b, G4, G5."""
    e = float(egfr)
    if math.isnan(e):
        return None
    if e >= 90:
        return "G1"
    if e >= 60:
        return "G2"
    if e >= 45:
        return "G3a"
    if e >= 30:
        return "G3b"
    if e >= 15:
        return "G4"
    return "G5"


def albuminuria_category(acr_mg_g):
    """KDIGO A category from urine albumin/creatinine ratio (mg/g)."""
    a = float(acr_mg_g)
    if math.isnan(a):
        return None
    if a < 30:
        return "A1"
    if a <= 300:
        return "A2"
    return "A3"


def ckd_stage_number(egfr):
    """1-5 numeric stage used by the Living Kidney visual (GFR-based only)."""
    g = gfr_stage(egfr)
    return None if g is None else int(g[1])


def has_ckd(egfr, acr_mg_g):
    """Single-visit CKD flag: eGFR < 60 or ACR >= 30 mg/g (chronicity not confirmed)."""
    return bool((egfr < 60) or (acr_mg_g >= 30))


# ---------------------------------------------------------------- KFRE (4-variable)
_KFRE = {
    # baseline survival at 2 and 5 years, by calibration region
    "north_america": {2: 0.9750, 5: 0.9240},
    "non_north_america": {2: 0.9832, 5: 0.9365},
}


def kfre_4var(age, male, egfr, acr_mg_g, years=5, region="non_north_america"):
    """Probability of kidney failure (dialysis / transplant) within `years` (2 or 5)."""
    s0 = _KFRE[region][years]
    lp = (
        -0.2201 * (age / 10.0 - 7.036)
        + 0.2467 * (float(male) - 0.5642)
        - 0.5567 * (egfr / 5.0 - 7.222)
        + 0.4510 * (math.log(max(acr_mg_g, 0.1)) - 5.137)
    )
    return 1.0 - s0 ** math.exp(lp)


if __name__ == "__main__":
    # sanity checks against well-known reference values
    e = egfr_ckdepi_2021(1.0, 60, False)
    print("eGFR male 60y Scr 1.0 ->", round(float(e), 1), "(2021 equation: about 86)")
    e2 = egfr_ckdepi_2021(2.5, 65, True)
    print("eGFR female 65y Scr 2.5 ->", round(float(e2), 1), "stage", gfr_stage(e2))
    print("KFRE 5y (age 60, male, eGFR 25, ACR 500):", round(kfre_4var(60, 1, 25, 500, 5), 3))
    print("KFRE 2y same:", round(kfre_4var(60, 1, 25, 500, 2), 3))
