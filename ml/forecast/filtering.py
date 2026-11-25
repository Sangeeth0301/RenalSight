"""Rao-Blackwellised particle filter for the switching local-linear-trend model (SPEC section 3).

Particles carry a sampled regime S and an exact Gaussian belief over z = (L, b). Everything is vectorised over particles.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import DT, Params, initial_regime_probs, regime_slope_means, transition_matrix


@dataclass
class Filtered:
    S: np.ndarray            # (N,) regime index
    mu: np.ndarray           # (N, 2) mean of (L, b)
    p11: np.ndarray          # (N,) Var(L)
    p12: np.ndarray          # (N,) Cov(L, b)
    p22: np.ndarray          # (N,) Var(b)
    w: np.ndarray            # (N,) normalised weights
    step: int                # last grid index processed
    logZ: float              # log marginal likelihood estimate of the observations
    ess: float

    @property
    def n(self) -> int:
        return len(self.w)


def to_grid(t, y, dt: float = DT) -> tuple[dict[int, float], int]:
    """Map irregular visits to grid steps (mean of visits that fall in the same step). Returns ({step: y}, last_step)."""
    t = np.asarray(t, float)
    y = np.asarray(y, float)
    t = t - t[0]
    steps = np.rint(t / dt).astype(int)
    obs: dict[int, list[float]] = {}
    for s, v in zip(steps, y):
        obs.setdefault(int(s), []).append(float(v))
    return {s: float(np.mean(v)) for s, v in obs.items()}, int(steps.max())


def _systematic_resample(w: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n = len(w)
    pos = (rng.random() + np.arange(n)) / n
    c = np.cumsum(w)
    c[-1] = 1.0
    return np.searchsorted(c, pos)


def _sample_regimes(S: np.ndarray, P: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    cdf = np.cumsum(P, axis=1)[S]                      # (N, K)
    u = rng.random((len(S), 1))
    return np.minimum((u > cdf).sum(axis=1), P.shape[0] - 1)


def kalman_predict(mu, p11, p12, p22, m_k, q_b_k, params: Params):
    """One Kalman prediction for A = [[1, dt], [0, rho]], c = (0, (1 - rho) m_k), Q = diag(q_L dt, q_b dt)."""
    rho = params.rho
    L = mu[:, 0] + DT * mu[:, 1]
    b = rho * mu[:, 1] + (1.0 - rho) * m_k
    n11 = p11 + 2.0 * DT * p12 + DT * DT * p22 + params.q_L * DT
    n12 = rho * (p12 + DT * p22)
    n22 = rho * rho * p22 + q_b_k * DT
    return np.stack([L, b], axis=1), n11, n12, n22


def run_filter(x: dict, t, y, params: Params, n_particles: int = 200, rng: np.random.Generator | None = None,
               t_end: float | None = None, levers: list[str] | None = None) -> Filtered:
    """Filter one patient's history. t: visit times (years), y: eGFR values. t_end: filter forward to this time (years from first visit)."""
    rng = rng or np.random.default_rng(0)
    obs, last = to_grid(t, y)
    S_end = last if t_end is None else max(last, int(round((t_end - float(np.asarray(t)[0])) / DT)))
    N, K = n_particles, params.K
    m = regime_slope_means(x, params, levers)
    P = transition_matrix(x, params, levers)
    S = rng.choice(K, size=N, p=initial_regime_probs(x, params))
    mu = np.stack([np.full(N, params.L0_mean), m[S]], axis=1)
    p11 = np.full(N, params.L0_sd ** 2)
    p12 = np.zeros(N)
    p22 = np.full(N, params.b0_sd ** 2)
    w = np.full(N, 1.0 / N)
    logZ = 0.0
    ess = float(N)
    for s in range(0, S_end + 1):
        if s > 0:
            S = _sample_regimes(S, P, rng)
            mu, p11, p12, p22 = kalman_predict(mu, p11, p12, p22, m[S], params.q_b[S], params)
        if s in obs:
            e = obs[s] - mu[:, 0]
            sv0 = p11 + params.R
            l0 = np.exp(-0.5 * (np.log(2.0 * np.pi * sv0) + e * e / sv0))
            if params.pi_out > 0:
                sv1 = p11 + params.R_out
                l1 = np.exp(-0.5 * (np.log(2.0 * np.pi * sv1) + e * e / sv1))
                lik = (1.0 - params.pi_out) * l0 + params.pi_out * l1
                outlier = rng.random(N) < (params.pi_out * l1 / np.maximum(lik, 1e-300))      # posterior responsibility
                sv = np.where(outlier, sv1, sv0)
            else:
                lik, sv = l0, sv0
            lw = np.log(w + 1e-300) + np.log(np.maximum(lik, 1e-300))
            mx = lw.max()
            ew = np.exp(lw - mx)
            logZ += mx + np.log(ew.sum())
            w = ew / ew.sum()
            k1, k2 = p11 / sv, p12 / sv
            mu = np.stack([mu[:, 0] + k1 * e, mu[:, 1] + k2 * e], axis=1)
            p22 = p22 - p12 * p12 / sv
            p12 = p12 - p11 * p12 / sv
            p11 = p11 - p11 * p11 / sv
            ess = float(1.0 / np.sum(w * w))
            if ess < 0.5 * N:
                idx = _systematic_resample(w, rng)
                S, mu, p11, p12, p22 = S[idx], mu[idx], p11[idx], p12[idx], p22[idx]
                w = np.full(N, 1.0 / N)
    return Filtered(S=S, mu=mu, p11=p11, p12=p12, p22=p22, w=w, step=S_end, logZ=float(logZ), ess=ess)


def marginal_loglik(x: dict, t, y, params: Params, n_particles: int = 100, seed: int = 0) -> float:
    return run_filter(x, t, y, params, n_particles, np.random.default_rng(seed)).logZ
