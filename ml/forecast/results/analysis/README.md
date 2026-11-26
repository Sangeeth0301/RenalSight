# Deeper analysis of the forecast (simulated test patients)

Built from per-patient data in `long_T0_*.csv.gz` / `patients_T0_*.csv.gz` (1,000 patients per history length, every horizon and method).
Regenerate: `python -m forecast.analysis` then `python -m forecast.figures.analysis_figs` and `python -m forecast.figures.analysis_engine`.
Figures: `../figures/analysis/` (a1-a12). Statistics: `paired_tests.csv`, `stage_recalibration.json`.

| Figure | What it shows |
|---|---|
| a1 | CRPS skill vs SALT and vs the prior, by stage and horizon; per-patient win rate |
| a2 | Subgroup forest plot (age, sex, diabetes, albuminuria, stage, visits) |
| a3 | Calibration surface (coverage by stage and horizon; raw vs conformal) |
| a4 | Error anatomy: error and bias by horizon and stage, sharpness, rank histograms |
| a5 | ROC, decision curves and reliability for kidney failure at 2 and 5 years vs KFRE |
| a6 | Time-dependent AUC |
| a7 | Effect of history length |
| a8 | Milestone ranges and milestone-probability calibration |
| a9 | Stage-conditional recalibration |
| a10-a12 | Sensitivity tornado, partial dependence, sources of uncertainty |

Findings worth knowing: skill is largest in advanced stages (up to about 40-60% CRPS reduction at eGFR 15-20) and smallest at eGFR 45+; the forecast is
biased by stage (too pessimistic at high eGFR, too optimistic at low eGFR) and G3b stays under-covered after calibration; a stage-conditional
correction gains only about 2% accuracy; milestone ranges conditional on realised crossings cover 39-46% (selection effect), while milestone
probabilities are well calibrated. All results are from a simulated world.
