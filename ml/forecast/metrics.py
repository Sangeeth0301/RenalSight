"""Proper scoring rules and uncertainty-aware evaluation (SPEC section 7)."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score


def crps_ensemble(members: np.ndarray, y: float) -> float:
    """CRPS = E|X - y| - 0.5 E|X - X'| estimated from an ensemble (exact sort-based pair term)."""
    x = np.sort(np.asarray(members, float))
    m = len(x)
    term1 = np.mean(np.abs(x - y))
    i = np.arange(1, m + 1)
    pair = 2.0 * np.sum((2 * i - m - 1) * x) / (m * m)
    return float(term1 - 0.5 * pair)


def crps_matrix(members: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Row-wise CRPS: members (n, M), y (n,)."""
    return np.array([crps_ensemble(members[i], y[i]) for i in range(len(y))])


def interval_score(lo: np.ndarray, hi: np.ndarray, y: np.ndarray, alpha: float = 0.2) -> np.ndarray:
    return (hi - lo) + (2.0 / alpha) * (lo - y) * (y < lo) + (2.0 / alpha) * (y - hi) * (y > hi)


def coverage(lo: np.ndarray, hi: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((y >= lo) & (y <= hi)))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def auc(p: np.ndarray, y: np.ndarray) -> float:
    y = np.asarray(y)
    return float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan")


def calibration_slope_intercept(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Logistic recalibration of predicted risk: slope 1 and intercept 0 mean perfect calibration."""
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    z = np.log(p / (1 - p)).reshape(-1, 1)
    m = LogisticRegression(C=1e6, max_iter=1000).fit(z, np.asarray(y))
    return float(m.coef_[0, 0]), float(m.intercept_[0])


def decile_calibration(p: np.ndarray, y: np.ndarray, bins: int = 5):
    """Mean predicted vs observed risk by predicted-risk quantile (tail behaviour, TRUST V12)."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p <= hi if hi == edges[-1] else p < hi)
        if m.sum():
            out.append((float(p[m].mean()), float(y[m].mean()), int(m.sum())))
    return out


def bootstrap_ci(values: np.ndarray, stat=np.mean, n: int = 2000, seed: int = 0, level: float = 0.95) -> tuple[float, float, float]:
    """Patient-level bootstrap interval for a statistic of per-patient values (use paired differences for comparisons)."""
    v = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    s = np.array([stat(v[i]) for i in idx])
    a = (1 - level) / 2
    return float(stat(v)), float(np.quantile(s, a)), float(np.quantile(s, 1 - a))
