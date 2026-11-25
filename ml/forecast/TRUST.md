# Trust case for the forecast

How we make a forecast something a clinician could rely on, and how we would find out if it is wrong.
Written **before** the benchmark is run. Acceptance criteria in section 3 are fixed in advance; failures are reported, not tuned away.

## 1. Vulnerability audit (what can go wrong, and what we do about it)

| # | Vulnerability | Why it matters | Design defence | Test that exercises it | Residual risk |
|---|---|---|---|---|---|
| V1 | Prior-slope coefficients are assumptions, not fitted | wrong prior biases short-history forecasts | prior treated as a *learnable hierarchical* factor with shrinkage; fitted by marginal likelihood; sensitivity sweep of every coefficient | sweep +-50% on coefficients; performance must degrade gracefully | real data still needed |
| V2 | Gaussian measurement noise | creatinine has outliers, AKI spikes, assay changes; one spike can bend a slope | **outlier-mixture observation model** (inlier N(0,R), outlier N(0,R_out)); responsibility sampled per particle | simulator injects spikes and t(5) noise; compare with Gaussian filter | spikes that look like real decline |
| V3 | Hidden regimes may be unidentifiable or label-switch | clinicians could over-read "phenotypes" | ordering constraint on regime means, informative priors, regimes shown only as internal state; posterior-predictive check against K=1 | ablation K=1 vs K=3; label stability across seeds | regimes need clinical meaning |
| V4 | Visit times are informative (sicker people are tested more) | biases slope and risk | model visit intensity as a function of recent level; report sensitivity | simulator with informative visits; compare naive vs adjusted | residual if intensity misspecified |
| V5 | Death modelled with an assumed hazard | competing risk drives kidney-failure incidence | hazard parameters fitted on NHANES linked mortality (real data); stress test with +-50% | hazard-misspecification sweep | population mismatch |
| V6 | Calibration guarantee needs exchangeability | fails under hospital/assay/population shift | **adaptive conformal inference** (online coverage control) plus drift monitor | covariate-shift stress test | fast abrupt shift |
| V7 | What-if effects are assumed, confounding is unmeasured | users may read scenarios as promises | effects from trial meta-analysis priors *with uncertainty*; outputs labelled scenarios; sensitivity analysis to hidden confounding | simulated confounded world; bounds must cover truth | observational confounding stays |
| V8 | Single model structure | one wrong structure fails silently | **ensemble of structurally different forecasters** (SALT, FG K=1, FG K=3, prior) combined by out-of-sample stacking; disagreement is an uncertainty signal | stack vs best single model; disagreement predicts error | all models share one blind spot |
| V9 | Particle filter noise and degeneracy | Monte-Carlo error can look like signal | report effective sample size, Monte-Carlo standard error; verify against exact math | K=1 equals exact Kalman; K=3 likelihood vs brute-force enumeration | very long histories |
| V10 | Bad or out-of-range input | unit errors (umol/L vs mg/dL) produce confident nonsense | **guard layer** validates ranges and units, detects out-of-distribution patients, abstains | fuzz tests, OOD detector evaluated on shifted cohort | subtle OOD |
| V11 | Evaluation circularity | grading on the model's own family overstates skill | simulator is **mis-specified** relative to the model; negative-control baselines | reported with and without the model's own family | simulation is still simulation |
| V12 | Tail risk is what matters (kidney failure is rare) | average scores hide tail miscalibration | tail-specific metrics: calibration by risk decile, Brier on the high-risk group, time-dependent AUC | decile calibration table | rare-event variance |
| V13 | Silent decay after deployment | calibration drifts | rolling coverage/calibration monitor with alert thresholds, retrain trigger | simulated drift detection delay | detection lag |

## 2. Core internal parts (definitions in SPEC.md, hardened here)

1. **Guard layer**: validates and normalises inputs, computes out-of-distribution score, decides *forecast* or *abstain*.
2. **Observation model**: `y_t = L_t + e_t`, `e_t ~ (1-pi) N(0,R) + pi N(0,R_out)`; also a per-assay bias term (later).
3. **Latent dynamics**: switching local-linear trend `(L, b)`, regime-dependent mean slope and process noise.
4. **Covariate factor**: hierarchical prior `m_k(x)` with learnable, shrunk coefficients and a full uncertainty (not a point prior).
5. **Regime chain**: sticky HMM tilted by risk score; ordering-constrained.
6. **Visit process** (optional but tested): intensity depends on recent level so informative sampling is not ignored.
7. **Competing outcomes**: cause-specific hazards; kidney failure as first passage of `L`, death with fitted hazard.
8. **Inference engine**: Rao-Blackwellised particle filter, diagnostics (ESS, MC standard error), exact checks.
9. **Forecast ensemble**: forward simulation of the *whole* state including process noise; paired counterfactual rollouts.
10. **Model stack**: out-of-sample weighted combination across structurally different forecasters.
11. **Calibration layer**: split conformal bands, Mondrian groups, adaptive update under shift.
12. **Counterfactual module**: action effects with prior uncertainty, paired rollouts, hidden-confounding sensitivity.
13. **Evaluation and monitoring**: proper scoring rules, bootstrap intervals, drift monitor.

## 3. Pre-registered acceptance criteria

A claim is made only if its criterion is met on the benchmark with a held-out test set (>= 1000 patients) and
95% bootstrap intervals.

| Claim | Criterion |
|---|---|
| **Implementation is correct** | K=1 filter equals the exact Kalman filter to 1e-8; K=3 marginal likelihood matches brute-force regime enumeration within 1% for T <= 6 with 4000 particles |
| **Bands are calibrated** | marginal coverage of the nominal 80% band in [77%, 83%] at every horizon; every subgroup with n >= 100 in [72%, 88%] |
| **Better than SALT** | CRPS lower than SALT with the bootstrap 95% interval of the difference excluding zero; otherwise reported as "no better" |
| **Better kidney-failure risk than KFRE** | Brier lower and time-dependent AUC at least equal, with intervals; calibration slope in [0.8, 1.2] |
| **Robust to noise and spikes** | with 2x noise and 10% outliers, 80% coverage stays in [74%, 86%] after the adaptive layer |
| **Robust to shift** | under covariate/assay shift, rolling coverage returns to [75%, 85%] within 200 patients |
| **Honest abstention** | among forecasts issued (not abstained), coverage >= nominal - 2 points; abstention rate reported |
| **What-if is sound in a known world** | mean absolute error of 2-year effect on eGFR < 0.6 mL/min/1.73 m^2 without confounding; with hidden confounding, the sensitivity band contains the true effect in >= 90% of patients |
| **Stack helps** | stacked CRPS <= best single member's CRPS |

## 4. Guard layer: when the system refuses to forecast

* fewer than 2 laboratory values, or no value in the last 18 months
* eGFR already below 15 (route to clinician)
* creatinine or eGFR outside plausible range, or a unit mismatch flagged by the parser
* out-of-distribution score above the 99th percentile of the training population
* filter effective sample size below 20% or Monte-Carlo standard error above 1.0 mL/min/1.73 m^2
* member disagreement (spread of stacked forecasters) above the calibrated threshold

## 5. What we will never claim

* an individual date of death or kidney failure
* clinical validity from simulated evidence
* that what-if effects are causal for a given patient when only assumptions support them
* superiority without an interval that excludes zero
