# Kidney forecasting architecture (research core)

Scope: the forecasting system only. Interfaces, messaging and agents are out of scope here.
Diagrams: `docs/architecture/fig_forecast_pipeline.png` (inputs, stages, outputs) and
`docs/architecture/fig_factor_graph.png` (model structure). The mathematics is in `SPEC.md`.

## 1. Goal and the questions it answers

For a person with CKD and a short, irregular laboratory history, estimate the distribution of their future
kidney function and outcomes, with calibrated uncertainty, under today's care and under stated changes.

| Question | Output | Never output |
|---|---|---|
| How will eGFR move? | median and calibrated 80/95% bands per horizon | a single curve |
| When are the next milestones? | first-crossing ranges for eGFR 60/45/30/20/15/10 | one date |
| What are the odds of kidney failure vs death? | cause-specific cumulative incidence, population shares | an individual date of death |
| What if care changes? | effect on eGFR and on incidence, with uncertainty | an unqualified promise |

## 2. Inputs

| Group | Variables | Source and format | Role in the model | Status |
|---|---|---|---|---|
| Core labs | serum creatinine, cystatin C, eGFR (CKD-EPI 2021), urine ACR/UPCR, urea, potassium, haemoglobin | FHIR Observation, LOINC; lab-report PDFs through the existing parser | observation `y_t`; ACR enters the covariate prior | creatinine/eGFR/ACR in use |
| Vitals and metabolic | blood pressure series, HbA1c, glucose, BMI | FHIR / device / patient entry | covariates `x`; do-targets for levers | SBP/HbA1c in use |
| History and context | age, sex, diabetes, hypertension, CVD, prior AKI, admissions | EHR problem list | covariates `x`; death-hazard terms | age/sex/diabetes in use |
| Care actions | ACEi/ARB, SGLT2 inhibitor, BP and glycaemic control, nephrotoxin avoidance | medication orders, doctor entry | action nodes `a` for what-if | levers in use |
| Imaging (optional) | retinal photograph, renal ultrasound | image store, DICOM | image encoder output as extra covariates for early detection and the initial state | **future**; see note |
| Genetics / biomarkers (optional) | APOL1 genotype, urine or plasma biomarkers | lab systems | extra covariates for the regime prior | **future** |
| Free text (optional) | clinic notes, report text | NLP extraction to structured values | fills missing covariates | **future** |

Imaging note: deep-learning detection of CKD from retinal photographs has been published in
[Lancet Digital Health 2020](https://katalog.lib.cas.cz/KNAV/EdsRecord/edsair,edsair.doi.dedup.....1246839180218c04e8400985bfb1a0fd)
and a diabetic-kidney-disease model in Lancet Digital Health 2025 (AUC about 0.84 internally, 0.79-0.83 externally).
Those are detection tasks. We treat images as an optional input to the early state estimate, not as a core
forecasting input, until real paired imaging and longitudinal eGFR data are available.

## 3. Stages (each stage has a typed input and output contract)

| # | Stage | Input | Output | Key methods |
|---|---|---|---|---|
| 0 | Ingest and harmonise | raw labs, orders, reports | canonical `PatientRecord` (time-stamped, unit-normalised, de-identified) | FHIR/LOINC mapping, unit conversion, report parser |
| 1 | Quality and cohorting | `PatientRecord` | cleaned record plus quality flags | plausibility limits, duplicate and AKI-spike flags, eligibility, patient-level splits |
| 2 | Features and state build | clean record | quarterly grid, covariates `x`, risk score `r(x)`, observation mask | missing-data handling, causal covariate set |
| 3 | State estimation | grid, `x`, `y` | filtered belief over level `L`, slope `b`, regime `S` | Rao-Blackwellised particle filter (SPEC 3) |
| 4 | Forecast ensembles | filtered belief, horizon | latent and observed paths, first-crossing times, cause-specific incidence | forward simulation with competing death (SPEC 4) |
| 5 | What-if | filtered belief, action set `a` | paired counterfactual ensembles and effect estimates | causal edges, common random numbers (SPEC 5) |
| 6 | Calibration | ensemble, calibration set | calibrated bands, recalibrated risk | split conformal (CQR), Mondrian groups (SPEC 6) |
| 7 | Evaluation | forecasts, truth | scores with bootstrap intervals, baseline comparison | CRPS, Brier, AUC, coverage; KFRE, SALT, prior-only, foundation-model baselines |

## 4. Model portfolio (what runs inside stages 3 to 5)

1. **SALT** (existing): shrinkage slope plus level uncertainty. Interpretable baseline and fallback.
2. **SALT-FG core** (this work): switching local-linear-trend state space with an HMM regime chain and a
   covariate (Bayesian-network) slope factor; exact Kalman inside a particle filter.
3. **Generative ensemble head** (planned): learned residual dynamics in the spirit of probabilistic
   ensemble forecasting (Price et al., *Nature* 2024), once real data allow training.
4. **Competing-risk head**: death hazard plus kidney-failure first passage; deep survival variants planned.
5. **Foundation-model baseline**: pre-trained time-series model run zero-shot for comparison only.

## 5. Evaluation protocol (what makes the claims defensible)

* **Mis-specified ground truth**: the benchmark world differs from the model (heavy tails, acceleration
  below eGFR 30, frailty effect, different regime dwell times, Gompertz death). See SPEC 8.
* **Potential outcomes**: each simulated patient is run with and without treatment under shared noise, so
  counterfactual accuracy can be measured, not just asserted.
* **Metrics**: CRPS, interval score, coverage and width, Brier and AUC for kidney failure within 5 years,
  calibration slope, effect bias and RMSE. Patient-level bootstrap intervals.
* **Ablations**: no regimes (K = 1), no covariate factor, no conformal layer, no level uncertainty.
* **Baselines**: SALT, prior-only, own-trend, KFRE (risk only).
* **Real-data step (blocking for clinical claims)**: repeat on a credentialed longitudinal cohort.

## 6. Cross-cutting

* **Learning loop**: hyper-parameters fitted by marginal likelihood on training patients, refit per data window.
* **Registry**: versioned data window, code hash, seeds, parameters; rollback to the last calibrated model.
* **Monitoring**: coverage and calibration drift, input shift, subgroup gaps; alerts when calibration decays.
* **Safety and privacy**: ranges not dates, no individual death date, doctor confirms levers, local data, audit.

## 7. Build order

1. Spec, model, filter (done; filter smoke-tested, unit tests pending).
2. Rollouts, competing outcomes, counterfactual pairs.
3. Ground-truth simulator with potential outcomes.
4. Scoring rules, conformal layer, unit tests.
5. Hyper-parameter learning, benchmark against SALT/KFRE, ablations.
6. Real-data validation and the generative head.

## 8. Known limits

* All current evidence is simulated; clinical validity needs real longitudinal data.
* Causal edges and treatment effects are assumptions from trials, not learned here.
* Hidden regimes are identifiable only up to relabelling and need clinical interpretation.
