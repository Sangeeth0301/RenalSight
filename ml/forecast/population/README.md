# Population face: kidney disease at health-system scale

The patient face forecasts one person's kidney trajectory. This face asks the system-level questions with the same engine: how many adults will
be at each stage, how many will reach kidney failure, how much dialysis and transplant demand follows, and what programmes would change it,
over 20 years for today's adults in India.

Architecture: `../results/figures/population/p00_architecture.png` (draw.io source in `docs/architecture/RenalSight_population_architecture.drawio`).

## Pipeline

| Step | Module | What it does |
|---|---|---|
| Population | `engine.load_population` | NHANES adults post-stratified to India's 2024 adult population by age and sex (World Bank / UN); optional anchoring to a target CKD prevalence |
| Mortality | `mortality.py` | Poisson hazard on NHANES linked deaths (age, sex, diabetes, albuminuria, current eGFR stage); fitted on half, validated on the other half (C-index 0.855) |
| Calibration | `calibrate.py` | Four population scales (slope shift, regime spread, process noise, excess-risk scale) fitted to real targets: US kidney-failure incidence (USRDS) and the NHANES age gradient of eGFR < 60 and mean eGFR; India incidence held out |
| Simulation | `engine.run` | Same state equations as the patient engine, vectorised; covariates refreshed yearly as people age; importance sampling of high-risk people with re-weighting |
| Programmes | `scenarios.py` | Status quo; BP + RAS blockade 60%; SGLT2 50%; screening + early care 56%; ambitious combined; 10 replicates with parameter and sampling uncertainty, paired random numbers |
| Comparison | `markov.py` | Classical memoryless Markov stage model fitted on years 1-5 |
| Results | `figures.py` | 12 figures and 6 tables (`python -m forecast.population.figures`) |

## Calibration and validation

| Target | Real data | Engine |
|---|---|---|
| US kidney-failure incidence, per million per year | 363-386 (USRDS 2019-2021) | 363 |
| eGFR < 60 at 60-69 (20 years after age 40-49) | 8.7% (NHANES) | 11.2% |
| eGFR < 60 at 70-79 (20 years after age 50-59) | 25.3% | 25.1% |
| Mean eGFR at 60-69 / 70-79 | 82.1 / 71.6 | 83.8 / 71.2 |
| India incidence, per million per year (not used in fitting) | 151-232 (Bhopal population study) | 217 |

Before calibration the engine put 70% of 40-59-year-olds below eGFR 60 twenty years later: the patient-level parameters were learned in a
CKD-enriched simulated world. Calibrating on incidence alone hid that; the age-gradient targets exposed and corrected it.

## Main projections (status quo, closed cohort of today's adults)

See `../results/tables/population_tables.md` for numbers with 10-90% intervals. In short: about 100 million adults have CKD today (10.4%);
new kidney failure rises from roughly 0.2-0.3 million to 0.7-0.8 million a year as the cohort ages; programmes avert about 6% (SGLT2 alone, narrow
eligibility) to about 45% (ambitious combined) of cumulative cases.

## Limits

1. Covariates and the CKD pattern are from US adults (NHANES), re-weighted to India's age and sex structure; India-specific risk factors are not modelled.
2. Closed cohort: people who turn 20 after 2024 are not added, so late-horizon totals understate the whole population.
3. Treatment effects use trial-range assumptions; effects on cardiovascular death, cost and adherence over time are not modelled.
4. The mortality model treats eGFR stage as fixed when checked alone and under-predicts 10-year deaths at low eGFR; in the engine eGFR evolves.
5. Women reach kidney failure more often than men in this engine (driven by NHANES eGFR distributions); registries usually show the reverse,
   so sex-specific results should not be used.
6. The calibration uses one US incidence figure and NHANES cross-sections (a pseudo-cohort assumption that ignores cohort effects).
