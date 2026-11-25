import numpy as np

import forecast  # noqa: F401
from forecast.conformal import AdaptiveConformal, MondrianCQR, conformal_quantile
from forecast.guard import OODDetector, check_input
from forecast.metrics import auc, brier, bootstrap_ci, calibration_slope_intercept, crps_ensemble, interval_score

X = dict(age=62.0, male=0, diabetes=True, sbp=150.0, hba1c=8.0, acr=300.0)


def test_crps_matches_the_closed_form_for_a_normal_forecast():
    rng = np.random.default_rng(0)
    members = rng.normal(0, 1, 40000)
    y = 0.7
    from scipy.stats import norm
    exact = y * (2 * norm.cdf(y) - 1) + 2 * norm.pdf(y) - 1 / np.sqrt(np.pi)       # CRPS of N(0,1) at y
    assert abs(crps_ensemble(members, y) - exact) < 0.01


def test_conformal_quantile_has_finite_sample_correction():
    s = np.arange(1, 10)                         # n = 9, alpha = 0.2 -> ceil(10 * 0.8) = 8th smallest
    assert conformal_quantile(s, 0.2) == 8.0


def test_split_conformal_gives_nominal_coverage_even_for_a_miscalibrated_band():
    rng = np.random.default_rng(1)
    def draw(n):
        y = rng.normal(0, 3.0, n)
        return np.full(n, -1.0), np.full(n, 1.0), y                                  # band far too narrow
    lo, hi, y = draw(4000)
    cq = MondrianCQR(0.2).fit(lo, hi, y, [1] * 4000, ["a"] * 4000)
    lo2, hi2, y2 = draw(20000)
    l, h = cq.apply(lo2, hi2, [1] * 20000, ["a"] * 20000)
    assert abs(np.mean((y2 >= l) & (y2 <= h)) - 0.8) < 0.02


def test_adaptive_conformal_recovers_coverage_after_a_shift():
    rng = np.random.default_rng(2)
    aci = AdaptiveConformal(0.2, gamma=0.05, init_scores=rng.normal(0, 1, 300) - 1.0)
    cov = []
    for i in range(3000):
        scale = 1.0 if i < 1000 else 3.0                     # variance triples after step 1000
        y = rng.normal(0, scale)
        cov.append(aci.update(-1.3, 1.3, y))
    assert abs(np.mean(cov[2000:]) - 0.8) < 0.04


def test_guard_abstains_on_bad_input_and_accepts_good_input():
    assert check_input(X, [0, 1], [50.0, 45.0]).forecast
    assert not check_input(X, [0.0], [50.0]).forecast
    assert not check_input(X, [0, 1], [50.0, 10.0]).forecast                        # already kidney failure
    assert not check_input(X, [0, 1], [5000.0, 4500.0]).forecast                    # unit error
    assert not check_input({**X, "age": 5.0}, [0, 1], [50.0, 45.0]).forecast


def test_ood_detector_flags_an_unusual_patient():
    rng = np.random.default_rng(3)
    train = [dict(age=float(rng.normal(55, 10)), sbp=float(rng.normal(130, 12)), hba1c=float(rng.normal(6.5, 1)), acr=float(np.exp(rng.normal(3.5, 1))), diabetes=bool(rng.random() < 0.3), male=1) for _ in range(800)]
    d = OODDetector().fit(train)
    odd = dict(age=95.0, sbp=215.0, hba1c=14.0, acr=15000.0, diabetes=True, male=1)
    assert not check_input(odd, [0, 1], [50.0, 45.0], ood=d).forecast


def test_metric_helpers_behave():
    assert brier(np.array([1.0, 0.0]), np.array([1, 0])) == 0.0
    assert auc(np.array([0.9, 0.1, 0.8, 0.2]), np.array([1, 0, 1, 0])) == 1.0
    s, i = calibration_slope_intercept(np.clip(np.random.default_rng(4).random(4000), 0.02, 0.98), (np.random.default_rng(5).random(4000) < 0.5).astype(int))
    assert np.isfinite(s) and np.isfinite(i)
    m, lo, hi = bootstrap_ci(np.arange(100.0), n=300)
    assert lo < m < hi
    assert interval_score(np.array([0.0]), np.array([1.0]), np.array([0.5]))[0] == 1.0
