import numpy as np
import pandas as pd
import pytest

from src.config import RAW_COLUMNS, SENSOR_COLS


def make_engines(n_units=4, cycles=40, seed=0):
    """Small synthetic C-MAPSS-shaped data: a few sensors drift as each unit ages."""
    rng = np.random.default_rng(seed)
    rows = []
    for unit in range(1, n_units + 1):
        for cycle in range(1, cycles + 1):
            wear = cycle / cycles
            sensors = [100 + 5 * wear * (i % 3) + rng.normal(0, 0.5) for i in range(len(SENSOR_COLS))]
            rows.append([unit, cycle, 0.0, 0.0, 100.0, *sensors])
    df = pd.DataFrame(rows, columns=RAW_COLUMNS)
    df["sensor_1"] = 518.67  # constant, like the real dataset
    return df


@pytest.fixture
def engines():
    return make_engines()
