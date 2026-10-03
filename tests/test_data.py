"""Loading, validation, cleaning, RUL labels and the engine-unit split.

All tests run on synthetic data so no disk files are required.
"""

import io

import numpy as np
import pandas as pd
import pytest

from src.config import RAW_COLUMNS, SENSOR_COLS
from src.data.loader import read_sensor_file
from src.data.validation import validate_dataset
from src.errors import InvalidDataError
from src.preprocessing.cleaning import clean_data
from src.preprocessing.labeling import add_rul, split_by_unit
from tests.conftest import make_engines


def test_reads_raw_text_and_csv(engines):  # TEST-D-001
    raw_text = engines.to_csv(sep=" ", header=False, index=False)
    assert list(read_sensor_file(io.StringIO(raw_text)).columns) == RAW_COLUMNS  # column order matters
    csv_bytes = io.BytesIO(engines.to_csv(index=False).encode())
    assert read_sensor_file(csv_bytes).shape == engines.shape


def test_wrong_column_count_is_rejected():  # TEST-D-002
    with pytest.raises(InvalidDataError, match="Expected 26 columns"):
        read_sensor_file(io.StringIO("1 2 3\n4 5 6\n"))


def test_empty_file_is_rejected():  # TEST-D-003
    with pytest.raises(InvalidDataError):
        read_sensor_file(io.StringIO("   "))


def test_missing_columns_are_reported(engines):  # TEST-D-004
    with pytest.raises(InvalidDataError, match="sensor_11"):
        validate_dataset(engines.drop(columns=["sensor_11"]), SENSOR_COLS)


def test_validation_warns_about_fixable_problems(engines):  # TEST-D-006
    engines = engines.astype({"sensor_2": object})
    engines.loc[0, "sensor_2"] = "bad"
    report = validate_dataset(engines, SENSOR_COLS)
    assert report["units"] == 4
    assert any("non-numeric" in w for w in report["warnings"])


def test_cleaning_handles_duplicates_missing_and_bad_types(engines):  # TEST-D-008
    dirty = engines.astype({"sensor_2": object})
    dirty.loc[3, "sensor_2"] = "not a number"
    dirty.loc[5, "sensor_3"] = np.nan
    dirty.loc[7, "unit"] = np.nan
    dirty = pd.concat([dirty, dirty.iloc[[10]]])

    clean, report = clean_data(dirty)
    assert report["dropped_duplicates"] == 1
    assert report["dropped_invalid_rows"] == 1
    assert clean.isna().sum().sum() == 0
    assert clean["sensor_2"].dtype.kind == "f"
    assert clean.duplicated(subset=["unit", "cycle"]).sum() == 0


def test_rul_is_capped_and_zero_at_last_cycle(engines):  # TEST-D-005
    labeled = add_rul(engines, cap=25)
    assert labeled["rul"].max() == 25
    last = labeled.groupby("unit")["cycle"].idxmax()
    assert (labeled.loc[last, "rul"] == 0).all()


def test_split_never_shares_units():  # TEST-D-007
    df = make_engines(n_units=10)
    train, val = split_by_unit(df, test_size=0.2, seed=1)
    assert set(train["unit"]).isdisjoint(val["unit"])
    assert val["unit"].nunique() == 2
    assert len(train) + len(val) == len(df)
