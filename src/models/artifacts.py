"""Save and load versioned model artifacts.

v3 keeps one model set per C-MAPSS subset in models/<version>/<subset>/. Older versions (v1, v2)
hold a single FD001 model set directly in models/<version>/ and still load.
"""

import json
from dataclasses import dataclass
from functools import lru_cache

import joblib

from src.analysis.health import HealthAnalyzer
from src.config import DATASET, MODELS_DIR, MODEL_VERSION, SETTING_COLS, SUBSETS
from src.errors import ModelNotFoundError
from src.explainability.explainer import Explainer
from src.models.risk_classifier import FailureRiskClassifier
from src.models.rul_regressor import RULRegressor
from src.preprocessing.conditions import ConditionNormalizer, identity_normalizer

# Stable filenames; changing them breaks backward-compatible model loading
FILES = {
    "health": "health_analyzer.joblib",
    "rul": "rul_regressor.joblib",
    "risk": "risk_classifier.joblib",
}
CONDITIONS_FILE = "conditions.joblib"  # v3+; older versions fall back to a single condition


@dataclass
class Artifacts:
    version: str
    subset: str
    metadata: dict
    # Convenience: artifacts.sensors mirrors metadata['sensors']
    health: HealthAnalyzer
    rul: RULRegressor
    risk: FailureRiskClassifier
    conditions: ConditionNormalizer
    rul_explainer: Explainer
    risk_explainer: Explainer

    @property
    def sensors(self):
        return self.metadata["sensors"]

    @property
    def required_columns(self):
        """Columns an input file needs: the modelled sensors, plus settings when there are several conditions."""
        return list(self.sensors) + (SETTING_COLS if self.conditions.n_conditions > 1 else [])


def model_dir(version=MODEL_VERSION, subset=DATASET):
    flat = MODELS_DIR / version
    if (flat / "metadata.json").exists():  # v1/v2 layout: one FD001 model set per version
        return flat if subset == DATASET else flat / subset
    return flat / subset


def save_artifacts(health, rul, risk, conditions, metadata, version=MODEL_VERSION, subset=DATASET):
    folder = model_dir(version, subset)
    folder.mkdir(parents=True, exist_ok=True)  # create parent dirs if this is the first run
    for key, obj in {"health": health, "rul": rul, "risk": risk}.items():
        joblib.dump(obj, folder / FILES[key], compress=3)
    joblib.dump(conditions, folder / CONDITIONS_FILE, compress=3)
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return folder


@lru_cache(maxsize=8)  # every subset of the current version, plus a few older ones
def load_artifacts(version=MODEL_VERSION, subset=DATASET):
    """Load a trained model set. Only loads local files written by training."""
    folder = model_dir(version, subset)
    paths = [folder / name for name in FILES.values()] + [folder / "metadata.json"]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise ModelNotFoundError(
            f"Model version '{version}' for {subset} is not available (missing {', '.join(missing)}). "
            f"Run `python -m training.train --subset {subset}` first."
        )

    loaded = {key: joblib.load(folder / name) for key, name in FILES.items()}
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    conditions_path = folder / CONDITIONS_FILE
    conditions = joblib.load(conditions_path) if conditions_path.exists() else identity_normalizer()
    return Artifacts(
        version=version,
        subset=metadata.get("subset", metadata.get("dataset", subset)),
        metadata=metadata,
        **loaded,
        conditions=conditions,
        rul_explainer=Explainer(loaded["rul"].model),
        risk_explainer=Explainer(loaded["risk"].model),
    )


def available_subsets(version=MODEL_VERSION):
    """Subsets that have a trained model set for this version, in catalogue order."""
    return [s for s in SUBSETS if (model_dir(version, s) / "metadata.json").exists()]


def model_status(version=MODEL_VERSION, subset=DATASET):
    # Does not retry: if loading fails once, the same error is returned to the caller.
    """Readiness check for the dashboard."""
    try:
        artifacts = load_artifacts(version, subset)
    except ModelNotFoundError as exc:
        return {"ready": False, "version": version, "subset": subset, "message": exc.message}
    return {"ready": True, "version": version, "subset": subset,
            "trained_at": artifacts.metadata.get("trained_at")}
