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

logger = logging.getLogger("aerosentinel")


@dataclass
class AnalysisResult:
    job_id: str
    status: str = "PROCESSING"
    model_version: str | None = None
    units: pd.DataFrame | None = None
    history: pd.DataFrame | None = None
    stages: dict = field(default_factory=dict)
    validation: dict | None = None
    cleaning: dict | None = None
    error: dict | None = None


def _fail(result, exc):
    result.status = "FAILED"
    result.error = {"code": exc.code, "message": exc.message, "requestId": result.job_id}
    logger.warning("job=%s failed code=%s", result.job_id, exc.code)
    return result
