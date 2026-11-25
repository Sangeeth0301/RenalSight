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
