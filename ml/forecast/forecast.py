"""Forward simulation, competing outcomes and paired counterfactuals (SPEC sections 4 and 5)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .filtering import Filtered, run_filter
from .model import DT, Params, death_hazard, regime_slope_means, transition_matrix

KF_EGFR = 15.0
MILESTONES = (60.0, 45.0, 30.0, 20.0, 15.0, 10.0)


@dataclass
class Noise:
    """Pre-drawn randomness so two scenarios can share it (common random numbers)."""
    idx: np.ndarray        # (M,) particle indices
    e0: np.ndarray         # (M, 2) initial-state noise
    ew: np.ndarray         # (M, H, 2) process noise
    ur: np.ndarray         # (M, H) regime uniforms
    ud: np.ndarray         # (M, H) death uniforms
    ey: np.ndarray         # (M, H+1) observation noise (standard normal)
    uo: np.ndarray         # (M, H+1) outlier uniforms


def draw_noise(filt: Filtered, M: int, H: int, rng: np.random.Generator) -> Noise:
    idx = rng.choice(filt.n, size=M, p=filt.w)
    return Noise(idx, rng.standard_normal((M, 2)), rng.standard_normal((M, H, 2)), rng.random((M, H)), rng.random((M, H)),
                 rng.standard_normal((M, H + 1)), rng.random((M, H + 1)))


@dataclass
class Ensemble:
    t: np.ndarray          # (H+1,) years from the forecast origin
    L: np.ndarray          # (M, H+1) latent eGFR
    Y: np.ndarray          # (M, H+1) predictive laboratory value
    S: np.ndarray          # (M, H+1) regime
    t_kf: np.ndarray       # (M,) first time latent eGFR < 15 (inf if never within horizon)
    t_d: np.ndarray        # (M,) death time (inf if alive at horizon)

    @property
    def M(self) -> int:
        return self.L.shape[0]

    def quantile(self, q, observed: bool = True) -> np.ndarray:
        return np.quantile(self.Y if observed else self.L, q, axis=0)

    def cif_kf(self, h: float) -> float:
        """Cause-specific cumulative incidence of kidney failure by h: kidney failure is declared no later than death (ties go to kidney failure)."""
        return float(np.mean((self.t_kf <= h) & (self.t_kf <= self.t_d)))

    def cif_death_before_kf(self, h: float) -> float:
        return float(np.mean((self.t_d <= h) & (self.t_d < self.t_kf)))

    def crossing(self, c: float) -> np.ndarray:
        """First-passage time of threshold c for every member (inf if not reached)."""
        below = self.L < c
        out = np.full(self.M, np.inf)
        hit = below.any(axis=1)
        out[hit] = self.t[below.argmax(axis=1)[hit]]
        return out

    def milestone_ranges(self, qs=(0.1, 0.5, 0.9)) -> dict:
        res = {}
        for c in MILESTONES:
            tc = self.crossing(c)
            res[c] = {"p": float(np.mean(np.isfinite(tc))), **{f"q{int(q * 100)}": (float(np.quantile(tc, q)) if np.mean(np.isfinite(tc)) > q else None) for q in qs}}
        return res

    def outcome_shares(self, h: float) -> dict:
        kf = self.t_kf <= h
        d = self.t_d <= h
        return {"working": float(np.mean(~kf & ~d)), "kf_alive": float(np.mean(kf & ~d)),
                "died_before_kf": float(np.mean(d & (self.t_d < self.t_kf))), "died_after_kf": float(np.mean(d & kf & (self.t_kf <= self.t_d)))}


def simulate(filt: Filtered, x: dict, params: Params, horizon: float, noise: Noise, levers: list[str] | None = None) -> Ensemble:
    """Roll the filtered belief forward. The *state* is sampled (process noise, regime changes), not only averaged."""
    M, H = noise.idx.shape[0], noise.ew.shape[1]
    i = noise.idx
    m = regime_slope_means(x, params, None)                  # the filtered slope b is the slope under *current* care and reverts to the untreated mean
    delta = regime_slope_means(x, params, levers) - m if levers else np.zeros(params.K)    # direct, immediate action effect on the slope (SPEC 5)
    P = transition_matrix(x, params, levers)
    cdf = np.cumsum(P, axis=1)
    rho = params.rho
    mu = filt.mu[i]
    p11, p12, p22 = filt.p11[i], filt.p12[i], filt.p22[i]
    L = mu[:, 0] + np.sqrt(p11) * noise.e0[:, 0]
    cond_sd = np.sqrt(np.maximum(p22 - p12 ** 2 / p11, 1e-12))
    b = mu[:, 1] + (p12 / p11) * (L - mu[:, 0]) + cond_sd * noise.e0[:, 1]
    S = filt.S[i].copy()
    Ls = np.empty((M, H + 1)); Ss = np.empty((M, H + 1), dtype=int)
    Ls[:, 0], Ss[:, 0] = L, S
    t_kf = np.full(M, np.inf); t_d = np.full(M, np.inf)
    age0 = float(x["age"])
    t = np.arange(H + 1) * DT
    t_kf[L < KF_EGFR] = 0.0
    for s in range(1, H + 1):
        S = np.minimum((noise.ur[:, s - 1][:, None] > cdf[S]).sum(axis=1), params.K - 1)
        L = L + DT * (b + delta[S]) + np.sqrt(params.q_L * DT) * noise.ew[:, s - 1, 0]
        b = rho * b + (1.0 - rho) * m[S] + np.sqrt(params.q_b[S] * DT) * noise.ew[:, s - 1, 1]
        L = np.maximum(L, 1.0)
        Ls[:, s], Ss[:, s] = L, S
        newly_kf = (L < KF_EGFR) & ~np.isfinite(t_kf)
        t_kf[newly_kf] = t[s]
        lam = death_hazard(age0 + t[s], L, params)
        dies = (noise.ud[:, s - 1] < 1.0 - np.exp(-lam * DT)) & ~np.isfinite(t_d)
        t_d[dies] = t[s]
    sd = np.sqrt(params.R)
    out = noise.uo < params.pi_out
    Y = Ls + noise.ey * np.where(out, np.sqrt(params.R_out), sd)
    return Ensemble(t=t, L=Ls, Y=np.maximum(Y, 2.0), S=Ss, t_kf=t_kf, t_d=t_d)


@dataclass
class Effect:
    """Paired counterfactual contrast (SPEC 5): treated minus control under shared noise."""
    t: np.ndarray
    delta_L_mean: np.ndarray
    delta_L_se: np.ndarray
    delta_cif_kf: dict
    control: Ensemble
    treated: Ensemble


def simulate_pair(filt: Filtered, x: dict, params: Params, horizon: float, levers: list[str], M: int = 2000, rng: np.random.Generator | None = None,
                  horizons=(2.0, 5.0)) -> Effect:
    rng = rng or np.random.default_rng(0)
    H = int(round(horizon / DT))
    noise = draw_noise(filt, M, H, rng)
    c = simulate(filt, x, params, horizon, noise, None)
    a = simulate(filt, x, params, horizon, noise, levers)
    d = a.L - c.L
    return Effect(t=c.t, delta_L_mean=d.mean(axis=0), delta_L_se=d.std(axis=0, ddof=1) / np.sqrt(M),
                  delta_cif_kf={h: a.cif_kf(h) - c.cif_kf(h) for h in horizons if h <= horizon}, control=c, treated=a)


def forecast_patient(x: dict, t, y, params: Params, horizon: float = 5.0, n_particles: int = 300, M: int = 1500, seed: int = 0,
                     t_origin: float | None = None, levers: list[str] | None = None) -> Ensemble:
    rng = np.random.default_rng(seed)
    filt = run_filter(x, t, y, params, n_particles, rng, t_end=t_origin)
    return simulate(filt, x, params, horizon, draw_noise(filt, M, int(round(horizon / DT)), rng), levers)
