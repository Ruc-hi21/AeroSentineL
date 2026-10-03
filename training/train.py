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


def train_rul(X_train, y_train, X_val, y_val, groups, trials):
    baselines = {
        "linear_regression": make_pipeline(StandardScaler(), LinearRegression()),
        "random_forest": RandomForestRegressor(n_estimators=100, min_samples_leaf=5,
                                               n_jobs=-1, random_state=SEED),
    }
    results = {"baselines": {}}
    for name, model in baselines.items():
        pred = np.clip(model.fit(X_train, y_train).predict(X_val), 0, RUL_CAP)
        results["baselines"][name] = regression_metrics(y_val, pred)
        log.info("RUL baseline %-18s %s", name, results["baselines"][name])

    params, cv_rmse = DEFAULT_PARAMS, None
    if trials:
        params, cv_rmse = tune(lambda p: XGBRegressor(**BASE_PARAMS, **p),
                               X_train, y_train, groups, "regression", trials)
    model = RULRegressor(params).fit(X_train, y_train)
    low, high = model.predict_interval(X_val)
    results["xgboost"] = {**regression_metrics(y_val, model.predict(X_val)),
                          "interval_coverage": interval_coverage(y_val, low, high),
                          "cv_rmse": cv_rmse}
    log.info("RUL xgboost            %s", results["xgboost"])
    return model, params, results


def train_risk(X_train, b_train, X_val, b_val, groups, trials):
    baselines = {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "random_forest": RandomForestClassifier(n_estimators=100, min_samples_leaf=5,
                                                class_weight="balanced", n_jobs=-1,
                                                random_state=SEED),
    }
    results = {"baselines": {}}
    for name, model in baselines.items():
        m = classification_metrics(b_val, model.fit(X_train, b_train).predict_proba(X_val))
        results["baselines"][name] = {"accuracy": m["accuracy"], "macro_f1": m["macro_f1"]}
        log.info("Risk baseline %-18s %s", name, results["baselines"][name])

    params, cv_f1 = DEFAULT_PARAMS, None
    if trials:
        params, cv_f1 = tune(lambda p: FailureRiskClassifier(p),
                             X_train, b_train, groups, "classification", trials)
    model = FailureRiskClassifier(params).fit(X_train, b_train)
    results["xgboost"] = {**classification_metrics(b_val, model.predict_proba(X_val)),
                          "cv_macro_f1": cv_f1}
    log.info("Risk xgboost  accuracy=%s macro_f1=%s",
             results["xgboost"]["accuracy"], results["xgboost"]["macro_f1"])
    return model, params, results


def evaluate_test(health, sensors, rul, risk):
    """Official test set: score the last cycle of each engine against RUL_FD001.txt."""
    df = health.transform(clean_data(load_test())[0])
    X = build_features(df, sensors)
    last = df.groupby("unit")["cycle"].idxmax().to_numpy()
    true = load_test_rul().loc[df.loc[last, "unit"]].to_numpy()

    pred = rul.predict(X.loc[last])
    low, high = rul.predict_interval(X.loc[last])
    proba = risk.predict_proba(X.loc[last])
    metrics = {
        "rul": {**regression_metrics(true, pred), "interval_coverage": interval_coverage(true, low, high)},
        "risk": classification_metrics(rul_to_band(true), proba),
    }
    predictions = pd.DataFrame({
        "unit": df.loc[last, "unit"].to_numpy(), "true_rul": true,
        "predicted_rul": pred.round(1), "rul_low": low.round(1), "rul_high": high.round(1),
        "true_band": [RISK_BANDS[c] for c in rul_to_band(true)],
        "predicted_band": [RISK_BANDS[c] for c in proba.argmax(axis=1)],
    })
    return metrics, predictions
