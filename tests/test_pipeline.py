"""Integration tests: end-to-end pipeline on the trained model.

Skipped until `python -m training.train` has run.
"""

import io

import pytest

from src.config import DATASET, MODEL_VERSION, MODELS_DIR, RAW_DATA_DIR, RISK_BANDS
from src.data.loader import read_sensor_file
from src.models.artifacts import load_artifacts, model_status
from src.pipeline import analyze

TEST_FILE = RAW_DATA_DIR / f"test_{DATASET}.txt"
pytestmark = pytest.mark.skipif(
    not (MODELS_DIR / MODEL_VERSION / "metadata.json").exists() or not TEST_FILE.exists(),
    reason="trained model or dataset not available",
)


@pytest.fixture(scope="module")
def test_df():
    return read_sensor_file(TEST_FILE)


def test_valid_dataset_is_fully_analyzed(test_df):  # TEST-001, TEST-005  # TEST-001, TEST-005
    result = analyze(test_df)
    assert result.status == "COMPLETED"
    units = result.units
    assert len(units) == test_df["unit"].nunique()
    assert units["predicted_rul"].between(0, 125).all()
    assert (units["rul_low"] <= units["predicted_rul"]).all()
    assert units["risk_band"].isin(RISK_BANDS).all()
    assert units["risk_probability"].between(0, 1).all()
    assert units["rul_factors"].apply(len).eq(5).all()
    assert units["risk_factors"].apply(len).eq(5).all()
    assert len(result.history) == len(test_df)


def test_missing_columns_give_invalid_dataset(test_df):  # TEST-002
    result = analyze(test_df.drop(columns=["sensor_11"]))
    assert result.status == "FAILED"
    assert result.error["code"] == "INVALID_DATASET"
    assert "sensor_11" in result.error["message"]


def test_garbage_file_gives_invalid_dataset():
    result = analyze(io.StringIO("hello world\nthis is not sensor data\n"))
    assert result.status == "FAILED" and result.error["code"] == "INVALID_DATASET"


def test_unit_with_few_cycles_is_handled(test_df):  # TEST-003
    short = test_df[(test_df["unit"] == 1) & (test_df["cycle"] <= 3)]
    result = analyze(short)
    assert result.status == "COMPLETED"
    assert any("short history" in r for r in result.units.loc[0, "review_reasons"])


def test_out_of_range_readings_are_flagged(test_df):  # TEST-004
    noisy = test_df[test_df["unit"] == 1].copy()
    noisy.loc[noisy.index[-1], "sensor_11"] = 999.0
    result = analyze(noisy)
    assert "readings outside training range" in result.units.loc[0, "review_reasons"]


def test_one_failing_model_gives_partial_result(test_df, monkeypatch):  # TEST-006
    artifacts = load_artifacts(MODEL_VERSION)

    def broken(_):
        raise RuntimeError("simulated model failure")

    monkeypatch.setattr(artifacts.risk, "classify_band", broken)
    result = analyze(test_df[test_df["unit"] <= 3])
    assert result.status == "PARTIAL"
    assert result.stages["risk"].startswith("failed")
    assert result.stages["rul"] == "ok"
    assert "predicted_rul" in result.units and "risk_band" not in result.units


def test_missing_model_fails_safely(test_df):  # TEST-007
    assert not model_status("does_not_exist")["ready"]
    result = analyze(test_df, version="does_not_exist")
    assert result.status == "FAILED" and result.error["code"] == "MODEL_UNAVAILABLE"


def test_same_input_gives_same_result(test_df):  # TEST-010
    first, second = analyze(test_df), analyze(test_df)
    cols = ["predicted_rul", "risk_band", "risk_probability"]
    assert first.units[cols].equals(second.units[cols])
