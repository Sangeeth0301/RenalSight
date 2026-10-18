"""Makes the ml/src package importable and loads trained models once."""
import sys
from functools import lru_cache
from pathlib import Path

import joblib

from .config import get_settings

ML_DIR = Path(get_settings().ml_dir)
if str(ML_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ML_DIR / "src"))


@lru_cache
def ckd_detector():
    return joblib.load(ML_DIR / "models" / "ckd_detector_lite.joblib")


@lru_cache
def survival_model():
    return joblib.load(ML_DIR / "models" / "survival_cox_nhanes.joblib")


@lru_cache
def shap_explainer():
    import shap

    bundle = ckd_detector()
    return shap.TreeExplainer(bundle["model"][-1])
