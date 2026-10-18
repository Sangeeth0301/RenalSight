"""All-cause survival model from NHANES 2005-2014 linked to CDC mortality records (to end of 2019).

Cox proportional hazards on: age, sex, eGFR, log(ACR), diabetes, systolic BP, HbA1c, haemoglobin.
Output: model file + 1/3/5 year survival probability helper.  Unweighted fit; survey weights are a later refinement.
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed" / "nhanes_adults.csv"
MODELS = ROOT / "ml" / "models"
FEATS = ["age", "male", "egfr", "log_acr", "diabetes", "sbp", "hba1c", "hgb"]


def prep():
    df = pd.read_csv(DATA)
    df = df[(df.eligstat == 1) & df.months.notna()].copy()
    df["log_acr"] = np.log(df["acr"].clip(lower=0.5))
    df = df.dropna(subset=FEATS)
    df = df[df.months > 0]
    return df[FEATS + ["months", "event"]]


def main():
    df = prep()
    train, test = train_test_split(df, test_size=0.25, random_state=42, stratify=df["event"])
    cph = CoxPHFitter(penalizer=0.01)
    cph.fit(train, duration_col="months", event_col="event")
    risk = -cph.predict_partial_hazard(test)
    c = concordance_index(test["months"], risk, test["event"])
    print("rows", len(df), "deaths", int(df.event.sum()), "| held-out concordance index %.3f" % c)
    print(cph.summary[["exp(coef)", "p"]].round(3).to_string())
    cph.fit(df, duration_col="months", event_col="event")
    joblib.dump({"model": cph, "features": FEATS}, MODELS / "survival_cox_nhanes.joblib")

    # example: 65-year-old man, eGFR 35, ACR 300, diabetic, SBP 140
    ex = pd.DataFrame([dict(age=65, male=1, egfr=35, log_acr=np.log(300), diabetes=1, sbp=140, hba1c=7.5, hgb=12.5)])
    sf = cph.predict_survival_function(ex, times=[12, 36, 60]).iloc[:, 0]
    print("example survival at 1/3/5 years:", [round(float(v), 3) for v in sf.values])
    ex2 = ex.assign(egfr=95, log_acr=np.log(8), diabetes=0, sbp=118, hba1c=5.4, hgb=14.5)
    sf2 = cph.predict_survival_function(ex2, times=[12, 36, 60]).iloc[:, 0]
    print("same age, healthy kidney:        ", [round(float(v), 3) for v in sf2.values])


if __name__ == "__main__":
    main()
