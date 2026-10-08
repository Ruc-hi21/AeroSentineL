"""Operating-condition correction and choosing a subset model for a file."""

import numpy as np
import pandas as pd

from src.config import AUTO_SUBSET, RAW_COLUMNS, SENSOR_COLS
from src.data.profile import detect_subset
from src.preprocessing.conditions import ConditionNormalizer, count_conditions
from tests.conftest import make_engines

CONDITIONS = [(0.0, 0.0, 100.0), (20.0, 0.70, 100.0), (42.0, 0.84, 100.0)]  # altitude kft, Mach, throttle


def make_multi_condition(n_units=4, cycles=60, seed=1):
    """Engines that switch condition every cycle; each condition shifts and scales every sensor."""
    rng = np.random.default_rng(seed)
    rows = []
    for unit in range(1, n_units + 1):
        for cycle in range(1, cycles + 1):
            c = rng.integers(len(CONDITIONS))
            wear = cycle / cycles
            sensors = [(100 + 40 * c) + (1 + c) * (3 * wear * (i % 3) + rng.normal(0, 0.5))
                       for i in range(len(SENSOR_COLS))]
            settings = [v + rng.normal(0, 0.001) for v in CONDITIONS[c]]
            rows.append([unit, cycle, *settings, *sensors])
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def test_single_condition_correction_is_the_identity(engines):
    norm = ConditionNormalizer().fit(engines, n_conditions=1)
    out = norm.transform(engines)
    assert np.array_equal(out[SENSOR_COLS].to_numpy(), engines[SENSOR_COLS].to_numpy())
    assert (out["condition"] == 1).all() and out["condition_known"].all()


def test_multi_condition_correction_removes_the_condition_offset():
    df = make_multi_condition()
    norm = ConditionNormalizer().fit(df, n_conditions=3)
    assert norm.n_conditions == 3
    assert norm.describe()[0]["reference"]  # sea level sorts first and is the reference
    out = norm.transform(df)
    by_condition = out.groupby("condition")["sensor_5"].mean()
    raw_by_condition = df.groupby(out["condition"])["sensor_5"].mean()
    assert by_condition.std() < 0.05 * raw_by_condition.std()
    reference = out["condition"] == 1
    assert np.allclose(out.loc[reference, "sensor_5"].mean(), df.loc[reference, "sensor_5"].mean())


def test_unseen_condition_is_flagged():
    df = make_multi_condition()
    norm = ConditionNormalizer().fit(df, n_conditions=3)
    odd = df.head(5).copy()
    odd[["setting_1", "setting_2", "setting_3"]] = [30.0, 0.3, 60.0]
    assert not norm.transform(odd)["condition_known"].any()


def test_conditions_are_counted(engines):
    assert count_conditions(engines) == 1
    assert count_conditions(make_multi_condition()) == 3


def test_subset_comes_from_the_name_only_when_the_data_agrees(engines):
    multi = make_multi_condition()
    assert detect_subset(multi, "test_FD002.txt")[0] == "FD002"
    assert detect_subset(engines, "train_fd003.txt")[0] == "FD003"
    assert detect_subset(multi, "test_FD001.txt")[0] == AUTO_SUBSET["multi"]  # name contradicts data
    assert detect_subset(engines)[0] == AUTO_SUBSET["single"]
    assert detect_subset(make_engines(), "my_fleet.csv")[0] == AUTO_SUBSET["single"]
