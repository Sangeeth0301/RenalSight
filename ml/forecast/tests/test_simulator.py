import numpy as np
import pandas as pd

import forecast  # noqa: F401
from forecast.simulator import Shift, World

X = dict(age=62.0, male=0, diabetes=True, sbp=154.0, hba1c=8.3, acr=340.0)


def _patients(world, n=120, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        p = world.make_patient(rng, X, 45.0, 2.0)
        if p is not None:
            out.append(p)
    return out


def test_treated_world_preserves_more_kidney_function_for_same_noise():
    ps = _patients(World())
    d = np.array([p["L_t"][24] - p["L_c"][24] for p in ps])           # two years after the origin
    assert d.mean() > 0.5 and (d >= -1e-9).mean() > 0.9               # shared noise: treated is almost never worse


def test_history_is_identical_before_the_origin_and_visits_are_ordered():
    for p in _patients(World(), 30, 1):
        assert np.all(np.diff(p["visits_t"]) > 0) and p["visits_t"][-1] <= p["T0"] + 1e-9
        assert p["L_c"][0] == p["L_t"][0]


def test_shift_changes_the_data_in_the_expected_direction():
    base = np.mean([np.mean(p["visits_y"]) for p in _patients(World(), 80, 2)])
    biased = np.mean([np.mean(p["visits_y"]) for p in _patients(World(shift=Shift(assay_bias=-6.0)), 80, 2)])
    assert biased < base - 4.0
