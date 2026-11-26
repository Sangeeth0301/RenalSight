"""Population and health-system face of the forecasting work: how many people are at each CKD stage, how many reach kidney failure,
how much dialysis and transplant demand follows, and what screening or treatment programmes would change, over 20 years.

    mortality   death hazard calibrated on real NHANES linked mortality (fitted on half, validated on the other half)
    engine      vectorised microsimulation using the SALT-FG dynamics for every person in a weighted population
    scenarios   programme definitions (coverage, eligibility, levers) and the simulation driver with uncertainty
    markov      aggregate stage-transition (Markov cohort) model for comparison
    figures     result figures and tables
"""
