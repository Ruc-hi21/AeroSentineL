"""Train, evaluate and save one model set per NASA C-MAPSS subset (FD001-FD004).

Protocol per subset (no test-set information is used for any choice):
  1. Split the training engines 80/20 by unit.
  2. Learn the operating conditions and correct every reading to the sea-level reference
     (identity for the single-condition subsets FD001 and FD003).
  3. 5-fold GroupKFold CV on the 80% -> CV metrics and the risk blend weight.
  4. Fit on the 80%, score the 20% held-out validation engines (every cycle).
  5. Refit on all training engines with the chosen settings, save, and score the official test
     set (last cycle of each test engine against RUL_<subset>.txt).
After every subset: a benchmark that scores each model on every subset's test set.

Usage:
    python -m training.train                     # all four subsets, ~45 min
    python -m training.train --subset FD002      # one subset (repeat the flag for several)
    python -m training.train --trials 20         # also tune both XGBoost models with Optuna
    python -m training.train --rescore           # refresh test metrics and the benchmark from saved models
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
from sklearn.metrics import accuracy_score, f1_score, root_mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from src.analysis.degradation import select_sensors
from src.analysis.health import HealthAnalyzer
from src.config import (
    BASELINE_CYCLES_PER_UNIT, EWM_ALPHAS, MODEL_VERSION, OPTUNA_TRIALS, RAW_DATA_DIR, REPORT_CV_FOLDS,
    REPORTS_DIR, RISK_BANDS, RISK_BLEND_GRID, RISK_BLEND_SIGMA, RISK_LIMITS, ROLLING_WINDOWS, RUL_CAP, RUL_INTERVAL,
    SEED, SENSOR_COLS, SLOPE_WINDOWS, SUBSETS,
)
from src.data.loader import load_test, load_test_rul, load_train
from src.data.validation import validate_dataset
from src.evaluation import plots
from src.evaluation.metrics import classification_metrics, interval_coverage, regression_metrics
from src.features.engineering import build_features, feature_names
from src.models.artifacts import load_artifacts, save_artifacts
from src.models.risk_classifier import FailureRiskClassifier, rul_band_proba, rul_to_band
from src.models.rul_regressor import BASE_PARAMS, RULRegressor
from src.models.tuning import tune
from src.pipeline import analyze
from src.preprocessing.cleaning import clean_data
from src.preprocessing.conditions import ConditionNormalizer
from src.preprocessing.labeling import add_rul, split_by_unit

log = logging.getLogger("aerosentinel.train")  # child logger; inherits root aerosentinel handler
# Defaults used when Optuna is disabled; chosen in GroupKFold CV on the training engines.
DEFAULT_RUL_PARAMS = {"n_estimators": 700, "max_depth": 6, "learning_rate": 0.03, "subsample": 0.8,
                      "colsample_bytree": 0.5, "min_child_weight": 5}
DEFAULT_RISK_PARAMS = {"n_estimators": 700, "max_depth": 5, "learning_rate": 0.04, "subsample": 0.8,
                       "colsample_bytree": 0.5, "min_child_weight": 5}


def load_labeled(subset):
    raw = load_train(subset)
    validate_dataset(raw, SENSOR_COLS)
    df, _ = clean_data(raw)
    return add_rul(df)


def prepare_split(df, n_conditions):
    train, val = split_by_unit(df)
    conditions = ConditionNormalizer().fit(train, n_conditions)  # learned on training units only
    train, val = conditions.transform(train), conditions.transform(val)
    sensors, sensor_scores = select_sensors(train)
    health = HealthAnalyzer().fit(train, sensors)
    return health.transform(train), health.transform(val), sensors, sensor_scores, health


def cross_validate(X, y, groups, rul_params, risk_params):
    """Out-of-fold predictions on the training engines: CV metrics and the risk blend weight."""
    b = rul_to_band(y)
    oof_rul, oof_clf = np.zeros(len(X)), np.zeros((len(X), len(RISK_BANDS)))
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=REPORT_CV_FOLDS).split(X, y, groups)):
        reg = XGBRegressor(**BASE_PARAMS, **rul_params).fit(X.iloc[tr], y[tr])
        oof_rul[te] = np.clip(reg.predict(X.iloc[te]), 0, RUL_CAP)
        oof_clf[te] = FailureRiskClassifier(risk_params).fit(X.iloc[tr], b[tr]).predict_proba(X.iloc[te])
        log.info("CV fold %d/%d done", fold + 1, REPORT_CV_FOLDS)
    blended = {a: (1 - a) * oof_clf + a * rul_band_proba(oof_rul) for a in RISK_BLEND_GRID}
    scores = {a: round(float(accuracy_score(b, p.argmax(axis=1))), 4) for a, p in blended.items()}
    blend = max(scores, key=scores.get)
    best = blended[blend].argmax(axis=1)
    cv = {"cv_rmse": round(float(root_mean_squared_error(y, oof_rul)), 3),
          "cv_accuracy": scores[blend], "cv_macro_f1": round(float(f1_score(b, best, average="macro")), 4),
          "blend": blend, "blend_scores": {str(a): s for a, s in scores.items()}}
    log.info("CV: %s", cv)
    return cv


def train_rul(X_train, y_train, X_val, y_val, params, cv_rmse):
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

    model = RULRegressor(params).fit(X_train, y_train)
    low, high = model.predict_interval(X_val)
    results["xgboost"] = {**regression_metrics(y_val, model.predict(X_val)),
                          "interval_coverage": interval_coverage(y_val, low, high),
                          "cv_rmse": cv_rmse}
    log.info("RUL xgboost            %s", results["xgboost"])
    return model, results


def train_risk(X_train, b_train, X_val, b_val, params, rul, cv):
    baselines = {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced")),
        "random_forest": RandomForestClassifier(n_estimators=100, min_samples_leaf=5,
                                                class_weight="balanced", n_jobs=-1,
                                                random_state=SEED),
    }
    results = {"baselines": {}}
    for name, model in baselines.items():
        m = classification_metrics(b_val, model.fit(X_train, b_train).predict_proba(X_val))
        results["baselines"][name] = {"accuracy": m["accuracy"], "macro_f1": m["macro_f1"]}
        log.info("Risk baseline %-18s %s", name, results["baselines"][name])

    classifier_only = FailureRiskClassifier(params).fit(X_train, b_train)
    m = classification_metrics(b_val, classifier_only.predict_proba(X_val))
    results["baselines"]["xgboost_classifier_only"] = {"accuracy": m["accuracy"], "macro_f1": m["macro_f1"]}

    model = FailureRiskClassifier(params, blend=cv["blend"]).fit(X_train, b_train, rul_model=rul.model)
    results["xgboost"] = {**classification_metrics(b_val, model.predict_proba(X_val)),
                          "cv_accuracy": cv["cv_accuracy"], "cv_macro_f1": cv["cv_macro_f1"],
                          "blend": cv["blend"], "blend_scores": cv["blend_scores"]}
    log.info("Risk xgboost  accuracy=%s macro_f1=%s",
             results["xgboost"]["accuracy"], results["xgboost"]["macro_f1"])
    return results


def evaluate_test(subset, conditions, health, sensors, rul, risk):
    """Official test set: score the last cycle of each engine against RUL_<subset>.txt."""
    df = health.transform(conditions.transform(clean_data(load_test(subset))[0]))
    X = build_features(df, sensors)
    last = df.groupby("unit")["cycle"].idxmax().to_numpy()
    true = load_test_rul(subset).loc[df.loc[last, "unit"]].to_numpy()

    pred = rul.predict(X.loc[last])
    low, high = rul.predict_interval(X.loc[last])
    proba = risk.predict_proba(X.loc[last])
    metrics = {
        "rul": {**regression_metrics(true, pred), **capped_rmse(true, pred),
                "interval_coverage": interval_coverage(true, low, high),
                # the range tops out at RUL_CAP like the target, so also score it against the capped truth
                "interval_coverage_capped": interval_coverage(np.minimum(true, RUL_CAP), low, high)},
        "risk": classification_metrics(rul_to_band(true), proba),
    }
    predictions = pd.DataFrame({
        "unit": df.loc[last, "unit"].to_numpy(), "true_rul": true,
        "predicted_rul": pred.round(1), "rul_low": low.round(1), "rul_high": high.round(1),
        "true_band": [RISK_BANDS[c] for c in rul_to_band(true)],
        "predicted_band": [RISK_BANDS[c] for c in proba.argmax(axis=1)],
    })
    return metrics, predictions


def capped_rmse(true, pred):
    """RMSE with the true RUL capped like the training target: the convention most C-MAPSS papers use."""
    return {"rmse_capped": round(float(root_mean_squared_error(np.minimum(true, RUL_CAP), pred)), 3)}


def write_reports(subset, metrics, test_predictions, sensor_scores, train, val, X_sample):
    artifacts = load_artifacts(MODEL_VERSION, subset)
    folder = REPORTS_DIR / subset
    folder.mkdir(parents=True, exist_ok=True)
    figures = folder / "figures"
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=2))
    test_predictions.to_csv(folder / "test_predictions.csv", index=False)
    sensor_scores.round(4).to_csv(folder / "sensor_scores.csv")

    plots.sensor_trends(train, artifacts.sensors, figures / "sensor_trends.png")
    plots.health_scores(val, artifacts.health.threshold, figures / "health_scores.png")
    plots.rul_predictions(test_predictions["true_rul"].to_numpy(),
                          test_predictions["predicted_rul"].to_numpy(),
                          test_predictions["rul_low"].to_numpy(),
                          test_predictions["rul_high"].to_numpy(),
                          figures / "rul_test_predictions.png")
    plots.confusion(metrics["validation"]["risk"]["xgboost"]["confusion_matrix"],
                    figures / "risk_confusion_validation.png", "Risk bands: validation units")

    sample = X_sample.sample(min(2000, len(X_sample)), random_state=SEED)
    rul_shap = artifacts.rul_explainer.sensor_contributions(sample).abs().mean()
    plots.sensor_importance(rul_shap, figures / "shap_rul.png", "What drives the RUL prediction")
    codes = artifacts.risk.predict_proba(sample).argmax(axis=1)
    risk_shap = artifacts.risk_explainer.sensor_contributions(sample, class_index=codes).abs().mean()
    plots.sensor_importance(risk_shap, figures / "shap_risk.png", "What drives the risk band")
    log.info("Reports written to %s", folder)


def train_subset(subset, trials):
    start = time.perf_counter()
    np.random.seed(SEED)  # fix numpy global seed for reproducibility
    n_conditions = SUBSETS[subset]["conditions"]

    labeled = load_labeled(subset)
    train, val, sensors, sensor_scores, health = prepare_split(labeled, n_conditions)
    log.info("[%s] Units: %d train / %d validation. Conditions: %d. Sensors kept: %d of %d", subset,
             train["unit"].nunique(), val["unit"].nunique(), n_conditions, len(sensors), len(SENSOR_COLS))

    X_train, X_val = build_features(train, sensors), build_features(val, sensors)
    y_train, y_val = train["rul"].to_numpy(), val["rul"].to_numpy()
    b_train, b_val = rul_to_band(y_train), rul_to_band(y_val)
    groups = train["unit"].to_numpy()
    log.info("[%s] Features per cycle: %d", subset, X_train.shape[1])

    rul_params, risk_params = DEFAULT_RUL_PARAMS, DEFAULT_RISK_PARAMS
    if trials:
        rul_params, _ = tune(lambda p: XGBRegressor(**BASE_PARAMS, **p), X_train, y_train, groups, "regression", trials)
        risk_params, _ = tune(lambda p: FailureRiskClassifier(p), X_train, b_train, groups, "classification", trials)

    cv = cross_validate(X_train, y_train, groups, rul_params, risk_params)
    rul, rul_results = train_rul(X_train, y_train, X_val, y_val, rul_params, cv["cv_rmse"])
    risk_results = train_risk(X_train, b_train, X_val, b_val, risk_params, rul, cv)

    # Final models: same settings and sensors, refit on every training engine (train + validation units).
    final_conditions = ConditionNormalizer().fit(labeled, n_conditions)
    corrected = final_conditions.transform(labeled)
    final_health = HealthAnalyzer().fit(corrected, sensors)
    full = final_health.transform(corrected)
    X_full, y_full = build_features(full, sensors), full["rul"].to_numpy()
    final_rul = RULRegressor(rul_params).fit(X_full, y_full)
    final_risk = FailureRiskClassifier(risk_params, blend=cv["blend"]).fit(X_full, rul_to_band(y_full),
                                                                          rul_model=final_rul.model)

    test_metrics, test_predictions = evaluate_test(subset, final_conditions, final_health, sensors,
                                                   final_rul, final_risk)
    log.info("[%s] Test RUL %s", subset, test_metrics["rul"])
    log.info("[%s] Test risk accuracy=%s macro_f1=%s", subset,
             test_metrics["risk"]["accuracy"], test_metrics["risk"]["macro_f1"])

    metrics = {"validation": {"rul": rul_results, "risk": risk_results}, "test": test_metrics}
    metadata = {
        "version": MODEL_VERSION,
        "subset": subset,
        "dataset": subset,
        "run_id": uuid.uuid4().hex[:8],
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": SEED,
        "fault_modes": list(SUBSETS[subset]["fault_modes"]),
        "conditions": final_conditions.describe(),
        "train_units": sorted(int(u) for u in train["unit"].unique()),
        "val_units": sorted(int(u) for u in val["unit"].unique()),
        "final_fit": "all training engines (train + validation units), after CV model selection",
        "sensors": sensors,
        "features": feature_names(sensors),
        "config": {"rul_cap": RUL_CAP, "risk_bands": RISK_BANDS, "risk_limits": RISK_LIMITS,
                   "rul_interval": list(RUL_INTERVAL), "health_threshold": round(final_health.threshold, 4),
                   "rolling_windows": list(ROLLING_WINDOWS), "ewm_alphas": list(EWM_ALPHAS),
                   "slope_windows": list(SLOPE_WINDOWS), "baseline_cycles_per_unit": BASELINE_CYCLES_PER_UNIT,
                   "risk_blend": cv["blend"], "risk_blend_sigma": RISK_BLEND_SIGMA, "optuna_trials": trials},
        "params": {"rul": rul_params, "risk": risk_params},
        "metrics": metrics,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
    }
    folder = save_artifacts(final_health, final_rul, final_risk, final_conditions, metadata, MODEL_VERSION, subset)
    log.info("[%s] Saved model artifacts to %s", subset, folder)

    # End-to-end check: the saved models, run through the real pipeline, give the same answers.
    load_artifacts.cache_clear()
    result = analyze(RAW_DATA_DIR / f"test_{subset}.txt", subset=subset)
    assert result.status == "COMPLETED", result.stages
    assert np.allclose(result.units["predicted_rul"], test_predictions["predicted_rul"], atol=0.1)

    write_reports(subset, metrics, test_predictions, sensor_scores, train, val, X_full)
    log.info("[%s] Done in %.0fs", subset, time.perf_counter() - start)


def rescore(subset):
    """Re-score a saved model on the official test set without retraining, and refresh its reports."""
    from src.models.artifacts import model_dir

    art = load_artifacts(MODEL_VERSION, subset)
    test_metrics, test_predictions = evaluate_test(subset, art.conditions, art.health, art.sensors, art.rul, art.risk)
    meta = json.loads(json.dumps(art.metadata))  # deep copy
    meta["metrics"]["test"] = test_metrics
    (model_dir(MODEL_VERSION, subset) / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    folder = REPORTS_DIR / subset
    (folder / "metrics.json").write_text(json.dumps(meta["metrics"], indent=2))
    test_predictions.to_csv(folder / "test_predictions.csv", index=False)
    log.info("[%s] Re-scored test set: %s", subset, test_metrics["rul"])
    load_artifacts.cache_clear()


def benchmark():
    """Score every trained model on every subset's test set and write reports/benchmark.json."""
    from src.models.artifacts import available_subsets

    load_artifacts.cache_clear()
    trained = available_subsets(MODEL_VERSION)
    summary, cross = {}, {}
    for subset in trained:
        meta = load_artifacts(MODEL_VERSION, subset).metadata
        val, test = meta["metrics"]["validation"], meta["metrics"]["test"]
        summary[subset] = {
            **{k: SUBSETS[subset][k] for k in ("conditions", "train_engines", "test_engines")},
            "fault_modes": list(SUBSETS[subset]["fault_modes"]),
            "trained_at": meta["trained_at"],
            "cv_accuracy": val["risk"]["xgboost"]["cv_accuracy"],
            "val_accuracy": val["risk"]["xgboost"]["accuracy"], "val_macro_f1": val["risk"]["xgboost"]["macro_f1"],
            "val_rmse": val["rul"]["xgboost"]["rmse"],
            "test_accuracy": test["risk"]["accuracy"], "test_macro_f1": test["risk"]["macro_f1"],
            "test_rmse": test["rul"]["rmse"], "test_rmse_capped": test["rul"].get("rmse_capped"),
            "test_r2": test["rul"]["r2"], "test_interval_coverage": test["rul"]["interval_coverage"],
            "test_interval_coverage_capped": test["rul"].get("interval_coverage_capped"),
        }

    for model in trained:
        cross[model] = {}
        for data in SUBSETS:
            path = RAW_DATA_DIR / f"test_{data}.txt"
            if not path.exists():
                continue
            result = analyze(path, subset=model)
            if result.status == "FAILED":
                cross[model][data] = {"error": result.error["code"]}
                continue
            units = result.units
            true = load_test_rul(data).loc[units["unit"]].to_numpy()
            pred = units["predicted_rul"].to_numpy()
            known = result.history.groupby("unit")["condition_known"].all().loc[units["unit"]].to_numpy()
            cross[model][data] = {
                "rmse": round(float(root_mean_squared_error(true, pred)), 2),
                "rmse_capped": round(float(root_mean_squared_error(np.minimum(true, RUL_CAP), pred)), 2),
                "accuracy": round(float(accuracy_score(rul_to_band(true), units["risk_band"].map(RISK_BANDS.index))), 3),
                "known_conditions": round(float(known.mean()), 3),
            }
            log.info("Benchmark model %s on %s: %s", model, data, cross[model][data])

    payload = {"version": MODEL_VERSION, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "rul_cap": RUL_CAP, "subsets": summary, "cross": cross}
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "benchmark.json").write_text(json.dumps(payload, indent=2))
    log.info("Benchmark written to %s", REPORTS_DIR / "benchmark.json")


def main(trials, subsets, run_benchmark=True, rescore_only=False):
    start = time.perf_counter()
    for subset in subsets:
        rescore(subset) if rescore_only else train_subset(subset, trials)
    if run_benchmark:
        benchmark()
    log.info("All done in %.0f min", (time.perf_counter() - start) / 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--trials", type=int, default=OPTUNA_TRIALS,
                        help="Optuna trials per model (0 = no tuning)")
    parser.add_argument("--subset", action="append", choices=list(SUBSETS),
                        help="subset to train (repeat for several; default: all four)")
    parser.add_argument("--rescore", action="store_true",
                        help="re-score saved models on the test sets and rebuild the benchmark, without retraining")
    args = parser.parse_args()
    main(args.trials, args.subset or list(SUBSETS), rescore_only=args.rescore)
