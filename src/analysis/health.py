"""Component health: a single health score per cycle and a normal/abnormal flag.

The score measures how far a unit's sensors have drifted from the healthy
baseline (the first cycles of every training engine), in the direction that
degradation pushes each sensor. 0 = like a new engine, higher = more degraded.
"""

import numpy as np
import pandas as pd

from src.config import (
    ABNORMAL_QUANTILE, BASELINE_CYCLES, CRITICAL_HEALTH_MULTIPLE, HEALTH_SMOOTHING, RANGE_MARGIN,
)


class HealthAnalyzer:
    def fit(self, train_df, sensors, baseline_cycles=BASELINE_CYCLES):
        """Learn the healthy baseline from training data that has a `rul` column."""
        self.sensors = list(sensors)
        if baseline_cycles > 0:
            baseline = train_df[train_df["cycle"] <= baseline_cycles]
        else:  # condition-labelled data (hydraulic): healthy = every row at the full target
            baseline = train_df[train_df["rul"] >= train_df["rul"].max()]
        self.mean = baseline[self.sensors].mean()
        span_all = train_df[self.sensors].max() - train_df[self.sensors].min()
        # Noise floor: 2% of the sensor's training span, so a near noise-free healthy baseline (the hydraulic
        # rig's steady load cycles) does not turn small shifts into hundreds of sigma. Zero spans fall back to 1.
        self.std = baseline[self.sensors].std().clip(lower=0.02 * span_all).replace(0, 1)
        # +1 if the sensor rises as RUL falls, -1 if it drops.
        self.direction = -np.sign(train_df[self.sensors].corrwith(train_df["rul"]))

        span = train_df[self.sensors].max() - train_df[self.sensors].min()
        self.low = train_df[self.sensors].min() - RANGE_MARGIN * span
        self.high = train_df[self.sensors].max() + RANGE_MARGIN * span

        self.threshold = float(self.health_score(baseline).quantile(ABNORMAL_QUANTILE))
        return self

    def sensor_deviation(self, df):
        """Directed z-score of each sensor vs. the healthy baseline (positive = degrading)."""
        return (df[self.sensors] - self.mean) / self.std * self.direction

    def health_score(self, df):
        raw = self.sensor_deviation(df).mean(axis=1)
        return raw.groupby(df["unit"]).transform(
            lambda s: s.rolling(HEALTH_SMOOTHING, min_periods=1).mean()
        )

    def transform(self, df):
        """Add health_score, health_condition and out_of_range columns."""
        df = df.copy()
        df["health_score"] = self.health_score(df)
        df["health_condition"] = np.where(df["health_score"] > self.threshold, "abnormal", "normal")
        readings = df[self.sensors]  # extract once for both low/high comparisons
        df["out_of_range"] = ((readings < self.low) | (readings > self.high)).any(axis=1)
        return df


def compute_fleet_health_distribution(scores: pd.Series, threshold: float) -> dict:
    """Count units as normal / degraded / critical from their health scores.

    Higher score = more degraded. `threshold` is the trained abnormal threshold
    (HealthAnalyzer.threshold): normal <= threshold < degraded <= CRITICAL_HEALTH_MULTIPLE
    x threshold < critical.
    """
    critical_limit = CRITICAL_HEALTH_MULTIPLE * threshold
    return {
        "normal": int((scores <= threshold).sum()),
        "degraded": int(((scores > threshold) & (scores <= critical_limit)).sum()),
        "critical": int((scores > critical_limit).sum()),
    }
