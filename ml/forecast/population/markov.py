"""Classical Markov cohort model for comparison: one time-homogeneous annual stage-transition matrix, estimated from the first years of the
microsimulation (status quo), then projected by matrix powers. It shows what is lost when individual covariates, ageing and regime memory
are collapsed into a memoryless stage chain."""
from __future__ import annotations

import numpy as np


def estimate(results, years_used: int = 5) -> np.ndarray:
    """Row-normalised 6x6 annual transition matrix pooled over replicates and the first `years_used` years."""
    C = sum(r.state_matrices[:years_used].sum(axis=0) for r in results)
    T = C / np.maximum(C.sum(axis=1, keepdims=True), 1e-12)
    T[5] = 0.0; T[5, 5] = 1.0                                   # death is absorbing
    return T


def project(T: np.ndarray, p0: np.ndarray, years: int) -> np.ndarray:
    out = [p0]
    for _ in range(years):
        out.append(out[-1] @ T)
    return np.array(out)
