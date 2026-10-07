"""Sensor selection, health analysis, features, risk bands and explanations."""

import numpy as np
import pandas as pd

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
    df = add_rul(make_engines(n_units=6, cycles=60))  # 6 units; enough for all 4 risk bands
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
    assert sensor_of("sensor_11__slope30") == "sensor_11"
    assert sensor_of("sensor_11__ewm0.1") == "sensor_11"
    assert sensor_of("sensor_11_mean") == "sensor_11"  # v1 names still map
    assert sensor_of("cycle") == "cycle"


def test_features_are_causal():
    """A feature at cycle t must not change when the engine's later cycles are removed."""
    df = make_engines(n_units=3, cycles=60)
    sensors = ["sensor_2", "sensor_3"]
    full = build_features(df, sensors)
    cut = df[df["cycle"] <= 35]
    early = build_features(cut, sensors)
    assert np.allclose(full.loc[cut.index].to_numpy(), early.to_numpy())
    assert not full.isna().any().any()


def test_rul_band_proba_is_a_distribution_centred_on_the_band():
    from src.models.risk_classifier import rul_band_proba
    proba = rul_band_proba(np.array([5.0, 22.0, 45.0, 110.0]), sigma=4.0)
    assert np.allclose(proba.sum(axis=1), 1.0)
    assert proba.argmax(axis=1).tolist() == [3, 2, 1, 0]


def test_blended_risk_probabilities_sum_to_one():
    X, y = _small_training_set()
    rul = RULRegressor({"n_estimators": 30, "max_depth": 3}).fit(X, y)
    risk = FailureRiskClassifier({"n_estimators": 30, "max_depth": 3}, blend=0.5).fit(X, rul_to_band(y), rul_model=rul.model)
    proba = risk.predict_proba(X)
    assert proba.shape == (len(X), 4)
    assert np.allclose(proba.sum(axis=1), 1.0)


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

    rul_top = Explainer(rul.model).explain(X.head(3), top_k=2)  # small top_k speeds up test
    codes, _ = risk.classify_band(X.head(3))
    risk_top = Explainer(risk.model).explain(X.head(3), class_index=codes, top_k=2)

    for top in (rul_top, risk_top):
        assert len(top) == 3 and all(len(row) == 2 for row in top)
        assert all(not f["sensor"].endswith(("_mean", "_std")) for row in top for f in row)


def test_rul_bounds_validation():
    import pandas as pd
    from src.preprocessing.labeling import validate_rul_bounds
    df = pd.DataFrame({"RUL": [10.0, 5.0, 0.0]})
    assert validate_rul_bounds(df) is True
    df_invalid = pd.DataFrame({"RUL": [10.0, -1.0, 0.0]})
    assert validate_rul_bounds(df_invalid) is False


def test_fleet_health_distribution_counts_higher_scores_as_worse():
    from src.analysis.health import compute_fleet_health_distribution
    scores = pd.Series([0.0, 0.5, 1.5, 3.0])  # threshold 1.0 -> critical above 2.0
    assert compute_fleet_health_distribution(scores, threshold=1.0) == {
        "normal": 2, "degraded": 1, "critical": 1,
    }
