"""Integration tests: end-to-end pipeline on the trained model.

Skipped until `python -m training.train` has run.
"""

import io

import pandas as pd
import pytest

from src.config import DATASET, MODEL_VERSION, MODELS_DIR, RAW_DATA_DIR, RISK_BANDS, SUBSETS
from src.data.loader import read_sensor_file
from src.models.artifacts import available_subsets, load_artifacts, model_dir, model_status
from src.pipeline import analyze

TEST_FILE = RAW_DATA_DIR / f"test_{DATASET}.txt"
pytestmark = pytest.mark.skipif(
    not (model_dir(MODEL_VERSION, DATASET) / "metadata.json").exists() or not TEST_FILE.exists(),
    reason="trained model or dataset not available",
)


@pytest.fixture(scope="module")
def test_df():
    return read_sensor_file(TEST_FILE)


def test_valid_dataset_is_fully_analyzed(test_df):  # TEST-001, TEST-005  # TEST-001, TEST-005
    result = analyze(test_df, subset=DATASET)
    assert result.status == "COMPLETED"
    units = result.units
    assert len(units) == test_df["unit"].nunique()
    assert units["predicted_rul"].between(0, 125).all()
    assert (units["rul_low"] <= units["predicted_rul"]).all()
    assert units["risk_band"].isin(RISK_BANDS).all()
    assert units["risk_probability"].between(0, 1).all()
    bands = units[[f"p_{b.lower()}" for b in RISK_BANDS]]
    assert bands.sum(axis=1).between(0.99, 1.01).all()
    chosen = bands.to_numpy()[range(len(units)), units["risk_band"].map(RISK_BANDS.index)]
    assert abs(chosen - units["risk_probability"]).max() < 0.002  # the winner's probability is the same number
    assert units["rul_factors"].apply(len).eq(5).all()
    assert units["risk_factors"].apply(len).eq(5).all()
    assert len(result.history) == len(test_df)


def test_missing_columns_give_invalid_dataset(test_df):  # TEST-002
    result = analyze(test_df.drop(columns=["sensor_11"]), subset=DATASET)
    assert result.status == "FAILED"
    assert result.error["code"] == "INVALID_DATASET"
    assert "sensor_11" in result.error["message"]


def test_garbage_file_gives_invalid_dataset():
    result = analyze(io.StringIO("hello world\nthis is not sensor data\n"))
    assert result.status == "FAILED" and result.error["code"] == "INVALID_DATASET"


def test_unit_with_few_cycles_is_handled(test_df):  # TEST-003
    short = test_df[(test_df["unit"] == 1) & (test_df["cycle"] <= 3)]
    result = analyze(short, subset=DATASET)
    assert result.status == "COMPLETED"
    assert any("short history" in r for r in result.units.loc[0, "review_reasons"])


def test_out_of_range_readings_are_flagged(test_df):  # TEST-004
    noisy = test_df[test_df["unit"] == 1].copy()
    noisy.loc[noisy.index[-1], "sensor_11"] = 999.0
    result = analyze(noisy, subset=DATASET)
    assert "readings outside training range" in result.units.loc[0, "review_reasons"]


def test_one_failing_model_gives_partial_result(test_df, monkeypatch):  # TEST-006
    artifacts = load_artifacts(MODEL_VERSION, DATASET)

    def broken(_):
        raise RuntimeError("simulated model failure")

    monkeypatch.setattr(artifacts.risk, "classify_band", broken)  # replaces method for this test only
    result = analyze(test_df[test_df["unit"] <= 3], subset=DATASET)
    assert result.status == "PARTIAL"
    assert result.stages["risk"].startswith("failed")
    assert result.stages["rul"] == "ok"
    assert "predicted_rul" in result.units and "risk_band" not in result.units


def test_missing_model_fails_safely(test_df):  # TEST-007
    assert not model_status("does_not_exist")["ready"]
    result = analyze(test_df, version="does_not_exist")
    assert result.status == "FAILED" and result.error["code"] == "MODEL_UNAVAILABLE"


def test_same_input_gives_same_result(test_df):  # TEST-010
    first, second = analyze(test_df, subset=DATASET), analyze(test_df, subset=DATASET)
    cols = ["predicted_rul", "risk_band", "risk_probability"]
    assert first.units[cols].equals(second.units[cols])


def test_file_name_picks_the_subset_model():
    result = analyze(TEST_FILE)
    assert result.subset == DATASET and "named in the file" in result.profile["reason"]
    assert result.profile["conditions_seen"] == 1 and not result.profile["corrected"]
    assert set(result.timings) >= {"read", "validate", "clean", "conditions", "health", "features", "rul"}


MULTI = "FD002"
MULTI_FILE = RAW_DATA_DIR / f"test_{MULTI}.txt"


@pytest.mark.skipif(MULTI not in available_subsets() or not MULTI_FILE.exists(),
                    reason="FD002 model or data not available")
def test_multi_condition_file_is_corrected_and_scored():
    result = analyze(MULTI_FILE)
    assert result.status == "COMPLETED" and result.subset == MULTI
    assert result.profile["corrected"] and result.profile["conditions_seen"] == 6
    assert result.history["condition"].nunique() == 6 and result.history["condition_known"].all()
    assert result.units["predicted_rul"].between(0, 125).all()


def test_unnamed_data_goes_to_a_model_for_its_kind_of_data(test_df):
    result = analyze(test_df)  # a DataFrame has no file name, so the model is chosen from the data
    assert result.status == "COMPLETED"
    assert SUBSETS[result.subset]["conditions"] == 1


@pytest.mark.skipif(not MULTI_FILE.exists(), reason="FD002 data not available")
def test_single_condition_model_flags_unseen_conditions():
    result = analyze(MULTI_FILE, subset=DATASET)
    assert result.status == "COMPLETED"
    assert any("not trained on" in w for w in result.validation["warnings"])
    assert result.units["review_reasons"].apply(lambda r: "operating condition not seen in training" in r).any()


BATTERY_FILE = RAW_DATA_DIR / "sample_PCOE.csv"
BEARING_FILE = RAW_DATA_DIR / "test_FEMTO.csv"
ROUTER_READY = (MODELS_DIR / MODEL_VERSION / "router" / "router.joblib").exists()


@pytest.mark.skipif(not ROUTER_READY or "PCOE" not in available_subsets() or not BATTERY_FILE.exists(),
                    reason="router, battery model or data not available")
def test_battery_file_is_recognised_and_scored():
    result = analyze(BATTERY_FILE)
    assert result.status == "COMPLETED", result.error
    assert result.component == "battery" and result.subset == "PCOE"
    assert result.routing["label"] == "battery" and result.routing["confidence"] >= 0.8
    assert result.units["predicted_rul"].between(0, 80).all()
    assert "soh" in result.history and result.eda["rows"] > 0


@pytest.mark.skipif(not ROUTER_READY or "FEMTO" not in available_subsets() or not BEARING_FILE.exists(),
                    reason="router, bearing model or data not available")
def test_bearing_file_is_recognised_and_scored():
    result = analyze(BEARING_FILE)
    assert result.status == "COMPLETED", result.error
    assert result.component == "bearing" and result.subset == "FEMTO"
    assert result.units["predicted_rul"].between(0, 60).all()


HYDRAULIC_FILE = RAW_DATA_DIR / "test_UCI.csv"
POWER_FILE = RAW_DATA_DIR / "sample_IGBT.csv"


@pytest.mark.skipif(not ROUTER_READY or "UCI" not in available_subsets() or not HYDRAULIC_FILE.exists(),
                    reason="router, hydraulic model or data not available")
def test_hydraulic_file_is_recognised_scored_and_diagnosed():
    result = analyze(HYDRAULIC_FILE)
    assert result.status == "COMPLETED", result.error
    assert result.component == "hydraulic" and result.subset == "UCI"
    assert result.units["predicted_rul"].between(0, 100).all()  # remaining condition margin, %
    for part in ("cooler", "valve", "pump"):
        assert f"diag_{part}" in result.units and f"diag_{part}" in result.history


@pytest.mark.skipif(not ROUTER_READY or "IGBT" not in available_subsets() or not POWER_FILE.exists(),
                    reason="router, IGBT model or data not available")
def test_power_file_is_recognised_and_scored():
    result = analyze(POWER_FILE)
    assert result.status == "COMPLETED", result.error
    assert result.component == "power" and result.subset == "IGBT"
    assert result.units["predicted_rul"].between(0, 40).all()


@pytest.mark.skipif(not ROUTER_READY, reason="router not trained")
def test_unrelated_table_is_not_routed_to_any_model():
    from sklearn.datasets import load_wine
    result = analyze(pd.DataFrame(load_wine().data))
    assert result.status == "FAILED" and result.error["code"] == "UNKNOWN_COMPONENT"
    assert result.routing is None or result.routing.get("chosen") is None


def test_turbofan_file_forced_into_another_component_is_rejected(test_df):
    result = analyze(test_df, component="battery")
    assert result.status == "FAILED" and result.error["code"] == "INVALID_DATASET"
