"""Sensor selection, health analysis, features, risk bands and explanations."""

import numpy as np

from src.analysis.degradation import select_sensors
from src.analysis.health import HealthAnalyzer
from src.config import RISK_BANDS, RISK_LIMITS
from src.explainability.explainer import Explainer
from src.features.engineering import build_features, feature_names, sensor_of
from src.models.risk_classifier import FailureRiskClassifier, rul_to_band
from src.models.rul_regressor import RULRegressor
from src.preprocessing.labeling import add_rul
from tests.conftest import make_engines


def test_constant_sensors_are_dropped(engines):  # TEST-M-001
    sensors, scores = select_sensors(add_rul(engines))
    assert "sensor_1" not in sensors
    assert not scores.loc["sensor_1", "kept"]


def test_health_score_rises_with_wear():  # TEST-M-002
    df = add_rul(make_engines(n_units=6, cycles=60))
    health = HealthAnalyzer().fit(df, ["sensor_2", "sensor_3", "sensor_5"])
    out = health.transform(df)
    early = out[out["cycle"] <= 10]["health_score"].mean()
    late = out[out["cycle"] >= 55]["health_score"].mean()
    assert late > early
    assert set(out["health_condition"]) <= {"normal", "abnormal"}


def test_features_work_for_a_unit_with_one_cycle(engines):
    one_cycle = engines[engines["cycle"] == 1]
    features = build_features(one_cycle, ["sensor_2", "sensor_3"])
    assert list(features.columns) == feature_names(["sensor_2", "sensor_3"])
    assert not features.isna().any().any()


def test_sensor_of_maps_features_back():
    assert sensor_of("sensor_11_mean") == "sensor_11"
    assert sensor_of("sensor_11_std") == "sensor_11"
    assert sensor_of("cycle") == "cycle"


def test_risk_bands_cover_every_rul_with_no_gaps():  # TEST-M-005
    rul = np.arange(0, 400)
    codes = rul_to_band(rul)
    assert set(codes) == set(range(len(RISK_BANDS)))
    assert np.all(np.diff(codes) <= 0)  # severity only falls as RUL grows
    assert codes[RISK_LIMITS["FAILURE_LIKELY"]] == RISK_BANDS.index("FAILURE_LIKELY")
    assert codes[RISK_LIMITS["FAILURE_LIKELY"] + 1] == RISK_BANDS.index("HIGH_RISK")
    assert codes[RISK_LIMITS["AT_RISK"] + 1] == RISK_BANDS.index("NORMAL")


def _small_training_set():
    df = add_rul(make_engines(n_units=6, cycles=80))  # RUL 0-79: all four bands present
    sensors = ["sensor_2", "sensor_3", "sensor_5"]
    return build_features(df, sensors), df["rul"].to_numpy()


def test_rul_interval_contains_prediction():  # TEST-M-006
    X, y = _small_training_set()
    model = RULRegressor({"n_estimators": 30, "max_depth": 3}).fit(X, y)
    low, high = model.predict_interval(X)
    pred = model.predict(X)
    assert np.all(low <= pred) and np.all(pred <= high)


def test_explanations_name_sensors_for_both_models():  # TEST-M-007
    X, y = _small_training_set()
    rul = RULRegressor({"n_estimators": 30, "max_depth": 3}).fit(X, y)
    risk = FailureRiskClassifier({"n_estimators": 30, "max_depth": 3}).fit(X, rul_to_band(y))

    rul_top = Explainer(rul.model).explain(X.head(3), top_k=2)
    codes, _ = risk.classify_band(X.head(3))
    risk_top = Explainer(risk.model).explain(X.head(3), class_index=codes, top_k=2)

    for top in (rul_top, risk_top):
        assert len(top) == 3 and all(len(row) == 2 for row in top)
        assert all(not f["sensor"].endswith(("_mean", "_std")) for row in top for f in row)
