"""SALT-FG: probabilistic eGFR forecasting with a switching state-space model, competing outcomes and conformal calibration.

See SPEC.md for the mathematics. Modules:

    model       parameters, covariate prior, regime transition matrix, lever (do) effects
    filtering   Rao-Blackwellised particle filter (exact Kalman per regime path)
    forecast    ensemble rollouts, first-passage times, cause-specific kidney-failure incidence, paired counterfactuals
    conformal   split-conformal (CQR) calibration of forecast bands, Mondrian groups
    metrics     CRPS, interval score, coverage, Brier, AUC, calibration, bootstrap
    simulator   mis-specified ground-truth world with potential outcomes
    learning    marginal-likelihood fitting of the filter hyper-parameters
    benchmark   head-to-head evaluation against SALT, the prior alone and the KFRE
"""
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
