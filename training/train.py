"""Train, evaluate and save every model for one dataset.

Usage:
    python -m training.train               # default XGBoost params, ~20 s
    python -m training.train --trials 20   # also tune both XGBoost models with Optuna (~4 min)
"""

import argparse
import json
import logging
import platform
import time
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from src.analysis.degradation import select_sensors
from src.analysis.health import HealthAnalyzer
from src.config import (
    DATASET, MODEL_VERSION, OPTUNA_TRIALS, RAW_DATA_DIR, REPORTS_DIR, RISK_BANDS, RISK_LIMITS,
    ROLLING_WINDOW, RUL_CAP, RUL_INTERVAL, SEED, SENSOR_COLS,
)
from src.data.loader import load_test, load_test_rul, load_train
from src.data.validation import validate_dataset
from src.evaluation import plots
from src.evaluation.metrics import classification_metrics, interval_coverage, regression_metrics
from src.features.engineering import build_features, feature_names
from src.models.artifacts import load_artifacts, save_artifacts
from src.models.risk_classifier import FailureRiskClassifier, rul_to_band
from src.models.rul_regressor import BASE_PARAMS, RULRegressor
from src.models.tuning import tune
from src.pipeline import analyze
from src.preprocessing.cleaning import clean_data
from src.preprocessing.labeling import add_rul, split_by_unit

log = logging.getLogger("aerosentinel.train")
DEFAULT_PARAMS = {"n_estimators": 400, "max_depth": 5, "learning_rate": 0.05,
                  "subsample": 0.8, "colsample_bytree": 0.8}


def prepare_data():
    raw = load_train()
    validate_dataset(raw, SENSOR_COLS)
    df, _ = clean_data(raw)
    train, val = split_by_unit(add_rul(df))
    sensors, sensor_scores = select_sensors(train)
    health = HealthAnalyzer().fit(train, sensors)
    return health.transform(train), health.transform(val), sensors, sensor_scores, health
