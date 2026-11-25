"""Guard layer (TRUST section 4): decide whether to forecast or abstain, and say why."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .filtering import Filtered

FEATURES = ("age", "sbp", "hba1c", "log_acr", "diabetes")


def _vec(x: dict) -> np.ndarray:
    return np.array([x["age"], x["sbp"], x["hba1c"], np.log(max(x["acr"], 1.0)), float(x["diabetes"])], float)


@dataclass
class Decision:
    forecast: bool = True
    reasons: list[str] = field(default_factory=list)


class OODDetector:
    """Mahalanobis distance of the covariates to the training population; threshold at a high training quantile."""

    def fit(self, xs: list[dict], q: float = 0.99):
        M = np.array([_vec(x) for x in xs])
        self.mu = M.mean(axis=0)
        self.prec = np.linalg.pinv(np.cov(M.T) + 1e-6 * np.eye(M.shape[1]))
        self.threshold = float(np.quantile([self.score(x) for x in xs], q))
        return self

    def score(self, x: dict) -> float:
        d = _vec(x) - self.mu
        return float(np.sqrt(d @ self.prec @ d))


def check_input(x: dict, t, y, ood: OODDetector | None = None, t_origin: float | None = None, max_gap_years: float = 1.5) -> Decision:
    d = Decision()
    t, y = np.asarray(t, float), np.asarray(y, float)
    if len(y) < 2:
        d.reasons.append("fewer than 2 laboratory values")
    if len(y) and (y.min() < 1.0 or y.max() > 200.0 or not np.all(np.isfinite(y))):
        d.reasons.append("eGFR outside the plausible range (check units)")
    if len(y) and y[-1] < 15.0:
        d.reasons.append("eGFR already in the kidney-failure range: refer to a clinician")
    origin = t_origin if t_origin is not None else (t[-1] if len(t) else 0.0)
    if len(t) and origin - t[-1] > max_gap_years:
        d.reasons.append("last laboratory value is older than 18 months")
    for k, lo, hi in (("age", 18, 110), ("sbp", 70, 250), ("hba1c", 3.5, 18), ("acr", 0, 20000)):
        v = x.get(k)
        if v is None or not np.isfinite(v) or not (lo <= v <= hi):
            d.reasons.append(f"covariate {k} missing or out of range")
    if ood is not None and not d.reasons and ood.score(x) > ood.threshold:
        d.reasons.append("patient is unlike the training population (out of distribution)")
    d.forecast = not d.reasons
    return d


def check_filter(f: Filtered, min_ess_frac: float = 0.05) -> Decision:
    d = Decision()
    if f.ess < min_ess_frac * f.n:
        d.reasons.append("particle filter degenerated (effective sample size too low)")
    d.forecast = not d.reasons
    return d


def check_disagreement(spread: float, threshold: float) -> Decision:
    d = Decision()
    if spread > threshold:
        d.reasons.append("independent forecasters disagree beyond the calibrated threshold")
    d.forecast = not d.reasons
    return d
