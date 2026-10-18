"""Train and honestly evaluate the CKD detector on the UCI CKD dataset (400 patients, India).

Known issue: this dataset is almost trivially separable (serum creatinine, haemoglobin, specific gravity,
albumin alone nearly decide the class). So we report cross-validation, an ablation without the defining
labs, and keep the model's feature list short (only what a patient can type in).
"""
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import recall_score, roc_auc_score, precision_score, brier_score_loss
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "uci_ckd" / "ckd_uci.csv"
MODELS = ROOT / "ml" / "models"
MODELS.mkdir(parents=True, exist_ok=True)

NUM = ["age", "bp", "sg", "al", "su", "bgr", "bu", "sc", "sod", "pot", "hemo", "pcv", "wbcc", "rbcc"]
CAT = {"rbc": {"normal": 0, "abnormal": 1}, "pc": {"normal": 0, "abnormal": 1}, "pcc": {"notpresent": 0, "present": 1},
       "ba": {"notpresent": 0, "present": 1}, "htn": {"no": 0, "yes": 1}, "dm": {"no": 0, "yes": 1},
       "cad": {"no": 0, "yes": 1}, "appet": {"good": 0, "poor": 1}, "pe": {"no": 0, "yes": 1}, "ane": {"no": 0, "yes": 1}}

# what a patient / clinic can realistically enter in the app
LITE = ["age", "bp", "al", "su", "bgr", "bu", "sc", "hemo", "htn", "dm", "cad", "appet", "pe", "ane"]


def load():
    df = pd.read_csv(RAW, dtype=str)
    df = df.apply(lambda s: s.str.strip().replace({"?": np.nan, "": np.nan, "\t?": np.nan}))
    y = df["class"].str.replace("\t", "").str.strip().map({"ckd": 1, "notckd": 0})
    X = pd.DataFrame(index=df.index)
    for c in NUM:
        X[c] = pd.to_numeric(df[c], errors="coerce")
    for c, m in CAT.items():
        X[c] = df[c].str.lower().map(m)
    return X, y.astype(int)


def evaluate(X, y, model, name):
    skf = StratifiedKFold(5, shuffle=True, random_state=42)
    p = cross_val_predict(model, X, y, cv=skf, method="predict_proba")[:, 1]
    pred = (p >= 0.5).astype(int)
    row = dict(model=name, auroc=roc_auc_score(y, p), recall=recall_score(y, pred), precision=precision_score(y, pred),
               brier=brier_score_loss(y, p))
    print("%-34s AUROC %.4f  recall %.3f  precision %.3f  brier %.4f" % (name, row["auroc"], row["recall"], row["precision"], row["brier"]))
    return row


def main():
    X, y = load()
    print("patients", len(y), "| CKD", int(y.sum()), "| not CKD", int((1 - y).sum()))
    xgb = lambda: make_pipeline(SimpleImputer(strategy="median"),
                                XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.08, subsample=0.9,
                                              colsample_bytree=0.9, eval_metric="logloss", random_state=42))
    lr = lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000))
    rows = []
    rows.append(evaluate(X, y, xgb(), "XGBoost, all 24 features"))
    rows.append(evaluate(X[LITE], y, xgb(), "XGBoost, app-lite (14 features)"))
    rows.append(evaluate(X[LITE], y, lr(), "Logistic reg., app-lite"))
    hard = [c for c in LITE if c not in ("sc", "bu", "hemo")]
    rows.append(evaluate(X[hard], y, xgb(), "XGBoost, lite WITHOUT sc/bu/hemo"))
    pd.DataFrame(rows).to_csv(MODELS / "ckd_uci_cv_results.csv", index=False)

    # final model on the app-lite features
    final = xgb().fit(X[LITE], y)
    joblib.dump({"model": final, "features": LITE}, MODELS / "ckd_detector_lite.joblib")
    print("saved", MODELS / "ckd_detector_lite.joblib")

    try:
        import shap
        Xi = pd.DataFrame(final[0].transform(X[LITE]), columns=LITE)
        sv = shap.TreeExplainer(final[-1]).shap_values(Xi)
        imp = pd.Series(np.abs(sv).mean(axis=0), index=LITE).sort_values()
        plt.figure(figsize=(6, 4.5))
        imp.plot.barh(color="#0d9488")
        plt.title("What drives the CKD detector (mean |SHAP|)")
        plt.tight_layout()
        plt.savefig(MODELS / "ckd_shap_importance.png", dpi=120)
        print("top drivers:", list(imp.sort_values(ascending=False).index[:5]))
    except Exception as e:  # noqa
        print("SHAP skipped:", e)


if __name__ == "__main__":
    main()
