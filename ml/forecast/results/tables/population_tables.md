# Population tables

### Population table 1. People in each state, millions (10-90%), status quo

| Year | G3a | G3b | G4 | Kidney failure | Dead |
|---|---|---|---|---|---|
| 2024 | 23.8 (23.1-24.3) | 7.7 (7.3-8.1) | 2.3 (2.0-2.6) | 0.8 (0.7-0.9) | 0.0 (0.0-0.0) |
| 2029 | 29.9 (28.9-31.0) | 9.3 (8.8-9.6) | 3.2 (2.8-3.4) | 2.0 (1.7-2.4) | 43.0 (38.8-46.3) |
| 2034 | 37.1 (33.9-38.7) | 11.8 (10.7-12.7) | 4.3 (3.8-4.7) | 2.9 (2.5-3.3) | 91.8 (86.5-100.5) |
| 2044 | 46.1 (43.3-50.4) | 17.1 (14.0-19.8) | 7.0 (5.5-7.7) | 5.6 (4.5-7.0) | 209.4 (197.9-223.9) |

### Population table 2. Programme impact over 20 years

| Code | Programme | Cumulative kidney failure 20 y, M | Averted, M (%) | People treated, M | Treated per case averted | KF person-years avoided, M |
|---|---|---|---|---|---|---|
| S0 | Status quo | 11.25 (9.53-13.51) | - | - | - | - |
| S1 | BP control + RAS blockade (60%) | 8.08 (6.78-9.34) | 3.17 (28%) | 97 | 32 | 13.5 |
| S2 | SGLT2 inhibitors (50%) | 10.55 (8.89-12.76) | 0.70 (6%) | 6 | 10 | 4.6 |
| S3 | Screening + early care (56%) | 7.18 (6.14-8.38) | 4.06 (36%) | 57 | 14 | 19.5 |
| S4 | Ambitious combined (80% + 70%) | 6.18 (5.28-7.29) | 5.07 (45%) | 129 | 26 | 23.1 |

### Population table 3. Calibration (shift 0.80, regime scale 0.40, noise scale 0.31, excess scale 2.40)

| Target | Real data | Engine | Source |
|---|---|---|---|
| US kidney-failure incidence (per million) | 363-386 | 363 | USRDS 2019-2021 |
| eGFR < 60 at 60-69 (pseudo-cohort) | 8.7% | 11.2% | NHANES |
| eGFR < 60 at 70-79 (pseudo-cohort) | 25.3% | 25.1% | NHANES |
| mean eGFR at 60-69 | 82.1 | 83.8 | NHANES |
| mean eGFR at 70-79 | 71.6 | 71.2 | NHANES |
| India incidence (per million), not used in fitting | 151-232 | 217 | Bhopal population study |

### Population table 4. Mortality model on held-out NHANES (C-index 0.855)

| Baseline eGFR | n (held out) | Observed 5 y | Predicted 5 y | Observed 10 y | Predicted 10 y |
|---|---|---|---|---|---|
| egfr>=90 | 7705 | 2.1% | 2.5% | 5.0% | 4.8% |
| egfr 60-90 | 3908 | 5.3% | 7.8% | 12.9% | 14.0% |
| egfr 45-60 | 635 | 18.8% | 19.8% | 41.9% | 33.5% |
| egfr 30-45 | 269 | 33.0% | 31.7% | 63.8% | 50.5% |
| egfr 15-30 | 85 | 47.0% | 42.3% | 69.9% | 61.5% |
| egfr<15 | 33 | 37.2% | 37.6% | 78.1% | 53.3% |

### Population table 5. Classical Markov cohort model fitted on years 1-5

| State at year 20 | Markov cohort error vs microsimulation |
|---|---|
| G3a | -31% |
| G3b | -32% |
| G4 | -27% |
| Kidney failure | -6% |
| Dead | -17% |

### Population table 6. Assumptions

| Item | Assumption |
|---|---|
| Population | India adults 2024 by age and sex (World Bank / UN projections); covariates and CKD pattern from NHANES; closed cohort (no new entrants) |
| Dynamics | SALT-FG patient-level equations with calibrated population scales |
| Death | Poisson hazard fitted on NHANES linked mortality |
| Programmes | coverage of eligible people; trial-range effects (ACR -35%, SGLT2 -30% of excess decline, BP to 125, HbA1c to 7) |
| Uncertainty | 10 replicates: resampled people, prior scale, treatment effects and death hazard drawn per replicate |
| Not modelled | effects on cardiovascular death, cost, adherence over time, India-specific covariates, new adults entering |
