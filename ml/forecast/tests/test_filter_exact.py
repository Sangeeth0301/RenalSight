"""Verification: the particle filter must agree with exact mathematics (TRUST.md, claim 'implementation is correct')."""
import itertools

import numpy as np

import forecast  # noqa: F401  (puts ml/src on the path)
from forecast.filtering import run_filter, to_grid
from forecast.model import DT, Params, initial_regime_probs, regime_slope_means, transition_matrix

X = dict(age=62, male=0, diabetes=True, sbp=154, hba1c=8.3, acr=340)
T = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25]
Y = [47.1, 44.0, 41.5, 36.9, 36.0, 31.2]


def reference_kalman(params, x, obs, last, regime_path):
    """Independent matrix-form Kalman filter for a fixed regime path. Returns (loglik, mean, cov) at the last step."""
    rho = params.rho
    A = np.array([[1.0, DT], [0.0, rho]])
    H = np.array([[1.0, 0.0]])
    m_k = regime_slope_means(x, params)
    mu = np.array([params.L0_mean, m_k[regime_path[0]]])
    P = np.diag([params.L0_sd ** 2, params.b0_sd ** 2])
    ll = 0.0
    for s in range(last + 1):
        k = regime_path[s]
        if s > 0:
            c = np.array([0.0, (1.0 - rho) * m_k[k]])
            Q = np.diag([params.q_L * DT, params.q_b[k] * DT])
            mu = A @ mu + c
            P = A @ P @ A.T + Q
        if s in obs:
            e = obs[s] - (H @ mu)[0]
            S = (H @ P @ H.T)[0, 0] + params.R
            ll += -0.5 * (np.log(2 * np.pi * S) + e * e / S)
            Kg = (P @ H.T)[:, 0] / S
            mu = mu + Kg * e
            P = P - np.outer(Kg, Kg) * S
    return ll, mu, P


def test_single_regime_equals_exact_kalman():
    params = Params(K=1, pi_out=0.0)
    obs, last = to_grid(T, Y)
    f = run_filter(X, T, Y, params, n_particles=50, rng=np.random.default_rng(0))
    ll, mu, P = reference_kalman(params, X, obs, last, [0] * (last + 1))
    assert abs(f.logZ - ll) < 1e-8
    np.testing.assert_allclose(f.mu[0], mu, atol=1e-8)
    assert abs(f.p11[0] - P[0, 0]) < 1e-8 and abs(f.p22[0] - P[1, 1]) < 1e-8


def test_three_regime_likelihood_matches_brute_force_enumeration():
    params = Params(K=3, pi_out=0.0)
    obs, last = to_grid(T, Y)
    Pi = transition_matrix(X, params)
    pi0 = initial_regime_probs(X, params)
    total = 0.0
    for path in itertools.product(range(3), repeat=last + 1):
        pr = pi0[path[0]] * np.prod([Pi[path[i], path[i + 1]] for i in range(last)])
        total += pr * np.exp(reference_kalman(params, X, obs, last, list(path))[0])
    estimates = [run_filter(X, T, Y, params, n_particles=3000, rng=np.random.default_rng(s)).logZ for s in range(8)]
    # the likelihood estimate is unbiased, so average the likelihoods (not the logs)
    est = np.log(np.mean(np.exp(np.array(estimates) - np.log(total))) ) + np.log(total)
    assert abs(est - np.log(total)) < 0.01 * abs(np.log(total)), (est, np.log(total))


def test_outlier_model_downweights_a_spike():
    y = list(Y)
    y[3] = 80.0                                           # an AKI-like spike
    robust = run_filter(X, T, y, Params(K=3, pi_out=0.05), n_particles=1500, rng=np.random.default_rng(1))
    plain = run_filter(X, T, y, Params(K=3, pi_out=0.0), n_particles=1500, rng=np.random.default_rng(1))
    clean = run_filter(X, T, Y, Params(K=3, pi_out=0.0), n_particles=1500, rng=np.random.default_rng(1))
    level = lambda f: float((f.w * f.mu[:, 0]).sum())
    assert abs(level(robust) - level(clean)) < abs(level(plain) - level(clean))


def test_weights_normalised_and_ess_reported():
    f = run_filter(X, T, Y, Params(K=3), n_particles=400, rng=np.random.default_rng(3))
    assert abs(f.w.sum() - 1.0) < 1e-9 and 1.0 <= f.ess <= 400.0
    assert np.all(f.p11 > 0) and np.all(f.p22 > 0)
