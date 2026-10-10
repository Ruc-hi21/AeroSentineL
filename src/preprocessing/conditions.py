"""Operating-condition correction.

FD002 and FD004 engines fly through six operating conditions (altitude, Mach number, throttle
resolver angle). Most readings change far more with the condition than with wear, so every
reading is mapped to the value it would show at a reference condition: sea level, Mach 0,
full throttle, the point FD001 and FD003 run at. Per condition c and sensor, from training data:

    corrected = (reading - mean_c) / std_c * std_ref + mean_ref

With a single condition this is the identity, so FD001 and FD003 readings are left untouched.
The same correction serves other components through their own settings: battery cells by
ambient temperature and discharge current, bearings by shaft speed and radial load.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from src.config import SEED, SENSOR_COLS, SETTING_COLS

REFERENCE_SETTINGS = np.array([0.0, 0.0, 100.0])  # altitude (kft), Mach, throttle resolver angle
# The settings span very different ranges, so scale them before measuring distances.
SETTING_SCALE = np.array([42.0, 0.84, 40.0])
UNKNOWN_DISTANCE = 0.1  # scaled distance beyond which a reading's condition was never trained on
MIN_STD = 1e-6


def _scaled(df, settings=SETTING_COLS, scale=SETTING_SCALE):
    return df[list(settings)].to_numpy(dtype=float) / np.asarray(scale, dtype=float)


class ConditionNormalizer:
    # Defaults keep models saved before settings were configurable (turbofan) loading.
    settings = tuple(SETTING_COLS)
    scale = SETTING_SCALE
    reference_settings = REFERENCE_SETTINGS

    def fit(self, df, n_conditions=None, sensors=SENSOR_COLS, settings=SETTING_COLS, scale=SETTING_SCALE,
            reference=REFERENCE_SETTINGS):
        """Learn the operating conditions and per-condition sensor statistics from training data.

        n_conditions None counts them in the data."""
        self.sensors = list(sensors)
        self.settings, self.scale = tuple(settings), np.asarray(scale, dtype=float)
        self.reference_settings = np.asarray(reference, dtype=float)
        if n_conditions is None:
            n_conditions = count_conditions(df, self.settings, self.scale)
        settings = _scaled(df, self.settings, self.scale)
        if n_conditions > 1:
            km = KMeans(n_clusters=n_conditions, n_init=10, random_state=SEED).fit(settings)
            centers = km.cluster_centers_
        else:
            centers = np.median(settings, axis=0, keepdims=True)
        # Condition ids 1..n in order of altitude, then Mach, so they read like a flight envelope.
        order = np.lexsort((centers[:, 1], centers[:, 0]))
        self.centers = centers[order]
        self.ids = np.arange(1, len(order) + 1)
        labels = self._nearest(settings)[0]

        stats = df[self.sensors].groupby(labels)
        self.mean = stats.mean().reindex(self.ids)
        self.std = stats.std().reindex(self.ids).fillna(0.0)
        self.counts = pd.Series(labels).value_counts().reindex(self.ids, fill_value=0)
        self.reference = int(self.ids[np.argmin(np.linalg.norm(self.centers - self.reference_settings / self.scale, axis=1))])
        return self

    @property
    def n_conditions(self):
        return len(self.ids)

    def _nearest(self, settings):
        dist = np.linalg.norm(settings[:, None, :] - self.centers[None, :, :], axis=2)
        return self.ids[dist.argmin(axis=1)], dist.min(axis=1)

    def assign(self, df):
        """(condition id per row, True where the row's condition was seen in training)."""
        if self.n_conditions == 1 and not set(self.settings) <= set(df.columns):
            return np.ones(len(df), dtype=int), np.ones(len(df), dtype=bool)
        labels, dist = self._nearest(_scaled(df, self.settings, self.scale))
        return labels, dist <= UNKNOWN_DISTANCE

    def transform(self, df):
        """Return a copy with condition-corrected sensors plus `condition` and `condition_known`."""
        df = df.copy()
        labels, known = self.assign(df)
        df["condition"], df["condition_known"] = labels, known
        if self.n_conditions == 1:
            return df
        ref_mean, ref_std = self.mean.loc[self.reference], self.std.loc[self.reference]
        mean = self.mean.loc[labels].to_numpy()
        std = self.std.loc[labels].to_numpy()
        ratio = np.divide(ref_std.to_numpy(), std, out=np.zeros_like(std), where=std > MIN_STD)
        values = df[self.sensors].to_numpy(dtype=float)
        df[self.sensors] = (values - mean) * ratio + ref_mean.to_numpy()
        return df

    def describe(self):
        """One dict per condition: id, settings in engineering units, training share, reference flag.

        Turbofan conditions also carry altitude_kft, mach and throttle."""
        centers = self.centers * self.scale
        total = max(int(self.counts.sum()), 1)
        out = []
        for i, c in zip(self.ids, centers):
            row = {"id": int(i), "settings": {k: round(float(v), 3) for k, v in zip(self.settings, c)},
                   "share": round(int(self.counts[i]) / total, 3), "reference": int(i) == self.reference}
            if tuple(self.settings) == tuple(SETTING_COLS):
                row.update(altitude_kft=round(float(c[0]), 1), mach=round(float(c[1]), 2), throttle=round(float(c[2]), 0))
            out.append(row)
        return out


def identity_normalizer(sensors=SENSOR_COLS):
    """Stand-in for models trained before condition correction existed (single condition)."""
    norm = ConditionNormalizer()
    norm.sensors = list(sensors)
    norm.centers = REFERENCE_SETTINGS[None, :] / SETTING_SCALE
    norm.ids = np.array([1])
    norm.mean = norm.std = None
    norm.counts = pd.Series([1], index=norm.ids)
    norm.reference = 1
    return norm


def count_conditions(df, settings=SETTING_COLS, scale=SETTING_SCALE, tolerance=UNKNOWN_DISTANCE):
    """How many distinct operating conditions a raw file contains (cheap greedy grouping)."""
    settings = list(settings)
    if not set(settings) <= set(df.columns):
        return 1
    values = df[settings].apply(pd.to_numeric, errors="coerce").dropna()
    if values.empty:
        return 1
    points = np.unique(np.round(values.to_numpy(dtype=float) / np.asarray(scale, dtype=float), 2), axis=0)
    centers = []
    for p in points:
        if not centers or np.min(np.linalg.norm(np.array(centers) - p, axis=1)) > tolerance:
            centers.append(p)
    return len(centers)
