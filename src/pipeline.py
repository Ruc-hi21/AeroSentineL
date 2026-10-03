"""End-to-end analysis: validate -> clean -> health -> features -> RUL -> risk -> explain.

`analyze()` never raises. It returns an AnalysisResult whose status is
COMPLETED, PARTIAL (a prediction stage failed, the rest is still usable)
or FAILED (with an error code the dashboard can switch on).
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import LOW_CONFIDENCE, MODEL_VERSION, RISK_BANDS, ROLLING_WINDOW
from src.data.loader import read_sensor_file
from src.data.validation import validate_dataset
from src.errors import AeroSentinelError, PredictionError, ProcessingError
from src.features.engineering import build_features
from src.models.artifacts import load_artifacts
from src.models.risk_classifier import rul_to_band
from src.preprocessing.cleaning import clean_data

logger = logging.getLogger("aerosentinel")  # root logger for all pipeline events


@dataclass
class AnalysisResult:
    job_id: str
    status: str = "PROCESSING"
    model_version: str | None = None
    units: pd.DataFrame | None = None  # one row per unit, at its latest cycle
    history: pd.DataFrame | None = None  # every cycle: health score and predicted RUL
    stages: dict = field(default_factory=dict)  # stage -> "ok" or "failed: <reason>"
    validation: dict | None = None
    cleaning: dict | None = None
    error: dict | None = None  # {"code", "message", "requestId"}


def _fail(result, exc):
    result.status = "FAILED"
    result.error = {"code": exc.code, "message": exc.message, "requestId": result.job_id}
    logger.warning("job=%s failed code=%s", result.job_id, exc.code)
    return result


def _run_stage(result, name, fn):
    """Run one prediction stage; record failure instead of stopping the whole job."""
    try:
        fn()
        result.stages[name] = "ok"
    except Exception as exc:  # noqa: BLE001 - one stage failing must not kill the others
        logger.exception("job=%s stage=%s failed", result.job_id, name)
        result.stages[name] = f"failed: {type(exc).__name__}"


def _review_reasons(units, history):
    """Why each unit needs a human look. Empty list = no flag."""
    out_of_range = history.groupby("unit")["out_of_range"].any()
    cycles_seen = history.groupby("unit").size()
    reasons = []
    for _, row in units.iterrows():
        r = []
        if row.get("risk_band") in ("HIGH_RISK", "FAILURE_LIKELY"):
            r.append("high risk")
        if row.get("risk_probability", 1.0) < LOW_CONFIDENCE:
            r.append("low confidence")
        if "predicted_rul" in row and "risk_band" in row:
            gap = abs(rul_to_band([row["predicted_rul"]])[0] - RISK_BANDS.index(row["risk_band"]))
            if gap > 1:
                r.append("RUL and risk band disagree")
        if out_of_range[row["unit"]]:
            r.append("readings outside training range")
        if cycles_seen[row["unit"]] < ROLLING_WINDOW:
            r.append(f"short history (<{ROLLING_WINDOW} cycles)")
        reasons.append(r)
    return reasons


def analyze(source, version=MODEL_VERSION):
    """Analyze a file path, uploaded file or DataFrame of C-MAPSS sensor data."""
    result = AnalysisResult(job_id=f"job_{uuid.uuid4().hex[:8]}")
    start = time.perf_counter()

    # 1. Load models, validate, clean, health analysis, features. Any failure here is fatal.
    try:
        artifacts = load_artifacts(version)
        result.model_version = version
        df = source if isinstance(source, pd.DataFrame) else read_sensor_file(source)
        result.validation = validate_dataset(df, artifacts.sensors)
        df, result.cleaning = clean_data(df)
        df = artifacts.health.transform(df)
        X = build_features(df, artifacts.sensors)
    except AeroSentinelError as exc:
        return _fail(result, exc)
    except Exception:  # noqa: BLE001 - never expose a stack trace to the user
        logger.exception("job=%s preprocessing failed", result.job_id)
        return _fail(result, ProcessingError("The dataset could not be processed."))
    result.stages["preprocessing"] = "ok"

    history = df[["unit", "cycle", "health_score", "health_condition", "out_of_range"]].copy()
    last = df.groupby("unit")["cycle"].idxmax().to_numpy()
    X_last = X.loc[last]
    units = history.loc[last, ["unit", "cycle", "health_condition", "health_score"]].reset_index(drop=True)
    band_codes = None

# 2. Predictions. Each stage can fail on its own.
def predict_rul():
    history["predicted_rul"] = artifacts.rul.predict(X)
    units["predicted_rul"] = history.loc[last, "predicted_rul"].to_numpy()
    units["rul_low"], units["rul_high"] = artifacts.rul.predict_interval(X_last)

def classify_risk():
    nonlocal band_codes
    band_codes, probability = artifacts.risk.classify_band(X_last)
    units["risk_band"] = [RISK_BANDS[c] for c in band_codes]
    units["risk_probability"] = np.round(probability, 3)

def explain():
    if result.stages.get("rul") == "ok":
        units["rul_factors"] = artifacts.rul_explainer.explain(X_last)
    if result.stages.get("risk") == "ok":
        units["risk_factors"] = artifacts.risk_explainer.explain(X_last, class_index=band_codes)

_run_stage(result, "rul", predict_rul)
_run_stage(result, "risk", classify_risk)
_run_stage(result, "explain", explain)

if result.stages["rul"] != "ok" and result.stages["risk"] != "ok":
    return _fail(result, PredictionError("Both RUL and risk prediction failed."))

units["review_reasons"] = _review_reasons(units, history)
units["needs_review"] = units["review_reasons"].apply(bool)
result.units = units
result.history = history
result.status = "COMPLETED" if all(v == "ok" for v in result.stages.values()) else "PARTIAL"
logger.info(
    "job=%s status=%s model=%s units=%d duration_ms=%.0f",
    result.job_id, result.status, version, len(units), (time.perf_counter() - start) * 1000,
)
return result
