"""Ground-truth world with potential outcomes (SPEC section 8).

Deliberately different from the forecasting model: heavy-tailed noise, AKI-like spikes, informative visit times,
nonlinear acceleration below eGFR 30, a frailty random effect, different regime dynamics, a Gompertz death hazard,
and a heterogeneous treatment effect. A `Shift` changes the world between calibration and test to stress the system.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import progression as pg

DS = 1.0 / 12.0                     # world step: one month
BASE = -0.8


@dataclass
class Shift:
    noise_scale: float = 1.0        # multiplies measurement noise sd
    outlier_rate: float = 0.03      # probability that a lab is an AKI-like downward spike
    assay_bias: float = 0.0         # constant additive bias on every lab (assay or lab change)
    risk_scale: float = 1.0         # multiplies the covariate-driven excess decline
    visit_scale: float = 1.0        # multiplies the gap between visits
    missing_rate: float = 0.0       # extra probability that a scheduled lab is missing


@dataclass
class World:
    excess_gain: float = 1.5        # world excess decline = excess_gain * model's (the model's prior understates it)
    frailty_sd: float = 0.9
    process_sd: float = 1.0         # per sqrt(year)
    noise_sd: float = 3.0
    t_df: float = 5.0
    accel: float = 0.05             # extra decline per unit eGFR below 30 (per year)
    offsets: tuple = (0.4, -0.4, -2.0)
    stay: tuple = (0.985, 0.975, 0.96)      # monthly regime persistence
    lam0: float = 0.012
    shift: Shift = field(default_factory=Shift)

    # ---------------------------------------------------------------------- pieces
    def base_slope(self, x: dict) -> float:
        raw = (pg.prior_slope(x["age"], x["diabetes"], x["sbp"], x["hba1c"], x["acr"]) - BASE) / 0.5     # covariate excess on the raw scale
        return BASE + 0.5 * self.excess_gain * raw * self.shift.risk_scale

    def treat_effect(self, x: dict) -> float:
        """Fraction of the excess decline removed by treatment (heterogeneous: larger with heavy albuminuria, smaller when old)."""
        return float(np.clip(0.32 + 0.10 * (x["acr"] >= 300) - 0.08 * (x["age"] > 70), 0.10, 0.50))

    def _regime_step(self, r: int, u: float, risk: float) -> int:
        up = 0.012 * (1.0 + risk)
        if r == 0:
            return 1 if u < up else (2 if u < up + 0.003 else 0)
        if r == 1:
            return 2 if u < 0.015 * (1.0 + risk) else (0 if u > 0.985 else 1)
        return 1 if u < 0.010 else 2

    def death_rate(self, age: float, L: float, diabetes: bool) -> float:
        rel = 1.0 + 1.0 * (L < 45) + 1.5 * (L < 30) + 2.5 * (L < 15)
        return self.lam0 * np.exp(0.09 * (age - 60.0)) * rel * (1.0 + 0.5 * float(diabetes))

    def measure(self, L: float, rng: np.random.Generator) -> float:
        sd = self.noise_sd * self.shift.noise_scale
        e = rng.standard_t(self.t_df) * np.sqrt((self.t_df - 2.0) / self.t_df) * sd
        spike = -abs(rng.normal(15.0, 6.0)) if rng.random() < self.shift.outlier_rate else 0.0
        return float(max(L + e + spike + self.shift.assay_bias, 2.0))

    # ---------------------------------------------------------------------- one patient
    def make_patient(self, rng: np.random.Generator, x: dict, L0: float, T0: float, horizon: float = 7.0) -> dict | None:
        """Simulate control and treated worlds from the same noise. T0 = forecast origin (years after the first visit)."""
        n = int(round((T0 + horizon) / DS))
        n0 = int(round(T0 / DS))
        frail = rng.normal(0.0, self.frailty_sd)
        base = self.base_slope(x) + frail
        risk = max(-(self.base_slope(x) - BASE), 0.0) / 3.0
        u_reg, z_proc, u_death = rng.random(n), rng.standard_normal(n), rng.random(n)
        r0 = int(rng.choice(3, p=[0.5 - 0.2 * min(risk, 1), 0.35, 0.15 + 0.2 * min(risk, 1)]))
        eff = self.treat_effect(x)

        def run(treated: bool, start: int, L: float, r: int):
            Ls, rs = [L], [r]
            kf, dd = np.inf, np.inf
            for k in range(start, n):
                r = self._regime_step(r, u_reg[k], risk)
                s = base + self.offsets[r]
                if treated:
                    ex = s - BASE
                    s = BASE + (1.0 - eff) * min(ex, 0.0) + max(ex, 0.0)
                s -= self.accel * max(30.0 - L, 0.0)
                L = max(L + DS * s + self.process_sd * np.sqrt(DS) * z_proc[k], 1.0)
                Ls.append(L); rs.append(r)
                t = (k + 1) * DS
                if not np.isfinite(kf) and L < 15.0:
                    kf = t
                if not np.isfinite(dd) and u_death[k] < 1.0 - np.exp(-self.death_rate(x["age"] + t, L, x["diabetes"]) * DS):
                    dd = t
            return np.array(Ls), np.array(rs), kf, dd

        Lc, rc, kf_c, d_c = run(False, 0, L0, r0)
        if kf_c <= T0 or d_c <= T0 or Lc[n0] < 15.0:
            return None                                           # not eligible: already failed or dead at the origin
        Lt, _, kf_t, d_t = run(True, n0, Lc[n0], int(rc[n0]))      # treatment starts at the forecast origin
        Lt = np.concatenate([Lc[:n0], Lt])
        # visits (informative: sicker people are tested more often), history only
        visits_t, visits_y = [0.0], [self.measure(L0, rng)]
        t = 0.0
        while True:
            Lnow = Lc[min(int(round(t / DS)), n)]
            gap = max(0.08, rng.exponential((0.35 if Lnow > 60 else 0.25 if Lnow > 30 else 0.15) * self.shift.visit_scale))
            t += gap
            if t > T0:
                break
            if rng.random() < self.shift.missing_rate:
                continue
            visits_t.append(t); visits_y.append(self.measure(Lc[min(int(round(t / DS)), n)], rng))
        hs = np.arange(1, int(round(horizon / 0.25)) + 1) * 0.25
        eval_y = {float(h): self.measure(Lc[min(n0 + int(round(h / DS)), n)], rng) for h in hs}
        return dict(x=x, visits_t=np.array(visits_t), visits_y=np.array(visits_y), T0=float(T0), L_T0=float(Lc[n0]),
                    kf_c=kf_c - T0, d_c=d_c - T0, kf_t=kf_t - T0, d_t=d_t - T0, eval_y=eval_y,
                    L_c=Lc[n0:], L_t=Lt[n0:], effect=eff)


def sample_covariates(df, rng: np.random.Generator, n: int):
    """Draw covariate rows from an NHANES-like frame with columns age, male, diabetes, sbp, hba1c, acr, egfr."""
    rows = df.sample(n, replace=len(df) < n, random_state=int(rng.integers(0, 2 ** 31 - 1))).reset_index(drop=True)
    for _, r in rows.iterrows():
        yield dict(age=float(r.age), male=int(r.male), diabetes=bool(r.diabetes), sbp=float(r.sbp), hba1c=float(r.hba1c), acr=float(r.acr)), float(r.egfr)
