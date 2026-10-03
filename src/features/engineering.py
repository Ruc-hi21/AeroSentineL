"""Model inputs: raw sensor values plus rolling statistics per engine unit."""

import pandas as pd

from src.config import ROLLING_WINDOW


def feature_names(sensors):
    return (
        ["cycle"]
        + list(sensors)
        + [f"{s}_mean" for s in sensors]
        + [f"{s}_std" for s in sensors]
    )


def build_features(df, sensors, window=ROLLING_WINDOW):
    """One feature row per input row. Works for units with very few cycles."""
    rolling = df.groupby("unit")[list(sensors)].rolling(window, min_periods=1)
    mean = rolling.mean().reset_index(level=0, drop=True).add_suffix("_mean")
    std = rolling.std().reset_index(level=0, drop=True).fillna(0).add_suffix("_std")
    features = pd.concat([df[["cycle"] + list(sensors)], mean, std], axis=1)
    return features[feature_names(sensors)]


def sensor_of(feature):
    """Map a feature back to the sensor it came from, e.g. 'sensor_11_mean' -> 'sensor_11'."""
    for suffix in ("_mean", "_std"):
        if feature.endswith(suffix):
            return feature[: -len(suffix)]
    return feature
