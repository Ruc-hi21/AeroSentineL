"""Train, evaluate and save one model set per component profile, plus the component-recognition model.

Profiles: turbofan FD001-FD004 (NASA C-MAPSS), battery PCOE (NASA PCoE Li-ion cells) and bearing
FEMTO (PRONOSTIA run-to-failure bearings). Each component uses its own RUL units, RUL cap and
risk-band limits (src/components/).

Protocol per profile (no test-set information is used for any choice):
  1. Split the training units 80/20 by unit.
  2. Learn the operating conditions and correct every reading to the reference condition
     (identity for single-condition data).
  3. 5-fold GroupKFold CV on the 80% -> CV metrics and the risk blend weight.
  4. Fit on the 80%, score the 20% held-out validation units (every cycle).
  5. Refit on all training units with the chosen settings, save, and score the test set
     (last cycle of each test unit against RUL_<profile>.txt).
Then the component-recognition model is trained on table fingerprints (src/router/), and a
benchmark scores every turbofan model on every C-MAPSS test fleet.

Usage:
    python -m training.train                       # everything, about 40 min
    python -m training.train --component battery   # one component (repeat for several; also: router)
    python -m training.train --subset FD002        # one profile (repeat the flag for several)
    python -m training.train --trials 20           # also tune both XGBoost models with Optuna
    python -m training.train --rescore             # refresh test metrics and the benchmark from saved models
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
from xgboost import XGBClassifier, XGBRegressor

from src.analysis.degradation import select_sensors
from src.analysis.health import HealthAnalyzer
from src.components import COMPONENTS, PROFILES, spec_of_profile
from src.config import (
    BASELINE_CYCLES_PER_UNIT, EWM_ALPHAS, MODEL_VERSION, OPTUNA_TRIALS, REPORT_CV_FOLDS, REPORTS_DIR, RISK_BANDS,
    RISK_BLEND_GRID, RISK_BLEND_SIGMA, ROLLING_WINDOWS, RUL_INTERVAL, SEED, SLOPE_WINDOWS, SUBSETS,
)
from src.data.loader import data_file, load_test, load_test_rul, load_train
from src.data.validation import validate_dataset
from src.evaluation import plots
from src.evaluation.metrics import classification_metrics, interval_coverage, regression_metrics
from src.features.engineering import derive_channels, model_features
from src.models.artifacts import available_subsets, load_artifacts, model_dir, save_artifacts
from src.models.risk_classifier import FailureRiskClassifier, rul_band_proba, rul_to_band
from src.models.rul_regressor import BASE_PARAMS, RULRegressor
from src.models.tuning import tune
from src.pipeline import analyze
from src.preprocessing.cleaning import clean_data
from src.preprocessing.conditions import ConditionNormalizer
from src.preprocessing.labeling import add_rul, split_by_unit

log = logging.getLogger("aerosentinel.train")  # child logger; inherits root aerosentinel handler
# Defaults used when Optuna is disabled; chosen in GroupKFold CV on the C-MAPSS training engines.
DEFAULT_RUL_PARAMS = {"n_estimators": 700, "max_depth": 6, "learning_rate": 0.03, "subsample": 0.8,
                      "colsample_bytree": 0.5, "min_child_weight": 5}
DEFAULT_RISK_PARAMS = {"n_estimators": 700, "max_depth": 5, "learning_rate": 0.04, "subsample": 0.8,
                       "colsample_bytree": 0.5, "min_child_weight": 5}


def load_labeled(profile):
    spec = spec_of_profile(profile)
    raw = load_train(profile)
    validate_dataset(raw, spec.channel_keys)
    df, _ = clean_data(raw, spec.columns + spec.label_columns)
    # Derived channels (battery state of health) come from the raw readings, before condition correction.
    df = derive_channels(df, spec)
    if spec.target:  # condition-labelled data (hydraulic): the target is in the file
        df = df.copy()
        df["rul"] = df[spec.target].clip(0, spec.rul_cap)
        return df
    return add_rul(df, spec.rul_cap)


def groups_of(df, spec):
    """What validation must keep together: units, or larger groups when units share a setting (hydraulic blocks)."""
    return df[spec.group].to_numpy() if spec.group else df["unit"].to_numpy()


def split_groups(df, spec):
    """80/20 split by unit, or by group for components that define one."""
    if not spec.group:
        return split_by_unit(df)
    groups = np.sort(df[spec.group].unique())
    rng = np.random.default_rng(SEED)
    val = rng.choice(groups, size=max(1, round(len(groups) * 0.2)), replace=False)
    mask = df[spec.group].isin(val)
    return df[~mask].copy(), df[mask].copy()


def fit_conditions(df, profile):
    """Turbofan subsets use their documented condition count; other components count them in the data."""
    spec = spec_of_profile(profile)
    n = spec.profiles[profile].conditions if spec.key == "turbofan" else None
    return ConditionNormalizer().fit(df, n, sensors=spec.channel_keys, settings=spec.settings,
                                     scale=spec.setting_scale, reference=spec.reference_settings)


def prepare_split(df, profile):
    spec = spec_of_profile(profile)
    train, val = split_groups(df, spec)
    conditions = fit_conditions(train, profile)  # learned on training units only
    train, val = conditions.transform(train), conditions.transform(val)
    sensors, sensor_scores = select_sensors(train, spec.model_channels)
    health = HealthAnalyzer().fit(train, sensors, spec.baseline_cycles)
    return health.transform(train), health.transform(val), sensors, sensor_scores, health, conditions


def cross_validate(X, y, groups, rul_params, risk_params, spec):
    """Out-of-fold predictions on the training units: CV metrics and the risk blend weight."""
    limits, cap = spec.risk_limits, spec.rul_cap
    b = rul_to_band(y, limits)
    oof_rul, oof_clf = np.zeros(len(X)), np.zeros((len(X), len(RISK_BANDS)))
    folds = min(REPORT_CV_FOLDS, len(np.unique(groups)))
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=folds).split(X, y, groups)):
        reg = XGBRegressor(**BASE_PARAMS, **rul_params).fit(X.iloc[tr], y[tr])
        oof_rul[te] = np.clip(reg.predict(X.iloc[te]), 0, cap)
        clf = FailureRiskClassifier(risk_params, limits=limits, cap=cap).fit(X.iloc[tr], b[tr])
        oof_clf[te] = _full_proba(clf, X.iloc[te])
        log.info("CV fold %d/%d done", fold + 1, folds)
    blended = {a: (1 - a) * oof_clf + a * rul_band_proba(oof_rul, limits=limits) for a in RISK_BLEND_GRID}
    scores = {a: round(float(accuracy_score(b, p.argmax(axis=1))), 4) for a, p in blended.items()}
    blend = max(scores, key=scores.get)
    best = blended[blend].argmax(axis=1)
    cv = {"cv_rmse": round(float(root_mean_squared_error(y, oof_rul)), 3),
          "cv_accuracy": scores[blend], "cv_macro_f1": round(float(f1_score(b, best, average="macro")), 4),
          "blend": blend, "blend_scores": {str(a): s for a, s in scores.items()}}
    log.info("CV: %s", cv)
    return cv


def _full_proba(model, X):
    """Class probabilities over all four bands, even if a training fold lacked one."""
    proba = model.predict_proba(X)
    if proba.shape[1] == len(RISK_BANDS):
        return proba
    classes = getattr(getattr(model, "model", model), "classes_", np.arange(proba.shape[1]))
    full = np.zeros((len(X), len(RISK_BANDS)))
    full[:, classes] = proba
    return full


def train_rul(X_train, y_train, X_val, y_val, params, cv_rmse, spec):
    baselines = {
        "linear_regression": make_pipeline(StandardScaler(), LinearRegression()),
        "random_forest": RandomForestRegressor(n_estimators=100, min_samples_leaf=5,
                                               n_jobs=-1, random_state=SEED),
    }
    results = {"baselines": {}}
    for name, model in baselines.items():
        pred = np.clip(model.fit(X_train, y_train).predict(X_val), 0, spec.rul_cap)
        results["baselines"][name] = regression_metrics(y_val, pred)
        log.info("RUL baseline %-18s %s", name, results["baselines"][name])

    model = RULRegressor(params, cap=spec.rul_cap).fit(X_train, y_train)
    low, high = model.predict_interval(X_val)
    results["xgboost"] = {**regression_metrics(y_val, model.predict(X_val)),
                          "interval_coverage": interval_coverage(y_val, low, high),
                          "cv_rmse": cv_rmse}
    log.info("RUL xgboost            %s", results["xgboost"])
    return model, results


def train_risk(X_train, b_train, X_val, b_val, params, rul, cv, spec):
    baselines = {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced")),
        "random_forest": RandomForestClassifier(n_estimators=100, min_samples_leaf=5,
                                                class_weight="balanced", n_jobs=-1,
                                                random_state=SEED),
    }
    results = {"baselines": {}}
    for name, model in baselines.items():
        m = classification_metrics(b_val, _full_proba(model.fit(X_train, b_train), X_val))
        results["baselines"][name] = {"accuracy": m["accuracy"], "macro_f1": m["macro_f1"]}
        log.info("Risk baseline %-18s %s", name, results["baselines"][name])

    kw = {"limits": spec.risk_limits, "cap": spec.rul_cap}
    classifier_only = FailureRiskClassifier(params, **kw).fit(X_train, b_train)
    m = classification_metrics(b_val, _full_proba(classifier_only, X_val))
    results["baselines"]["xgboost_classifier_only"] = {"accuracy": m["accuracy"], "macro_f1": m["macro_f1"]}

    model = FailureRiskClassifier(params, blend=cv["blend"], **kw).fit(X_train, b_train, rul_model=rul.model)
    results["xgboost"] = {**classification_metrics(b_val, _full_proba(model, X_val)),
                          "cv_accuracy": cv["cv_accuracy"], "cv_macro_f1": cv["cv_macro_f1"],
                          "blend": cv["blend"], "blend_scores": cv["blend_scores"]}
    log.info("Risk xgboost  accuracy=%s macro_f1=%s",
             results["xgboost"]["accuracy"], results["xgboost"]["macro_f1"])
    return results


def evaluate_test(profile, conditions, health, sensors, rul, risk):
    """Test set: score the last cycle of each test unit against RUL_<profile>.txt."""
    spec = spec_of_profile(profile)
    df = health.transform(conditions.transform(derive_channels(clean_data(load_test(profile), spec.columns)[0], spec)))
    X = model_features(df, sensors, spec)
    last = df.groupby("unit")["cycle"].idxmax().to_numpy()
    true = load_test_rul(profile).loc[df.loc[last, "unit"]].to_numpy()

    pred = rul.predict(X.loc[last])
    low, high = rul.predict_interval(X.loc[last])
    proba = _full_proba(risk, X.loc[last])
    bands = rul_to_band(true, spec.risk_limits)
    metrics = {
        "rul": {**regression_metrics(true, pred), **capped_rmse(true, pred, spec.rul_cap),
                "interval_coverage": interval_coverage(true, low, high),
                # the range tops out at the RUL cap like the target, so also score it against the capped truth
                "interval_coverage_capped": interval_coverage(np.minimum(true, spec.rul_cap), low, high)},
        "risk": classification_metrics(bands, proba),
    }
    predictions = pd.DataFrame({
        "unit": df.loc[last, "unit"].to_numpy(), "true_rul": true,
        "predicted_rul": pred.round(1), "rul_low": low.round(1), "rul_high": high.round(1),
        "true_band": [RISK_BANDS[c] for c in bands],
        "predicted_band": [RISK_BANDS[c] for c in proba.argmax(axis=1)],
    })
    return metrics, predictions


def train_diagnosis(spec, full, X_full, groups):
    """One classifier per labelled part (hydraulic cooler, valve, pump), with grouped CV accuracy."""
    models, metrics = {}, {}
    for d in spec.diagnosis:
        values = [v for v, _, _ in d.levels]
        y = full[d.key].map({v: i for i, v in enumerate(values)}).to_numpy()
        params = dict(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.8,
                      random_state=SEED, n_jobs=-1, verbosity=0)
        oof = np.zeros(len(y), dtype=int)
        folds = min(REPORT_CV_FOLDS, len(np.unique(groups)))
        for tr, te in GroupKFold(n_splits=folds).split(X_full, y, groups):
            clf = XGBClassifier(**params).fit(X_full.iloc[tr], _dense(y[tr]))
            oof[te] = np.asarray(_classes(y[tr]))[clf.predict(X_full.iloc[te])]
        models[d.key] = {"model": XGBClassifier(**params).fit(X_full, y), "values": values}
        metrics[d.key] = {"name": d.name, "cv_accuracy": round(float((oof == y).mean()), 4)}
    return models, metrics


def _classes(y):
    return np.unique(y)


def _dense(y):
    """XGBoost needs classes 0..k-1; a fold can miss one."""
    return np.searchsorted(np.unique(y), y)


def evaluate_diagnosis(profile, conditions, health, sensors, diagnosis, metrics):
    """Every cycle of the held-out units against labels_<profile>.csv."""
    spec = spec_of_profile(profile)
    df = health.transform(conditions.transform(derive_channels(clean_data(load_test(profile), spec.columns)[0], spec)))
    X = model_features(df, sensors, spec)
    labels = pd.read_csv(data_file("labels", profile)).rename(columns={spec.id_column: "unit", spec.time_column: "cycle"})
    truth = df[["unit", "cycle"]].merge(labels, on=["unit", "cycle"], how="left")
    for key, part in diagnosis.items():
        pred = np.asarray(part["values"])[part["model"].predict_proba(X).argmax(axis=1)]
        true = truth[key].to_numpy()
        cm = pd.crosstab(pd.Categorical(true, part["values"]), pd.Categorical(pred, part["values"]), dropna=False)
        metrics[key].update({"test_accuracy": round(float((pred == true).mean()), 4),
                             "labels": [str(v) for v in part["values"]], "confusion_matrix": cm.to_numpy().tolist()})
    return metrics


def capped_rmse(true, pred, cap):
    """RMSE with the true RUL capped like the training target: the convention most C-MAPSS papers use."""
    return {"rmse_capped": round(float(root_mean_squared_error(np.minimum(true, cap), pred)), 3)}


def write_reports(profile, metrics, test_predictions, sensor_scores, train, val, X_sample):
    artifacts = load_artifacts(MODEL_VERSION, profile)
    folder = REPORTS_DIR / profile
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
    codes = _full_proba(artifacts.risk, sample).argmax(axis=1)
    risk_shap = artifacts.risk_explainer.sensor_contributions(sample, class_index=codes).abs().mean()
    plots.sensor_importance(risk_shap, figures / "shap_risk.png", "What drives the risk band")
    log.info("Reports written to %s", folder)


def train_subset(profile, trials):
    start = time.perf_counter()
    np.random.seed(SEED)  # fix numpy global seed for reproducibility
    spec = spec_of_profile(profile)

    labeled = load_labeled(profile)
    train, val, sensors, sensor_scores, health, conditions = prepare_split(labeled, profile)
    log.info("[%s] %s. Units: %d train / %d validation. Conditions: %d. Sensors kept: %d of %d", profile, spec.name,
             train["unit"].nunique(), val["unit"].nunique(), conditions.n_conditions, len(sensors), len(spec.model_channels))

    X_train, X_val = model_features(train, sensors, spec), model_features(val, sensors, spec)
    y_train, y_val = train["rul"].to_numpy(), val["rul"].to_numpy()
    b_train, b_val = rul_to_band(y_train, spec.risk_limits), rul_to_band(y_val, spec.risk_limits)
    groups = groups_of(train, spec)
    log.info("[%s] Features per cycle: %d", profile, X_train.shape[1])

    rul_params, risk_params = DEFAULT_RUL_PARAMS, DEFAULT_RISK_PARAMS
    if trials:
        rul_params, _ = tune(lambda p: XGBRegressor(**BASE_PARAMS, **p), X_train, y_train, groups, "regression", trials)
        risk_params, _ = tune(lambda p: FailureRiskClassifier(p, limits=spec.risk_limits, cap=spec.rul_cap),
                              X_train, b_train, groups, "classification", trials)

    cv = cross_validate(X_train, y_train, groups, rul_params, risk_params, spec)
    rul, rul_results = train_rul(X_train, y_train, X_val, y_val, rul_params, cv["cv_rmse"], spec)
    risk_results = train_risk(X_train, b_train, X_val, b_val, risk_params, rul, cv, spec)

    # Final models: same settings and sensors, refit on every training unit (train + validation units).
    final_conditions = fit_conditions(labeled, profile)
    corrected = final_conditions.transform(labeled)
    final_health = HealthAnalyzer().fit(corrected, sensors, spec.baseline_cycles)
    full = final_health.transform(corrected)
    X_full, y_full = model_features(full, sensors, spec), full["rul"].to_numpy()
    final_rul = RULRegressor(rul_params, cap=spec.rul_cap).fit(X_full, y_full)
    final_risk = FailureRiskClassifier(risk_params, blend=cv["blend"], limits=spec.risk_limits, cap=spec.rul_cap).fit(
        X_full, rul_to_band(y_full, spec.risk_limits), rul_model=final_rul.model)

    test_metrics, test_predictions = evaluate_test(profile, final_conditions, final_health, sensors,
                                                   final_rul, final_risk)
    diagnosis, diagnosis_metrics = train_diagnosis(spec, full, X_full, groups_of(full, spec))
    if diagnosis:
        diagnosis_metrics = evaluate_diagnosis(profile, final_conditions, final_health, sensors, diagnosis,
                                               diagnosis_metrics)
        log.info("[%s] Part diagnosis: %s", profile, {k: v.get("test_accuracy") for k, v in diagnosis_metrics.items()})
    log.info("[%s] Test RUL %s", profile, test_metrics["rul"])
    log.info("[%s] Test risk accuracy=%s macro_f1=%s", profile,
             test_metrics["risk"]["accuracy"], test_metrics["risk"]["macro_f1"])

    metrics = {"validation": {"rul": rul_results, "risk": risk_results}, "test": test_metrics}
    if diagnosis:
        metrics["diagnosis"] = diagnosis_metrics
    metadata = {
        "version": MODEL_VERSION,
        "component": spec.key,
        "subset": profile,
        "dataset": profile,
        "run_id": uuid.uuid4().hex[:8],
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": SEED,
        "fault_modes": list(spec.profiles[profile].fault_modes),
        "conditions": final_conditions.describe(),
        "train_units": sorted(int(u) for u in train["unit"].unique()),
        "val_units": sorted(int(u) for u in val["unit"].unique()),
        "final_fit": "all training units (train + validation units), after CV model selection",
        "sensors": sensors,
        "features": list(X_full.columns),
        "config": {"rul_cap": spec.rul_cap, "life_unit": spec.life_unit, "risk_bands": RISK_BANDS,
                   "risk_limits": spec.risk_limits, "rul_interval": list(RUL_INTERVAL),
                   "health_threshold": round(final_health.threshold, 4), "baseline_cycles": spec.baseline_cycles,
                   "rolling_windows": list(ROLLING_WINDOWS), "ewm_alphas": list(EWM_ALPHAS),
                   "slope_windows": list(SLOPE_WINDOWS), "baseline_cycles_per_unit": BASELINE_CYCLES_PER_UNIT,
                   "risk_blend": cv["blend"], "risk_blend_sigma": RISK_BLEND_SIGMA, "optuna_trials": trials},
        "params": {"rul": rul_params, "risk": risk_params},
        "metrics": metrics,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
    }
    folder = save_artifacts(final_health, final_rul, final_risk, final_conditions, metadata, MODEL_VERSION, profile,
                            diagnosis=diagnosis)
    log.info("[%s] Saved model artifacts to %s", profile, folder)

    # End-to-end check: the saved models, run through the real pipeline, give the same answers.
    load_artifacts.cache_clear()
    result = analyze(data_file("test", profile), subset=profile, component=spec.key)
    assert result.status == "COMPLETED", (result.stages, result.error)
    assert np.allclose(result.units["predicted_rul"], test_predictions["predicted_rul"], atol=0.1)

    write_reports(profile, metrics, test_predictions, sensor_scores, train, val, X_full)
    log.info("[%s] Done in %.0fs", profile, time.perf_counter() - start)


def rescore(profile):
    """Re-score a saved model on its test set without retraining, and refresh its reports."""
    art = load_artifacts(MODEL_VERSION, profile)
    test_metrics, test_predictions = evaluate_test(profile, art.conditions, art.health, art.sensors, art.rul, art.risk)
    meta = json.loads(json.dumps(art.metadata))  # deep copy
    meta["metrics"]["test"] = test_metrics
    (model_dir(MODEL_VERSION, profile) / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    folder = REPORTS_DIR / profile
    (folder / "metrics.json").write_text(json.dumps(meta["metrics"], indent=2))
    test_predictions.to_csv(folder / "test_predictions.csv", index=False)
    log.info("[%s] Re-scored test set: %s", profile, test_metrics["rul"])
    load_artifacts.cache_clear()


def benchmark():
    """Headline metrics for every trained profile, every turbofan model on every C-MAPSS test fleet,
    and the component-recognition results; written to reports/benchmark.json."""
    from src.router import load_router

    load_artifacts.cache_clear()
    trained = available_subsets(MODEL_VERSION)
    summary, cross = {}, {}
    for profile in trained:
        spec = spec_of_profile(profile)
        meta = load_artifacts(MODEL_VERSION, profile).metadata
        val, test = meta["metrics"]["validation"], meta["metrics"]["test"]
        info = spec.profiles[profile]
        summary[profile] = {
            "component": spec.key, "component_name": spec.name, "life_unit": spec.life_unit,
            "conditions": len(meta.get("conditions") or [1]), "train_engines": info.train_units,
            "test_engines": info.test_units, "fault_modes": list(info.fault_modes),
            "trained_at": meta["trained_at"],
            "cv_accuracy": val["risk"]["xgboost"]["cv_accuracy"],
            "val_accuracy": val["risk"]["xgboost"]["accuracy"], "val_macro_f1": val["risk"]["xgboost"]["macro_f1"],
            "val_rmse": val["rul"]["xgboost"]["rmse"], "cv_rmse": val["rul"]["xgboost"].get("cv_rmse"),
            "test_accuracy": test["risk"]["accuracy"], "test_macro_f1": test["risk"]["macro_f1"],
            "test_rmse": test["rul"]["rmse"], "test_rmse_capped": test["rul"].get("rmse_capped"),
            "test_mae": test["rul"]["mae"], "test_r2": test["rul"]["r2"],
            "test_interval_coverage": test["rul"]["interval_coverage"],
            "test_interval_coverage_capped": test["rul"].get("interval_coverage_capped"),
        }

    turbofan = [p for p in trained if spec_of_profile(p).key == "turbofan"]
    for model in turbofan:
        cross[model] = {}
        for data in SUBSETS:
            path = data_file("test", data)
            if not path.exists():
                continue
            result = analyze(path, subset=model, component="turbofan")
            if result.status == "FAILED":
                cross[model][data] = {"error": result.error["code"]}
                continue
            units = result.units
            true = load_test_rul(data).loc[units["unit"]].to_numpy()
            pred = units["predicted_rul"].to_numpy()
            known = result.history.groupby("unit")["condition_known"].all().loc[units["unit"]].to_numpy()
            cap = spec_of_profile(model).rul_cap
            cross[model][data] = {
                "rmse": round(float(root_mean_squared_error(true, pred)), 2),
                "rmse_capped": round(float(root_mean_squared_error(np.minimum(true, cap), pred)), 2),
                "accuracy": round(float(accuracy_score(rul_to_band(true), units["risk_band"].map(RISK_BANDS.index))), 3),
                "known_conditions": round(float(known.mean()), 3),
            }
            log.info("Benchmark model %s on %s: %s", model, data, cross[model][data])

    router = load_router()
    payload = {"version": MODEL_VERSION, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "rul_cap": spec_of_profile("FD001").rul_cap, "subsets": summary, "cross": cross,
               "router": router.metadata.get("metrics") if router else None}
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "benchmark.json").write_text(json.dumps(payload, indent=2))
    log.info("Benchmark written to %s", REPORTS_DIR / "benchmark.json")


def main(trials, profiles, router=True, run_benchmark=True, rescore_only=False):
    start = time.perf_counter()
    for profile in profiles:
        rescore(profile) if rescore_only else train_subset(profile, trials)
    if router and not rescore_only:
        from training.train_router import train_router
        train_router()
    if run_benchmark:
        benchmark()
    log.info("All done in %.0f min", (time.perf_counter() - start) / 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--trials", type=int, default=OPTUNA_TRIALS,
                        help="Optuna trials per model (0 = no tuning)")
    parser.add_argument("--subset", action="append", choices=list(PROFILES),
                        help="profile to train (repeat for several)")
    parser.add_argument("--component", action="append", choices=[*COMPONENTS, "router"],
                        help="component to train (repeat for several; 'router' = only the recognition model)")
    parser.add_argument("--rescore", action="store_true",
                        help="re-score saved models on the test sets and rebuild the benchmark, without retraining")
    args = parser.parse_args()
    chosen = list(args.subset or [])
    for comp in args.component or []:
        if comp != "router":
            chosen += [p for p in COMPONENTS[comp].profiles if p not in chosen]
    only_router = args.component == ["router"]
    if not chosen and not only_router:
        chosen = list(PROFILES)
    with_router = only_router or "router" in (args.component or []) or not (args.subset or args.component)
    main(args.trials, chosen, router=with_router, rescore_only=args.rescore)
