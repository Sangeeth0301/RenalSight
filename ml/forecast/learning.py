"""Fit the filter hyper-parameters by maximising the marginal likelihood of training histories (TRUST V1, V2, V3).

Ordering constraints (q_b and g are monotone across regimes) are built into the parametrisation so regimes cannot swap labels.
A weak Gaussian prior on the log-parameters keeps the optimiser away from degenerate corners.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from .filtering import marginal_loglik
from .model import Params


def _expit(z):
    return 1.0 / (1.0 + np.exp(-z))


def vector_to_params(v: np.ndarray, K: int, base: Params) -> Params:
    if K == 1:
        return Params(K=1, q_L=float(np.exp(v[0])), q_b=np.array([np.exp(v[1])]), prior_scale=float(np.exp(v[2])), R=float(np.exp(v[3])), pi_out=float(_expit(v[4])),
                      tau=base.tau, R_out=base.R_out, lam0=base.lam0)
    qb0 = np.exp(v[1]); qb1 = qb0 * (1.0 + np.exp(v[2])); qb2 = qb1 * (1.0 + np.exp(v[3]))
    g1 = v[4]; g0 = g1 + np.exp(v[5]); g2 = g1 - np.exp(v[6])
    return Params(K=3, q_L=float(np.exp(v[0])), q_b=np.array([qb0, qb1, qb2]), g=np.array([g0, g1, g2]), stay=float(0.8 + 0.199 * _expit(v[7])),
                  prior_scale=float(np.exp(v[8])), R=float(np.exp(v[9])), pi_out=float(_expit(v[10])), tau=base.tau, R_out=base.R_out, lam0=base.lam0,
                  gamma=base.gamma, up_bias=base.up_bias)


def params_to_vector(p: Params) -> np.ndarray:
    if p.K == 1:
        return np.array([np.log(p.q_L), np.log(p.q_b[0]), np.log(p.prior_scale), np.log(p.R), np.log(p.pi_out / (1 - p.pi_out))])
    return np.array([np.log(p.q_L), np.log(p.q_b[0]), np.log(p.q_b[1] / p.q_b[0] - 1.0), np.log(p.q_b[2] / p.q_b[1] - 1.0), p.g[1], np.log(p.g[0] - p.g[1]),
                     np.log(p.g[1] - p.g[2]), np.log((p.stay - 0.8) / 0.199 / (1 - (p.stay - 0.8) / 0.199)), np.log(p.prior_scale), np.log(p.R),
                     np.log(p.pi_out / (1 - p.pi_out))])


def fit(patients: list[dict], K: int = 3, n_particles: int = 60, maxiter: int = 300, seed: int = 0, base: Params | None = None, verbose: bool = False):
    """patients: dicts with x, visits_t, visits_y (the histories up to the forecast origin). Returns (Params, info)."""
    base = base or Params(K=K)
    v0 = params_to_vector(base)
    prior_sd = 2.0
    calls = {"n": 0}

    def objective(v):
        calls["n"] += 1
        try:
            p = vector_to_params(v, K, base)
        except Exception:
            return 1e9
        ll = 0.0
        for i, pt in enumerate(patients):
            ll += marginal_loglik(pt["x"], pt["visits_t"], pt["visits_y"], p, n_particles, seed + i)
        pen = 0.5 * float(np.sum(((v - v0) / prior_sd) ** 2))
        val = -ll + pen
        if verbose and calls["n"] % 50 == 0:
            print(calls["n"], round(val, 2))
        return val if np.isfinite(val) else 1e9

    res = minimize(objective, v0, method="Powell", options={"maxiter": maxiter, "xtol": 1e-2, "ftol": 1e-4})
    fitted = vector_to_params(res.x, K, base)
    return fitted, {"neg_log_posterior": float(res.fun), "evaluations": calls["n"], "converged": bool(res.success), "start": float(objective(v0))}


def tune_predictive(params: Params, patients: list[dict], horizons=(0.5, 1.0, 2.0, 3.0), maxiter: int = 30, M: int = 200, n_particles: int = 100, seed: int = 0):
    """Stage 2: rescale the process-noise and mean-reversion settings to minimise the *multi-step* CRPS on training patients.

    The marginal likelihood fits one-step-ahead behaviour; forecast dispersion at long horizons also depends on heterogeneity the model does not
    contain, so these three scalars are tuned directly on the forecast objective (still on training data only).
    """
    from dataclasses import replace

    from .forecast import forecast_patient
    from .metrics import crps_ensemble

    idx = [int(round(h / 0.25)) for h in horizons]

    def objective(v):
        p = replace(params, q_L=params.q_L * float(np.exp(v[0])), q_b=params.q_b * float(np.exp(v[1])), tau=params.tau * float(np.exp(v[2])))
        tot, cnt = 0.0, 0
        for i, pt in enumerate(patients):
            ens = forecast_patient(pt["x"], pt["visits_t"], pt["visits_y"], p, horizon=max(horizons), n_particles=n_particles, M=M, seed=seed + i, t_origin=pt["T0"])
            for h, j in zip(horizons, idx):
                if pt["d_c"] > h:
                    tot += crps_ensemble(ens.Y[:, j], pt["eval_y"][h]); cnt += 1
        pen = 0.5 * float(np.sum((np.asarray(v) / 1.5) ** 2)) * 1e-3 * len(patients)
        return tot / max(cnt, 1) + pen

    res = minimize(objective, np.zeros(3), method="Powell", options={"maxiter": maxiter, "xtol": 1e-2, "ftol": 1e-4})
    v = res.x
    tuned = replace(params, q_L=params.q_L * float(np.exp(v[0])), q_b=params.q_b * float(np.exp(v[1])), tau=params.tau * float(np.exp(v[2])))
    return tuned, {"scales": [float(np.exp(x)) for x in v], "crps_start": float(objective(np.zeros(3))), "crps_end": float(res.fun)}
