"""Conformal calibration of forecast bands (SPEC section 6): split CQR with Mondrian groups, and an adaptive variant for shift."""
from __future__ import annotations

from collections import defaultdict

import numpy as np


def cqr_score(lo: np.ndarray, hi: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.maximum(lo - y, y - hi)


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Finite-sample corrected (1-alpha) quantile: the ceil((n+1)(1-alpha))-th smallest score."""
    s = np.sort(np.asarray(scores, float))
    n = len(s)
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    return float(s[min(k, n) - 1]) if n else float("inf")


class MondrianCQR:
    """Per-(horizon, group) offsets for the ensemble band. Falls back to the pooled horizon offset when a group is small."""

    def __init__(self, alpha: float = 0.2, min_group: int = 40):
        self.alpha, self.min_group = alpha, min_group
        self._scores: dict = defaultdict(list)
        self._q: dict = {}

    def fit(self, lo, hi, y, horizon, group):
        sc = cqr_score(np.asarray(lo), np.asarray(hi), np.asarray(y))
        self._scores.clear()
        for s, h, g in zip(sc, horizon, group):
            self._scores[(h, g)].append(s)
            self._scores[(h, None)].append(s)
        self._q = {k: conformal_quantile(np.array(v), self.alpha) for k, v in self._scores.items()}
        self._n = {k: len(v) for k, v in self._scores.items()}
        return self

    def offset(self, horizon, group) -> float:
        if self._n.get((horizon, group), 0) >= self.min_group:
            return self._q[(horizon, group)]
        return self._q.get((horizon, None), 0.0)

    def apply(self, lo, hi, horizon, group):
        q = np.array([self.offset(h, g) for h, g in zip(horizon, group)])
        return np.asarray(lo) - q, np.asarray(hi) + q


class AdaptiveConformal:
    """Adaptive conformal inference (Gibbs and Candes): alpha_t <- alpha_t + gamma (alpha - err_t) keeps long-run coverage under shift.

    One instance per horizon. `update(score_candidates...)` is called after each realised outcome.
    """

    def __init__(self, alpha: float = 0.2, gamma: float = 0.02, window: int = 500, init_scores=None):
        self.alpha, self.gamma, self.window = alpha, gamma, window
        self.alpha_t = alpha
        self.scores = list(init_scores) if init_scores is not None else []

    def offset(self) -> float:
        if not self.scores:
            return 0.0
        a = float(np.clip(self.alpha_t, 1e-3, 0.999))
        s = np.sort(np.array(self.scores[-self.window:]))
        return float(np.quantile(s, 1.0 - a, method="higher")) if self.alpha_t < 1.0 else float(s[0])

    def band(self, lo: float, hi: float) -> tuple[float, float]:
        q = self.offset()
        return lo - q, hi + q

    def update(self, lo: float, hi: float, y: float) -> bool:
        """Register an outcome; returns whether it was covered by the band that was issued."""
        blo, bhi = self.band(lo, hi)
        covered = bool(blo <= y <= bhi)
        self.alpha_t += self.gamma * (self.alpha - (0.0 if covered else 1.0))
        self.scores.append(float(cqr_score(np.array([lo]), np.array([hi]), np.array([y]))[0]))
        return covered
