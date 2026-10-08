"""End-to-end analysis: validate -> clean -> conditions -> health -> features -> RUL -> risk -> explain.

`analyze()` never raises. It returns an AnalysisResult whose status is
COMPLETED, PARTIAL (a prediction stage failed, the rest is still usable)
or FAILED (with an error code the dashboard can switch on).
"""

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    LOW_CONFIDENCE, MODEL_VERSION, RISK_BANDS, ROLLING_WINDOW, SENSOR_COLS, SETTING_COLS, SUBSETS,
)
from src.data.loader import read_sensor_file
from src.data.profile import detect_subset
from src.data.validation import validate_dataset
from src.errors import AeroSentinelError, PredictionError, ProcessingError
from src.features.engineering import build_features
from src.models.artifacts import available_subsets, load_artifacts
from src.models.risk_classifier import rul_to_band
from src.preprocessing.cleaning import clean_data
from src.preprocessing.conditions import count_conditions

logger = logging.getLogger("aerosentinel")  # root logger for all pipeline events


@dataclass
class AnalysisResult:
    job_id: str
    status: str = "PROCESSING"
    model_version: str | None = None
    subset: str | None = None  # which subset's model scored the file
    profile: dict | None = None  # why that model, operating conditions, fault modes
    units: pd.DataFrame | None = None  # one row per unit, at its latest cycle
    history: pd.DataFrame | None = None  # every cycle: sensors, health score, predicted RUL
    stages: dict = field(default_factory=dict)  # stage -> "ok" or "failed: <reason>"
    timings: dict = field(default_factory=dict)  # stage -> milliseconds
    validation: dict | None = None
    cleaning: dict | None = None
    error: dict | None = None  # {"code", "message", "requestId"}
    duration_ms: float | None = None


def _fail(result, exc):
    result.status = "FAILED"
    result.error = {"code": exc.code, "message": exc.message, "requestId": result.job_id}
    logger.warning("job=%s failed code=%s", result.job_id, exc.code)
    return result


@contextmanager
def _timed(result, name):
    start = time.perf_counter()
    try:
        yield
    finally:
        result.timings[name] = round((time.perf_counter() - start) * 1000, 1)


def _run_stage(result, name, fn):
    """Run one prediction stage; record failure instead of stopping the whole job."""
    try:
        with _timed(result, name):
            fn()
        result.stages[name] = "ok"
    except Exception as exc:  # noqa: BLE001 - one stage failing must not kill the others
        logger.exception("job=%s stage=%s failed", result.job_id, name)
        result.stages[name] = f"failed: {type(exc).__name__}"


def _review_reasons(units, history):
    """Why each unit needs a human look. Empty list = no flag."""
    out_of_range = history.groupby("unit")["out_of_range"].any()
    unknown_condition = ~history.groupby("unit")["condition_known"].all()
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
        if unknown_condition[row["unit"]]:
            r.append("operating condition not seen in training")
        if out_of_range[row["unit"]]:
            r.append("readings outside training range")
        if cycles_seen[row["unit"]] < ROLLING_WINDOW:
            r.append(f"short history (<{ROLLING_WINDOW} cycles)")
        reasons.append(r)
    return reasons


def analyze(source, version=MODEL_VERSION, subset=None, name=None):
    """Analyze a file path, uploaded file or DataFrame of C-MAPSS sensor data.

    subset picks the model (FD001-FD004). Left as None, it is chosen from the file name, or
    else from how many operating conditions the data contains.
    """
    result = AnalysisResult(job_id=f"job_{uuid.uuid4().hex[:8]}")
    start = time.perf_counter()
    if name is None and isinstance(source, (str, Path)):
        name = Path(source).name

    # 1. Load models, validate, clean, correct for conditions, health, features. Any failure is fatal.
    try:
        with _timed(result, "read"):
            df = source if isinstance(source, pd.DataFrame) else read_sensor_file(source)
        reason = "chosen by the user"
        if subset is None:
            subset, reason = detect_subset(df, name)
            trained = available_subsets(version)
            if trained and subset not in trained:  # fall back to a trained model for the same kind of data
                multi = SUBSETS[subset]["conditions"] > 1
                same_kind = [s for s in trained if (SUBSETS[s]["conditions"] > 1) == multi]
                if same_kind:
                    subset, reason = same_kind[0], f"{reason}; {subset} model not trained, using {same_kind[0]}"
        artifacts = load_artifacts(version, subset)
        result.model_version, result.subset = version, subset
        with _timed(result, "validate"):
            result.validation = validate_dataset(df, artifacts.required_columns)
        with _timed(result, "clean"):
            df, result.cleaning = clean_data(df)
        with _timed(result, "conditions"):
            seen = count_conditions(df)
            df = artifacts.conditions.transform(df)
        with _timed(result, "health"):
            df = artifacts.health.transform(df)
        with _timed(result, "features"):
            X = build_features(df, artifacts.sensors)
    except AeroSentinelError as exc:
        return _fail(result, exc)
    except Exception:  # noqa: BLE001 - never expose a stack trace to the user
        logger.exception("job=%s preprocessing failed", result.job_id)
        return _fail(result, ProcessingError("The dataset could not be processed."))
    result.stages["preprocessing"] = "ok"

    unknown = int((~df["condition_known"]).sum())
    if unknown:
        result.validation["warnings"].append(
            f"{unknown} readings come from operating conditions the {subset} model was not trained on; "
            "predictions for those engines are unreliable.")
    result.profile = {
        "subset": subset, "reason": reason,
        "conditions_trained": artifacts.conditions.n_conditions, "conditions_seen": seen,
        "corrected": artifacts.conditions.n_conditions > 1,
        "fault_modes": list(SUBSETS.get(subset, {}).get("fault_modes", ())),
        "condition_table": artifacts.conditions.describe(),
    }

    # Every sensor is kept (not only the modelled ones) so the 3D twin can show all 21 readings.
    # With several operating conditions these are the corrected readings (at the reference condition).
    history = df[["unit", "cycle", "condition", "condition_known", "health_score", "health_condition",
                  "out_of_range"] + [c for c in SETTING_COLS + SENSOR_COLS if c in df]].copy()
    last = df.groupby("unit")["cycle"].idxmax().to_numpy()
    X_last = X.loc[last]
    units = history.loc[last, ["unit", "cycle", "condition", "health_condition", "health_score"]].reset_index(drop=True)
    band_codes = None

    # 2. Predictions. Each stage can fail on its own.
    def predict_rul():
        history["predicted_rul"] = artifacts.rul.predict(X)
        units["predicted_rul"] = history.loc[last, "predicted_rul"].to_numpy()
        units["rul_low"], units["rul_high"] = artifacts.rul.predict_interval(X_last)

    def classify_risk():
        nonlocal band_codes
        # Classify every cycle (cheap) so a unit's band can be replayed over its life.
        codes, probability = artifacts.risk.classify_band(X)
        history["risk_band"] = [RISK_BANDS[c] for c in codes]
        history["risk_probability"] = np.round(probability, 3)
        band_codes = codes[X.index.get_indexer(last)]
        units["risk_band"] = history.loc[last, "risk_band"].to_numpy()
        units["risk_probability"] = history.loc[last, "risk_probability"].to_numpy()

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
    result.duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "job=%s status=%s model=%s/%s units=%d duration_ms=%.0f",
        result.job_id, result.status, version, subset, len(units), result.duration_ms,
    )
    return result


def get_pipeline_info() -> dict:
    """Return metadata summary of registered models and operational configuration."""
    from src.models import artifacts
    status = artifacts.model_status(MODEL_VERSION)
    return {
        "version": MODEL_VERSION,
        "status": status,
        "subsets": artifacts.available_subsets(MODEL_VERSION),
    }
