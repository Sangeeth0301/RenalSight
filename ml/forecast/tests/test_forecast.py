"""Forecast layer properties: monotone incidence, competing-risk bookkeeping, paired counterfactual sanity."""
import numpy as np

import forecast  # noqa: F401
from forecast.filtering import run_filter
from forecast.forecast import draw_noise, forecast_patient, simulate, simulate_pair
from forecast.model import Params

X = dict(age=62, male=0, diabetes=True, sbp=154, hba1c=8.3, acr=340)
T = [0, 0.5, 1.0, 1.5, 2.0]
Y = [47.1, 39.6, 33.9, 29.7, 24.7]


def test_cumulative_incidence_is_monotone_and_bounded():
    ens = forecast_patient(X, T, Y, Params(), horizon=5.0, seed=1)
    cif = [ens.cif_kf(h) for h in (0.5, 1, 2, 3, 5)]
    assert all(0.0 <= c <= 1.0 for c in cif) and all(b >= a - 1e-12 for a, b in zip(cif, cif[1:]))
    sh = ens.outcome_shares(5.0)
    assert abs(sum(sh.values()) - 1.0) < 1e-9


def test_kf_cif_plus_death_never_exceeds_one():
    ens = forecast_patient(X, T, Y, Params(), horizon=5.0, seed=2)
    assert ens.cif_kf(5.0) + ens.cif_death_before_kf(5.0) <= 1.0 + 1e-12


def test_higher_death_hazard_lowers_kidney_failure_incidence():
    lo = forecast_patient(X, T, Y, Params(lam0=0.012), horizon=6.0, seed=3).cif_kf(6.0)
    hi = forecast_patient(X, T, Y, Params(lam0=0.30), horizon=6.0, seed=3).cif_kf(6.0)
    assert hi < lo            # competing risk: dying first removes people from the kidney-failure count


def test_paired_counterfactual_is_beneficial_and_low_variance():
    filt = run_filter(X, T, Y, Params(), 300, np.random.default_rng(4))
    eff = simulate_pair(filt, X, Params(), 3.0, ["bp_control", "sglt2", "protein_drug"], M=3000, rng=np.random.default_rng(5))
    assert eff.delta_L_mean[-1] > 0.0                                  # treatment preserves eGFR on average
    assert np.all(eff.delta_L_se[1:] < 0.6)                            # common random numbers keep the contrast tight


def test_same_noise_gives_identical_ensemble():
    filt = run_filter(X, T, Y, Params(), 200, np.random.default_rng(6))
    n = draw_noise(filt, 500, 20, np.random.default_rng(7))
    a, b = simulate(filt, X, Params(), 5.0, n), simulate(filt, X, Params(), 5.0, n)
    np.testing.assert_array_equal(a.L, b.L)


def test_action_effect_is_immediate_and_equals_the_slope_shift_times_time():
    from forecast.model import regime_slope_means
    p = Params(K=1)
    filt = run_filter(X, T, Y, p, 50, np.random.default_rng(8))
    eff = simulate_pair(filt, X, p, 3.0, ["sglt2"], M=4000, rng=np.random.default_rng(9))
    shift = float(regime_slope_means(X, p, ["sglt2"])[0] - regime_slope_means(X, p, None)[0])
    assert shift > 0
    assert abs(eff.delta_L_mean[8] - 2.0 * shift) < 4 * eff.delta_L_se[8] + 1e-6          # at t = 2 years the gain is 2 x the slope shift
