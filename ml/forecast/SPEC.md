# SALT-FG: mathematical specification

A probabilistic forecasting model for eGFR trajectories with competing outcomes, written so every
quantity in the code has a definition here. Status: research prototype, validated on simulated data only.

## 1. Notation

| Symbol | Meaning |
|---|---|
| `t = 0, 1, 2, ...` | quarterly grid, step `dt = 0.25` year |
| `L_t` | true eGFR (mL/min/1.73 m^2), latent |
| `b_t` | true eGFR slope (mL/min/1.73 m^2 per year), latent |
| `z_t = (L_t, b_t)^T` | continuous latent state |
| `S_t in {1..K}` | discrete latent regime (progression phenotype), K = 3 transient regimes |
| `x` | baseline covariates: age, sex, diabetes, SBP, HbA1c, ACR |
| `a` | care action (levers), a subset of {BP, glycaemic, RAS blockade, SGLT2} |
| `y_t` | observed eGFR at visit t (missing when no visit) |
| `D`, `KF` | competing absorbing outcomes: death, kidney failure (first `L_t < 15`) |

## 2. Generative model

The joint density factorises over a dynamic graph whose factors are

```
p(S_{0:T}, z_{0:T}, y_{0:T} | x, a) =
    p(S_0 | x) p(z_0 | S_0, x)                                   (initial)
  * prod_t  P(S_{t+1} | S_t, x, a)                               (HMM factor)
  * prod_t  N(z_{t+1}; A z_t + c_{S_{t+1}}(x, a), Q_{S_{t+1}})    (switching state-space factor)
  * prod_t  N(y_t; H z_t, R)^{o_t}                               (observation factor)
```

with `H = (1, 0)`, `o_t = 1` when a visit occurred.

### 2.1 Continuous dynamics (switching local linear trend)

```
L_{t+1} = L_t + dt * b_t + w^L_t                 w^L ~ N(0, q_L dt)
b_{t+1} = rho * b_t + (1 - rho) * m_k(x, a) + w^b_t     w^b ~ N(0, q_{b,k} dt),   rho = exp(-dt / tau)
```

so `A = [[1, dt], [0, rho]]`, `c_k = (0, (1 - rho) m_k)`, `Q_k = diag(q_L dt, q_{b,k} dt)`.
The slope mean-reverts to a regime-specific mean `m_k`.

### 2.2 Slope mean = Bayesian-network (covariate) factor

```
m_k(x, a) = mu0(x_do(a)) + g_k  +  d_a
```

* `mu0(x)` is the covariate prior slope (existing `progression.prior_slope`).
* `g_k` is a regime offset (stable > 0 > rapid, g_1 > g_2 > g_3).
* `x_do(a)` is `x` after the causal edges from actions to risk factors (BP -> 125, HbA1c -> 7, ACR x 0.65).
* `d_a` is the direct effect of SGLT2: multiplies the *excess* decline by `1 - 0.30`.

This is the directed (causal) part of the graph. Risk factors among themselves (BP, HbA1c, ACR) are
related by undirected Markov ties, which only matter when imputing missing covariates; they carry
no causal meaning and are not used for do-operations.

### 2.3 Regime chain (HMM factor)

```
P(S_{t+1} = k | S_t = j, x) = Pi0[j,k] * exp(gamma_k * r(x)) / Z_j,       r(x) = standardised risk score from mu0(x)
```

`Pi0` is sticky (diagonal-dominant). `gamma_k` raises the propensity of moving into rapid regimes for
high-risk covariates. Death and kidney failure are absorbing outcomes handled in the forecast layer
(Section 4), not as filter states.

## 3. Inference (filtering)

Exact inference over the joint `(S, z)` is exponential in time. We use a **Rao-Blackwellised particle
filter**: sample the discrete regime path, integrate the Gaussian state exactly.

For particle `i` with regime `S^i_t`, state belief `N(mu^i_t, P^i_t)` and weight `w^i_t`:

1. sample `S^i_{t+1} ~ P(. | S^i_t, x)`
2. Kalman predict: `mu^- = A mu + c_k`,   `P^- = A P A^T + Q_k`
3. if visit: innovation `e = y - H mu^-`,  `s = H P^- H^T + R`,  weight `w <- w * N(e; 0, s)`,
   Kalman gain `K = P^- H^T / s`,  `mu = mu^- + K e`,  `P = (I - K H) P^-`
4. normalise weights; resample (systematic) if ESS < N/2.

Marginal likelihood estimate: `log p(y_{0:T}) ~ sum_t log( sum_i w^i_{t-1} * lik^i_t )`, used for learning.

Properties used in testing: with `K = 1` the filter equals the exact Kalman filter; with `R -> 0`
the level posterior collapses onto observations; the marginal-likelihood estimate is unbiased.

## 4. Forecasting and competing outcomes

From the filtered, resampled particles simulate `M` ensemble members forward (sampling regimes and
states, not only means), producing latent paths `L^m_{t+h}` and predictive observations
`y^m_{t+h} = L^m_{t+h} + v`, `v ~ N(0, R)`.

* first-passage time of threshold `c`: `T_c = inf{ t : L_t < c }`; `P(T_c <= h)` = share of members crossed.
* **kidney failure** is `T_15`.
* **death** has hazard `lambda_D(t) = lambda0 * exp(a1 (age - 60)/10 + a2 * 1[L_t < 30] + a3 * 1[L_t < 15])`,
  member-wise exponential waiting time. First of {`T_15`, death time} decides the outcome class, so
  `P(KF within h)` is a *cause-specific cumulative incidence*, not a naive one-minus-survival.

## 5. Counterfactuals (what-if)

For action set `a`, the same pipeline runs with `x -> x_do(a)` and `d_a`, re-using the *same* filtered
state and the same noise draws (common random numbers) so the estimated effect
`Delta(h) = E[L_{t+h} | do(a)] - E[L_{t+h} | do(no action)]` has low Monte-Carlo variance.
Identification rests on the assumed causal edges; it is **not** learned from observational data here.

## 6. Calibration layer (conformal)

Let `q_lo(h), q_hi(h)` be the ensemble `alpha/2` and `1 - alpha/2` quantiles at horizon `h`.
On a calibration set the conformalised-quantile-regression score is

```
s_i(h) = max( q_lo(h) - y_i(h),  y_i(h) - q_hi(h) )
```

and `qhat = Quantile_{(1+1/n)(1-alpha)}( s_1..s_n )`, computed per horizon bin and per Mondrian group
(diabetes, history length). The calibrated band is `[q_lo - qhat, q_hi + qhat]`.
Under exchangeability of calibration and test patients, `P(y in band) >= 1 - alpha` (marginal, within group).

## 7. Scoring rules

* CRPS of the ensemble `{x_m}` at observation `y`: `CRPS = mean|x_m - y| - 0.5 * mean|x_m - x_m'|`
* interval score (width + miss penalty), coverage, mean width
* Brier score and AUC for kidney failure within 5 years, calibration slope and intercept
* all reported with patient-level bootstrap 95% intervals

## 8. Ground-truth simulator (deliberately different from the model)

To avoid grading the model on its own family, the benchmark world differs:

* heavy-tailed measurement noise (Student-t, 5 d.o.f.), irregular visit gaps, missing labs
* nonlinear "acceleration" of decline below eGFR 30
* patient-level frailty random effect on slope (not in the model)
* regime process with 3 phenotypes but different dwell times and a covariate-dependent entry
* Gompertz death hazard
* potential outcomes: each patient simulated with and without treatment using shared noise, so the true
  individual treatment effect is known

## 9. Claims this prototype supports, and does not

Supports: correctness of the inference code (tests), calibrated uncertainty under exchangeability,
comparative accuracy against SALT, the prior alone, and KFRE *in the benchmark world*.

Does not support: clinical validity. Real longitudinal kidney data are required; the causal edges and
treatment effects are assumptions from trials, not estimates.
