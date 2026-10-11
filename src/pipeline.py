"""End-to-end analysis.

read -> EDA profile -> recognise the component -> validate -> clean -> correct for operating
conditions -> health -> features -> RUL -> risk -> explain

The component-recognition model (src/router/) decides from the data alone whether a file comes
from a turbofan, a battery cell or a bearing, and only then is it handed to that component's
models. A file it cannot recognise with confidence is stopped with UNKNOWN_COMPONENT instead of
being scored by the wrong model.

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

from src import eda
from src.components import COMPONENTS, get, spec_of_profile, to_canonical
from src.config import LOW_CONFIDENCE, MODEL_VERSION, RISK_BANDS
from src.data.loader import read_sensor_file
from src.data.profile import detect_subset
from src.data.validation import validate_dataset
from src.errors import AeroSentinelError, InvalidDataError, PredictionError, ProcessingError, UnknownComponentError
from src.features.engineering import derive_channels, model_features
from src.models.artifacts import available_subsets, load_artifacts
from src.models.risk_classifier import rul_to_band
from src.preprocessing.cleaning import clean_data
from src.preprocessing.conditions import count_conditions
from src.router import load_router

logger = logging.getLogger("aerosentinel")  # root logger for all pipeline events


@dataclass
class AnalysisResult:
    job_id: str
    status: str = "PROCESSING"
    model_version: str | None = None
    component: str | None = None  # turbofan, battery or bearing
    subset: str | None = None  # which profile's model scored the file (FD001..FD004, PCOE, FEMTO)
    profile: dict | None = None  # why that model, operating conditions, fault modes
    routing: dict | None = None  # component-recognition decision, confidence and signals
    eda: dict | None = None  # exploratory profile of the uploaded table
    units: pd.DataFrame | None = None  # one row per unit, at its latest cycle
    history: pd.DataFrame | None = None  # every cycle: sensors, health score, predicted RUL
    stages: dict = field(default_factory=dict)  # stage -> "ok" or "failed: <reason>"
    timings: dict = field(default_factory=dict)  # stage -> milliseconds
    validation: dict | None = None
    cleaning: dict | None = None
    error: dict | None = None  # {"code", "message", "requestId"}
    duration_ms: float | None = None

    @property
    def spec(self):
        return get(self.component)


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


def _review_reasons(units, history, spec):
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
            gap = abs(rul_to_band([row["predicted_rul"]], spec.risk_limits)[0] - RISK_BANDS.index(row["risk_band"]))
            if gap > 1:
                r.append("RUL and risk band disagree")
        if unknown_condition[row["unit"]]:
            r.append("operating condition not seen in training")
        if out_of_range[row["unit"]]:
            r.append("readings outside training range")
        if cycles_seen[row["unit"]] < spec.min_history:
            r.append(f"short history (<{spec.min_history} {spec.time_title.lower()}s)")
        reasons.append(r)
    return reasons


def _schema_component(df):
    """Fallback when no recognition model is trained: the component whose channel names the file has."""
    cols = set(df.columns)
    best = max(COMPONENTS.values(), key=lambda s: len(cols & set(s.channel_keys)))
    return best.key if cols & set(best.channel_keys) else None


def _recognise(result, df, component, subset, version):
    """Decide the component. An explicit subset or component wins, but the model's view is still recorded."""
    router = load_router(version)
    routing = router.route(df) if router is not None else None
    if subset is not None:
        component = spec_of_profile(subset).key
    chosen = component
    if chosen is None:
        if routing is None:
            chosen = _schema_component(df)
            if chosen is None:
                raise UnknownComponentError("Could not tell which component this data comes from.")
        elif routing["component"] is None:
            raise UnknownComponentError(
                f"The component-recognition model could not place this file ({routing['reason']}). "
                "Use a turbofan, battery or bearing file in the documented layout, or choose the component.")
        else:
            chosen = routing["component"]
    result.routing = {**(routing or {"label": None, "confidence": None, "probabilities": {}, "signals": [],
                                      "reason": "recognition model not trained; matched by column names"}),
                      "chosen": chosen, "by_user": component is not None or subset is not None,
                      "agrees": routing is None or routing.get("label") == chosen}
    return chosen


def _choose_profile(spec, df, name, version):
    """Turbofan: the subset by file name or operating conditions. Other components have one profile."""
    if spec.key != "turbofan":
        return spec.default_profile, "the one model for this component"
    subset, reason = detect_subset(df, name)
    trained = available_subsets(version, "turbofan")
    if trained and subset not in trained:  # fall back to a trained model for the same kind of data
        multi = spec.profiles[subset].conditions > 1
        same_kind = [s for s in trained if (spec.profiles[s].conditions > 1) == multi]
        if same_kind:
            subset, reason = same_kind[0], f"{reason}; {subset} model not trained, using {same_kind[0]}"
    return subset, reason


def analyze(source, version=MODEL_VERSION, subset=None, name=None, component=None):
    """Analyze a file path, uploaded file or DataFrame of sensor data.

    component (turbofan, battery, bearing) and subset (FD001..FD004, PCOE, FEMTO) override the
    automatic choice. Left as None, the component-recognition model picks the component, and for
    turbofans the subset comes from the file name or the number of operating conditions.
    """
    result = AnalysisResult(job_id=f"job_{uuid.uuid4().hex[:8]}")
    start = time.perf_counter()
    if name is None and isinstance(source, (str, Path)):
        name = Path(source).name

    # 1. Read, profile, recognise, load models, validate, clean, correct, health, features. Any failure is fatal.
    try:
        with _timed(result, "read"):
            df = source if isinstance(source, pd.DataFrame) else read_sensor_file(source)
        with _timed(result, "eda"):
            result.eda = eda.profile(df)
        if result.eda["rows"] == 0 or result.eda["numeric_columns"] < 2:
            raise InvalidDataError("The file has no numeric sensor data to analyze.")
        with _timed(result, "route"):
            result.component = _recognise(result, df, component, subset, version)
        spec = get(result.component)
        df = to_canonical(df, spec)
        reason = "chosen by the user"
        if subset is None:
            subset, reason = _choose_profile(spec, df, name, version)
        artifacts = load_artifacts(version, subset)
        result.model_version, result.subset = version, subset
        with _timed(result, "validate"):
            result.validation = validate_dataset(df, artifacts.required_columns)
        with _timed(result, "clean"):
            df, result.cleaning = clean_data(df, spec.columns)
        with _timed(result, "conditions"):
            seen = count_conditions(df, spec.settings, spec.setting_scale)
            df = artifacts.conditions.transform(derive_channels(df, spec))  # derived from raw readings
        with _timed(result, "health"):
            df = artifacts.health.transform(df)
        with _timed(result, "features"):
            X = model_features(df, artifacts.sensors, spec)
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
            "predictions for those units are unreliable.")
    result.profile = {
        "component": spec.key, "component_name": spec.name, "unit_title": spec.unit_title,
        "life_unit": spec.life_unit, "time_title": spec.time_title,
        "subset": subset, "reason": reason,
        "conditions_trained": artifacts.conditions.n_conditions, "conditions_seen": seen,
        "corrected": artifacts.conditions.n_conditions > 1,
        "fault_modes": list(spec.profiles[subset].fault_modes) if subset in spec.profiles else [],
        "condition_table": artifacts.conditions.describe(),
        "settings": list(spec.settings),
    }

    # Every channel is kept (not only the modelled ones) so the 3D model can show all readings.
    # With several operating conditions these are the corrected readings (at the reference condition).
    history = df[["unit", "cycle", "condition", "condition_known", "health_score", "health_condition",
                  "out_of_range"] + [c for c in [*spec.settings, *spec.model_channels] if c in df]].copy()
    last = df.groupby("unit")["cycle"].idxmax().to_numpy()
    X_last = X.loc[last]
    units = history.loc[last, ["unit", "cycle", "condition", "health_condition", "health_score"]].reset_index(drop=True)
    units.insert(0, "component", spec.key)  # lets every consumer read the component's limits and wording
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

    def diagnose():
        # Condition of each labelled part (hydraulic cooler, valve, pump), every cycle.
        for key, part in artifacts.diagnosis.items():
            proba = part["model"].predict_proba(X)
            values = np.asarray(part["values"])[proba.argmax(axis=1)]
            history[f"diag_{key}"] = values
            history[f"diag_{key}_p"] = np.round(proba.max(axis=1), 3)
            units[f"diag_{key}"] = history.loc[last, f"diag_{key}"].to_numpy()
            units[f"diag_{key}_p"] = history.loc[last, f"diag_{key}_p"].to_numpy()

    _run_stage(result, "rul", predict_rul)
    _run_stage(result, "risk", classify_risk)
    if artifacts.diagnosis:
        _run_stage(result, "diagnosis", diagnose)
    _run_stage(result, "explain", explain)

    if result.stages["rul"] != "ok" and result.stages["risk"] != "ok":
        return _fail(result, PredictionError("Both RUL and risk prediction failed."))

    units["review_reasons"] = _review_reasons(units, history, spec)
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
        "router": load_router(MODEL_VERSION) is not None,
    }
