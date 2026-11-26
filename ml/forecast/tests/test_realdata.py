import numpy as np
import pytest

import forecast  # noqa: F401
from forecast import realdata as rd
from forecast.model import Params

MIMIC = rd.MIMIC


@pytest.mark.skipif(not (MIMIC / "labevents.csv.gz").exists(), reason="MIMIC demo not downloaded (python -m forecast.datasets)")
def test_loader_gives_ordered_plausible_trajectories():
    pts = rd.load_patients()
    assert len(pts) >= 10
    for p in pts:
        assert np.all(np.diff(p["t"]) > 0) and p["t"][-1] >= 0.75
        assert np.all((p["y"] > 3) & (p["y"] < 200)) and len(p["t"]) == len(p["y"]) >= 4
        assert 18 <= p["x"]["age"] <= 110


def test_origins_use_only_the_past_and_future_targets_in_range():
    p = dict(t=np.array([0, 0.3, 0.6, 1.0, 1.5, 4.0]), y=np.arange(6.0), ckd_coded=False)
    for i, tgt in rd.origins(p):
        assert i >= 2 and p["t"][i] - p["t"][0] >= 0.4
        assert all(0.2 <= p["t"][j] - p["t"][i] <= rd.HMAX and j > i for j in tgt)


def test_forecast_on_short_history_is_finite_and_has_the_right_shape():
    x = dict(age=60, male=1, diabetes=True, sbp=130, hba1c=7.0, acr=15)
    t, y = np.array([0, 0.4, 0.8, 1.2]), np.array([55.0, 52.0, 50.0, 47.0])
    Y = rd.fg_members(x, t, y, Params(), M=200)
    S = rd.salt_members(x, t, y, 200)
    assert Y.shape[0] == 200 and S.shape == (200, int(rd.HMAX / 0.25) + 1) and np.isfinite(Y).all() and np.isfinite(S).all()


def _toy_patients(n=8, seed=0):
    rng = np.random.default_rng(seed)
    P = {}
    for k in range(n):
        t = np.sort(np.r_[0.0, rng.uniform(0.1, 3.0, 9)])
        y = 60 - 2.5 * t + rng.normal(0, 3, t.size)
        P[k] = dict(id=k, t=t, y=y, x=dict(age=60.0, male=k % 2, diabetes=bool(k % 3 == 0), sbp=130.0, hba1c=6.5, acr=15.0), ckd_coded=False)
    return P


@pytest.mark.parametrize("method", ["persistence", "lmm"])
def test_lopo_baselines_never_see_the_held_out_patient_future(method):
    """Changing patient 0's later labs must not change any forecast for patient 0 (no leakage across the leave-one-patient-out split)."""
    from forecast import realdata_plus as rp
    P = _toy_patients()
    T = rp.targets(list(P.values()))
    a = getattr(rp, method)(P, T, np.random.default_rng(1))
    P2 = {k: dict(v) for k, v in P.items()}
    i_last = int(T[T.id == 0].origin.min())
    y = P2[0]["y"].copy(); y[i_last + 1:] += 40.0; P2[0]["y"] = y
    T2 = rp.targets(list(P2.values()))
    b = getattr(rp, method)(P2, T2, np.random.default_rng(1))
    k = next(k for k in a if k[0] == 0 and k[1] == i_last)
    np.testing.assert_allclose(a[k], b[k])
