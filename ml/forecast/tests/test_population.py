"""Population engine invariants: same covariate formulas as the patient model, conservation of people, paired programme effects."""
import numpy as np
import pytest

import forecast  # noqa: F401
import progression as pg
from forecast.analysis import params_for
from forecast.model import Params, transition_matrix
from forecast.population.engine import Levers, draw_noise, load_population, prior_slope_v, run, transition_v
from forecast.population.mortality import Hazard, design, load_hazard



def test_vectorised_prior_slope_matches_the_patient_model():
    rng = np.random.default_rng(0)
    for _ in range(50):
        a, dm, sbp, h, acr = rng.uniform(25, 85), float(rng.random() < 0.4), rng.uniform(100, 190), rng.uniform(5, 11), float(np.exp(rng.uniform(1, 8)))
        assert abs(prior_slope_v(np.array([a]), np.array([dm]), np.array([sbp]), np.array([h]), np.array([acr]))[0] - pg.prior_slope(a, bool(dm), sbp, h, acr)) < 1e-12


def test_vectorised_transition_matrix_matches_the_patient_model():
    P = Params()
    x = dict(age=62, male=0, diabetes=True, sbp=154, hba1c=8.3, acr=340)
    from forecast.model import risk_score
    T = transition_v(np.array([risk_score(x)]), P)[0]
    np.testing.assert_allclose(T, transition_matrix(x, P), atol=1e-12)
    assert np.allclose(T.sum(axis=1), 1.0)


def test_hazard_rises_with_age_and_falling_egfr():
    h = Hazard(-5.0, np.array([0.08, 0.3, 0.2, 0.3, -0.2, 0.0, 0.2, 0.3, 0.6]))
    assert h(70, 1, 0, 15, 80) > h(50, 1, 0, 15, 80)
    assert h(60, 1, 0, 15, 20) > h(60, 1, 0, 15, 80)
    assert design([50], [1], [0], [15], [95]).shape == (1, 9)


@pytest.fixture(scope="module")
def setup():
    pop = load_population(2024)
    nz = draw_noise(len(pop), 3000, 40, pop.w, np.random.default_rng(1))
    return pop, nz, params_for(2.0), load_hazard()


def test_people_are_conserved_and_states_are_valid(setup):
    pop, nz, P, haz = setup
    r = run(pop, nz.idx, nz, Levers.none(len(pop)), P, haz, 10)
    np.testing.assert_allclose(r.counts.sum(axis=1), pop.total, rtol=1e-9)
    assert np.all(np.diff(r.counts[:, 5]) >= -1e-6)                       # the dead only accumulate
    assert np.isclose(r.counts[10, 5], r.deaths.sum(), rtol=1e-9)
    assert r.treated == 0.0


def test_programme_effect_is_paired_and_protective(setup):
    pop, nz, P, haz = setup
    allon = np.ones(len(pop), bool)
    base = run(pop, nz.idx, nz, Levers.none(len(pop)), P, haz, 10)
    trt = run(pop, nz.idx, nz, Levers(allon, allon, allon, allon), P, haz, 10)
    assert trt.incident_kf.sum() < base.incident_kf.sum()
    assert trt.treated > 0


def test_calibration_file_hits_its_targets():
    from forecast.population.calibrate import load_calibration
    c = load_calibration()
    lo, hi = c["targets"]["us_cases_per_year"]
    assert 0.85 * lo <= c["achieved_fresh_seed"]["us_cases_per_year"] <= 1.15 * hi
    for k in ("60-69", "70-79"):
        assert abs(c["achieved_fresh_seed"][k]["prev_lt60"] - c["targets"]["nhanes"][k]["prev_lt60"]) < 0.05


def test_importance_sampling_keeps_totals_unbiased(setup):
    pop, _, P, haz = setup
    boost = np.where(pop.ckd | (pop.dm > 0), 6.0, 1.0)
    tots = []
    for s in range(5):
        nz = draw_noise(len(pop), 3000, 4, pop.w, np.random.default_rng(10 + s), boost)
        tots.append(run(pop, nz.idx, nz, Levers.none(len(pop)), P, haz, 1).counts[0].sum())
    assert abs(np.mean(tots) / pop.total - 1.0) < 0.03
