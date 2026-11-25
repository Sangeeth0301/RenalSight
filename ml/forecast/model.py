"""Model parameters and the covariate-driven factors of SALT-FG (see SPEC.md sections 2.1 to 2.3)."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

import progression as pg
import trajectory as tj

DT = 0.25                      # quarterly grid, years
BASE_AGEING = -0.8             # healthy ageing slope, mL/min/1.73 m^2 per year


def _default(arr):
    return field(default_factory=lambda: np.array(arr, float))


@dataclass
class Params:
    """Hyper-parameters. K regimes ordered from slow to rapid decline."""

    K: int = 3
    prior_scale: float = 1.0                 # learnable multiplier on the covariate-driven excess decline (TRUST V1)
    tau: float = 2.0                         # slope mean-reversion time (years)
    q_L: float = 0.8                         # level process variance rate (per year)
    q_b: np.ndarray = _default([0.15, 0.35, 0.8])     # slope process variance rate per regime
    R: float = 9.0                           # visit noise variance (3.0^2)
    pi_out: float = 0.04                     # outlier probability of a lab value (AKI spike, assay error)
    R_out: float = 225.0                     # outlier variance (15^2)
    g: np.ndarray = _default([0.5, -0.3, -1.6])       # regime offsets on the slope mean
    stay: float = 0.95                       # per-quarter probability of staying in a regime
    up_bias: float = 0.65                    # share of leaving probability that goes towards faster decline
    gamma: np.ndarray = _default([-0.3, 0.1, 0.7])    # risk tilt on entering each regime
    pi_init: np.ndarray = _default([0.45, 0.40, 0.15])
    L0_mean: float = 55.0                    # diffuse prior on the first level
    L0_sd: float = 25.0
    b0_sd: float = 1.5
    lam0: float = 0.012                      # baseline death hazard per year at age 60
    death_age: float = 0.09                  # log-hazard per year of age
    death_l45: float = 0.8                   # extra relative hazard when eGFR < 45
    death_l30: float = 1.2                   # extra relative hazard when eGFR < 30
    death_l15: float = 2.0                   # extra relative hazard when eGFR < 15 (not reached before KF is declared)

    def __post_init__(self):
        if self.K == 1:
            self.q_b, self.g, self.gamma, self.pi_init = self.q_b[:1], np.zeros(1), np.zeros(1), np.ones(1)
        elif self.K != 3:
            raise ValueError("K must be 1 or 3")

    @property
    def rho(self) -> float:
        return float(np.exp(-DT / self.tau))


def with_updates(p: Params, **kw) -> Params:
    return replace(p, **kw)


# ----------------------------------------------------------------------------- covariate factor
def prior_mean_slope(x: dict) -> float:
    """mu0(x): the covariate prior slope used by SALT."""
    return float(pg.prior_slope(x["age"], x["diabetes"], x["sbp"], x["hba1c"], x["acr"]))


def risk_score(x: dict) -> float:
    """r(x) >= 0: how much faster than healthy ageing the covariates predict decline (mL/min/yr)."""
    return float(max(-(prior_mean_slope(x) - BASE_AGEING), 0.0))


def do_covariates(x: dict, levers: list[str] | None) -> tuple[dict, float]:
    """Causal edges from actions to covariates (BP, HbA1c, ACR) and the SGLT2 multiplier on the excess decline."""
    if not levers:
        return dict(x), 1.0
    p = dict(x)
    p.setdefault("egfr0", 60.0)
    q, mult = tj.apply_levers(p, list(levers))
    return q, mult


def regime_slope_means(x: dict, params: Params, levers: list[str] | None = None) -> np.ndarray:
    """m_k(x, a) for k = 1..K  (SPEC 2.2)."""
    q, mult = do_covariates(x, levers)
    excess = min(prior_mean_slope(q) - BASE_AGEING, 0.0)
    return BASE_AGEING + params.prior_scale * mult * excess + params.g


def transition_matrix(x: dict, params: Params, levers: list[str] | None = None) -> np.ndarray:
    """P(S_{t+1}=k | S_t=j, x): sticky chain tilted towards rapid regimes by the risk score (SPEC 2.3)."""
    K = params.K
    if K == 1:
        return np.ones((1, 1))
    q, _ = do_covariates(x, levers)
    r = risk_score(q)
    ub = params.up_bias
    W = np.array([[0.0, 0.7, 0.3], [1.0 - ub, 0.0, ub], [0.3, 0.7, 0.0]])    # where leaving mass goes (rows sum to 1)
    P = (1.0 - params.stay) * W
    np.fill_diagonal(P, params.stay)
    P = P * np.exp(params.gamma * r)[None, :]
    return P / P.sum(axis=1, keepdims=True)


def initial_regime_probs(x: dict, params: Params) -> np.ndarray:
    p = params.pi_init * np.exp(params.gamma * risk_score(x))
    return p / p.sum()


def death_hazard(age: np.ndarray, egfr: np.ndarray, params: Params) -> np.ndarray:
    """lambda_D per year (SPEC 4). Vectorised over members."""
    rel = 1.0 + params.death_l45 * (egfr < 45) + params.death_l30 * (egfr < 30) + params.death_l15 * (egfr < 15)
    return params.lam0 * np.exp(params.death_age * (age - 60.0)) * rel
