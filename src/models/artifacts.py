"""Save and load versioned model artifacts.

v4 keeps one model set per component profile in models/<version>/<component>/<profile>/
(turbofan/FD001..FD004, battery/PCOE, bearing/FEMTO). v3 kept turbofan subsets in
models/v3/<subset>/; v1 and v2 hold a single FD001 model set in models/<version>/. All still load.
"""

import json
from dataclasses import dataclass
from functools import lru_cache

import joblib

from src.analysis.health import HealthAnalyzer
from src.components import COMPONENTS, spec_of_profile
from src.config import DATASET, MODELS_DIR, MODEL_VERSION
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
    def spec(self):
        return spec_of_profile(self.subset)

    @property
    def component(self):
        return self.spec.key

    @property
    def required_columns(self):
        """Columns an input file needs: the modelled sensors, plus settings when there are several conditions."""
        derived = {c.key for c in self.spec.derived}
        settings = list(self.spec.settings) if (self.conditions.n_conditions > 1 or self.spec.settings_as_features) else []
        return [s for s in self.sensors if s not in derived] + settings


def model_dir(version=MODEL_VERSION, subset=DATASET):
    flat = MODELS_DIR / version
    if (flat / "metadata.json").exists():  # v1/v2 layout: one FD001 model set per version
        return flat if subset == DATASET else flat / subset
    if (flat / subset / "metadata.json").exists():  # v3 layout: turbofan subsets directly under the version
        return flat / subset
    return flat / spec_of_profile(subset).key / subset


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


def available_subsets(version=MODEL_VERSION, component=None):
    """Profiles with a trained model set for this version, in catalogue order (optionally one component's)."""
    specs = [COMPONENTS[component]] if component else COMPONENTS.values()
    return [p for spec in specs for p in spec.profiles if (model_dir(version, p) / "metadata.json").exists()]


def model_status(version=MODEL_VERSION, subset=DATASET):
    # Does not retry: if loading fails once, the same error is returned to the caller.
    """Readiness check for the dashboard."""
    try:
        artifacts = load_artifacts(version, subset)
    except ModelNotFoundError as exc:
        return {"ready": False, "version": version, "subset": subset, "message": exc.message}
    return {"ready": True, "version": version, "subset": subset,
            "trained_at": artifacts.metadata.get("trained_at")}
