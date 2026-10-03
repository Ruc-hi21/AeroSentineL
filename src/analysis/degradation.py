"""Find which sensors carry a real degradation signal."""

import numpy as np
import pandas as pd

from src.config import CONSTANT_STD_THRESHOLD, ROLLING_WINDOW, SENSOR_COLS


def _monotonicity(series):  # private helper; call via score_sensors
    """1 = the smoothed signal only moves one way over a unit's life, 0 = no trend."""
    diffs = np.diff(series.rolling(ROLLING_WINDOW, min_periods=1).mean().to_numpy())
    if len(diffs) == 0:
        return 0.0
    return abs((diffs > 0).sum() - (diffs < 0).sum()) / len(diffs)


def score_sensors(df):
    """Per-sensor std, correlation with RUL and monotonicity (training data with a `rul` column)."""
    rows = []
    for sensor in SENSOR_COLS:
        std = df[sensor].std()
        constant = std < CONSTANT_STD_THRESHOLD
        rows.append({
            "sensor": sensor,
            "std": std,
            "corr_with_rul": 0.0 if constant else df[sensor].corr(df["rul"]),
            "monotonicity": 0.0 if constant else df.groupby("unit")[sensor].apply(_monotonicity).mean(),  # mean across units
            "kept": not constant,
        })
    return pd.DataFrame(rows).set_index("sensor")


def select_sensors(df):
    """Drop sensors that never change; return (kept sensor names, score table)."""
    scores = score_sensors(df)
    kept = scores.index[scores["kept"]].tolist()  # preserves original sensor column order
    return kept, scores
