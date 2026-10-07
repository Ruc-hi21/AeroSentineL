"""Model inputs: raw sensors plus multi-scale rolling stats, trends and drift per engine unit.

Every feature is causal: the value at cycle t only uses cycles <= t of the same unit, so a
prediction never looks into that engine's future. Feature names are "<sensor>__<statistic>".
"""

import numpy as np
import pandas as pd

from src.config import BASELINE_CYCLES_PER_UNIT, DRIFT_SMOOTHING, EWM_ALPHAS, ROLLING_WINDOWS, SLOPE_WINDOWS

SEP = "__"


def feature_names(sensors):
    names = ["cycle"] + list(sensors)
    for s in sensors:
        names += [f"{s}{SEP}mean{w}" for w in ROLLING_WINDOWS]
        names += [f"{s}{SEP}std{w}" for w in ROLLING_WINDOWS]
        names += [f"{s}{SEP}ewm{a}" for a in EWM_ALPHAS]
        names += [f"{s}{SEP}slope{w}" for w in SLOPE_WINDOWS]
        names.append(f"{s}{SEP}drift")
    return names


def _flat(per_group):
    """groupby().rolling/ewm/expanding results carry (unit, row) index; keep only the row label."""
    return per_group.reset_index(level=0, drop=True)


def _slopes(df, sensors, unit):
    """Least-squares slope of each sensor against cycle over the last w cycles of its unit."""
    x = df["cycle"].astype(float)
    aux = pd.concat([df[sensors], df[sensors].mul(x, axis=0).add_suffix("_xy")], axis=1).assign(_x=x, _xx=x * x)
    grouped = aux.groupby(unit, sort=False)
    frames = []
    for w in SLOPE_WINDOWS:
        m = _flat(grouped.rolling(w, min_periods=2).mean())
        var = (m["_xx"] - m["_x"] ** 2).to_numpy()
        cov = m[[f"{s}_xy" for s in sensors]].to_numpy() - m[sensors].to_numpy() * m["_x"].to_numpy()[:, None]
        with np.errstate(divide="ignore", invalid="ignore"):
            slope = np.where(var[:, None] > 1e-9, cov / var[:, None], 0.0)
        frames.append(pd.DataFrame(slope, index=m.index, columns=[f"{s}{SEP}slope{w}" for s in sensors]))
    return frames


def build_features(df, sensors):
    """One feature row per input row (same index and order). Works for units with very few cycles."""
    sensors = list(sensors)
    unit = df["unit"]
    grouped = df.groupby("unit", sort=False)[sensors]
    frames = [df[["cycle"] + sensors]]

    for w in ROLLING_WINDOWS:
        rolling = grouped.rolling(w, min_periods=1)
        frames.append(_flat(rolling.mean()).add_suffix(f"{SEP}mean{w}"))
        frames.append(_flat(rolling.std()).fillna(0).add_suffix(f"{SEP}std{w}"))  # 0 for 1-row windows
    for a in EWM_ALPHAS:
        frames.append(_flat(grouped.ewm(alpha=a).mean()).add_suffix(f"{SEP}ewm{a}"))
    frames += _slopes(df, sensors, unit)

    # Drift from the unit's own early life: removes engine-to-engine manufacturing offsets.
    early = _flat(grouped.expanding().mean())
    early[grouped.cumcount().reindex(early.index).to_numpy() >= BASELINE_CYCLES_PER_UNIT] = np.nan
    baseline = early.groupby(unit.reindex(early.index)).ffill()
    smooth = _flat(grouped.rolling(DRIFT_SMOOTHING, min_periods=1).mean())
    frames.append((smooth - baseline.reindex(smooth.index)).add_suffix(f"{SEP}drift"))

    features = pd.concat(frames, axis=1).reindex(df.index)
    return features[feature_names(sensors)]


def sensor_of(feature):
    """Map a feature back to the sensor it came from, e.g. 'sensor_11__slope30' -> 'sensor_11'."""
    if SEP in feature:
        return feature.split(SEP, 1)[0]
    for suffix in ("_mean", "_std"):  # v1 feature names
        if feature.endswith(suffix):
            return feature[: -len(suffix)]
    return feature
