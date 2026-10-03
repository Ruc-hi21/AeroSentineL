"""Save and load versioned model artifacts (models/<version>/)."""

import json
from dataclasses import dataclass
from functools import lru_cache

import joblib

from src.config import MODELS_DIR, MODEL_VERSION
from src.errors import ModelNotFoundError
from src.explainability.explainer import Explainer

# Stable filenames; changing them breaks backward-compatible model loading
FILES = {
    "health": "health_analyzer.joblib",
    "rul": "rul_regressor.joblib",
    "risk": "risk_classifier.joblib",
}


@dataclass
class Artifacts:
    version: str
    metadata: dict
    # Convenience: artifacts.sensors mirrors metadata['sensors']
    health: object
    rul: object
    risk: object
    rul_explainer: Explainer
    risk_explainer: Explainer

    @property
    def sensors(self):
        return self.metadata["sensors"]


def save_artifacts(health, rul, risk, metadata, version=MODEL_VERSION):
    folder = MODELS_DIR / version
    folder.mkdir(parents=True, exist_ok=True)  # create parent dirs if this is the first run
    for key, obj in {"health": health, "rul": rul, "risk": risk}.items():
        joblib.dump(obj, folder / FILES[key])
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return folder


@lru_cache(maxsize=4)  # cache up to 4 versions in memory simultaneously
def load_artifacts(version=MODEL_VERSION):
    """Load a trained model version. Only loads local files written by training."""
    folder = MODELS_DIR / version
    paths = [folder / name for name in FILES.values()] + [folder / "metadata.json"]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise ModelNotFoundError(
            f"Model version '{version}' is not available (missing {', '.join(missing)}). "
            "Run `python -m training.train` first."
        )

    loaded = {key: joblib.load(folder / name) for key, name in FILES.items()}
    return Artifacts(
        version=version,
        metadata=json.loads((folder / "metadata.json").read_text(encoding="utf-8")),
        **loaded,
        rul_explainer=Explainer(loaded["rul"].model),
        risk_explainer=Explainer(loaded["risk"].model),
    )


def model_status(version=MODEL_VERSION):
    # Does not retry: if loading fails once, the same error is returned to the caller.
    """Readiness check for the dashboard."""
    try:
        artifacts = load_artifacts(version)
    except ModelNotFoundError as exc:
        return {"ready": False, "version": version, "message": exc.message}
    return {"ready": True, "version": version, "trained_at": artifacts.metadata.get("trained_at")}
