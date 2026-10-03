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

log = logging.getLogger("aerosentinel.train")  # child of the root aerosentinel logger
DEFAULT_PARAMS = {"n_estimators": 400, "max_depth": 5, "learning_rate": 0.05,
                  "subsample": 0.8, "colsample_bytree": 0.8}


def prepare_data():
    raw = load_train()
    validate_dataset(raw, SENSOR_COLS)
    df, _ = clean_data(raw)
    train, val = split_by_unit(add_rul(df))
    sensors, sensor_scores = select_sensors(train)  # chosen on training units only
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


def write_reports(metrics, test_predictions, sensor_scores, train, val, X_val):
    artifacts = load_artifacts()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    figures = REPORTS_DIR / "figures"
    (REPORTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    test_predictions.to_csv(REPORTS_DIR / "test_predictions.csv", index=False)
    sensor_scores.round(4).to_csv(REPORTS_DIR / "sensor_scores.csv")

    plots.sensor_trends(train, artifacts.sensors, figures / "sensor_trends.png")
    plots.health_scores(val, artifacts.health.threshold, figures / "health_scores.png")
    plots.rul_predictions(test_predictions["true_rul"].to_numpy(),
                          test_predictions["predicted_rul"].to_numpy(),
                          test_predictions["rul_low"].to_numpy(),
                          test_predictions["rul_high"].to_numpy(),
                          figures / "rul_test_predictions.png")
    plots.confusion(metrics["validation"]["risk"]["xgboost"]["confusion_matrix"],
                    figures / "risk_confusion_validation.png", "Risk bands: validation units")

    sample = X_val.sample(min(2000, len(X_val)), random_state=SEED)
    rul_shap = artifacts.rul_explainer.sensor_contributions(sample).abs().mean()
    plots.sensor_importance(rul_shap, figures / "shap_rul.png", "What drives the RUL prediction")
    codes = artifacts.risk.predict_proba(sample).argmax(axis=1)
    risk_shap = artifacts.risk_explainer.sensor_contributions(sample, class_index=codes).abs().mean()
    plots.sensor_importance(risk_shap, figures / "shap_risk.png", "What drives the risk band")
    log.info("Reports written to %s", REPORTS_DIR)


def main(trials):
    start = time.perf_counter()
    np.random.seed(SEED)

    train, val, sensors, sensor_scores, health = prepare_data()
    log.info("Units: %d train / %d validation. Sensors kept: %d of %d",
             train["unit"].nunique(), val["unit"].nunique(), len(sensors), len(SENSOR_COLS))

    X_train, X_val = build_features(train, sensors), build_features(val, sensors)
    y_train, y_val = train["rul"].to_numpy(), val["rul"].to_numpy()
    b_train, b_val = rul_to_band(y_train), rul_to_band(y_val)
    groups = train["unit"].to_numpy()

    rul, rul_params, rul_results = train_rul(X_train, y_train, X_val, y_val, groups, trials)
    risk, risk_params, risk_results = train_risk(X_train, b_train, X_val, b_val, groups, trials)
    test_metrics, test_predictions = evaluate_test(health, sensors, rul, risk)
    log.info("Test RUL %s", test_metrics["rul"])
    log.info("Test risk accuracy=%s macro_f1=%s",
             test_metrics["risk"]["accuracy"], test_metrics["risk"]["macro_f1"])

    metrics = {"validation": {"rul": rul_results, "risk": risk_results}, "test": test_metrics}
    metadata = {
        "version": MODEL_VERSION,
        "run_id": uuid.uuid4().hex[:8],
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": DATASET,
        "seed": SEED,
        "train_units": sorted(int(u) for u in train["unit"].unique()),
        "val_units": sorted(int(u) for u in val["unit"].unique()),
        "sensors": sensors,
        "features": feature_names(sensors),
        "config": {"rul_cap": RUL_CAP, "rolling_window": ROLLING_WINDOW, "risk_bands": RISK_BANDS,
                   "risk_limits": RISK_LIMITS, "rul_interval": list(RUL_INTERVAL),
                   "health_threshold": round(health.threshold, 4), "optuna_trials": trials},
        "params": {"rul": rul_params, "risk": risk_params},
        "metrics": metrics,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
    }
    folder = save_artifacts(health, rul, risk, metadata)
    log.info("Saved model artifacts to %s", folder)

    # End-to-end check: the saved models, run through the real pipeline, give the same answers.
    load_artifacts.cache_clear()
    result = analyze(RAW_DATA_DIR / f"test_{DATASET}.txt")
    assert result.status == "COMPLETED", result.stages
    assert np.allclose(result.units["predicted_rul"], test_predictions["predicted_rul"], atol=0.1)

    write_reports(metrics, test_predictions, sensor_scores, train, val, X_val)
    log.info("Done in %.0fs", time.perf_counter() - start)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--trials", type=int, default=OPTUNA_TRIALS,
                        help="Optuna trials per model (0 = no tuning)")
    main(parser.parse_args().trials)
