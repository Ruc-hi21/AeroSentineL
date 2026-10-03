"""Component health: a single health score per cycle and a normal/abnormal flag.

The score measures how far a unit's sensors have drifted from the healthy
baseline (the first cycles of every training engine), in the direction that
degradation pushes each sensor. 0 = like a new engine, higher = more degraded.
"""

import numpy as np

from src.config import ABNORMAL_QUANTILE, BASELINE_CYCLES, HEALTH_SMOOTHING, RANGE_MARGIN


class HealthAnalyzer:
    def fit(self, train_df, sensors):
        """Learn the healthy baseline from training data that has a `rul` column."""
        self.sensors = list(sensors)
        baseline = train_df[train_df["cycle"] <= BASELINE_CYCLES]
        self.mean = baseline[self.sensors].mean()
        self.std = baseline[self.sensors].std().replace(0, 1)  # avoid zero division for constant sensors
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
