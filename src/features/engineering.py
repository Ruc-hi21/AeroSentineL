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


def derive_channels(df, spec):
    """Add a component's derived channels. Battery: state of health against the cell's first discharges."""
    if spec.key == "battery" and "capacity_ah" in df:
        df = df.copy()
        start = df.groupby("unit")["capacity_ah"].transform(lambda s: s.iloc[:3].median())
        df["soh"] = df["capacity_ah"] / start * 100.0
    return df


def _window_slope(values, unit, cycle, window):
    """Causal least-squares slope of values against cycle over the last `window` rows of each unit."""
    aux = pd.DataFrame({"v": values, "x": cycle, "xv": values * cycle, "xx": cycle * cycle})
    m = aux.groupby(unit, sort=False).rolling(window, min_periods=4).mean().reset_index(level=0, drop=True).reindex(aux.index)
    var = m["xx"] - m["x"] ** 2
    return ((m["xv"] - m["v"] * m["x"]) / var.where(var > 1e-9)).fillna(0.0)


def extra_features(df, spec):
    """Component-specific model inputs beyond the generic sensor statistics (None for the turbofan).

    Names follow '<channel>__<statistic>' so explanations group them with their channel."""
    parts = []
    if spec.settings_as_features:
        parts.append(df[list(spec.settings)].astype(float).add_suffix(f"{SEP}setting"))
    if "soh" in df:
        # Fade extrapolation: cycles until state of health reaches end of life at the recent fade rate.
        unit, cycle = df["unit"], df["cycle"].astype(float)
        soh = df.groupby("unit", sort=False)["soh"].transform(lambda s: s.rolling(5, min_periods=1).median()) / 100.0
        eol = 0.8
        cols = {f"soh{SEP}margin": soh - eol}
        for w in (10, 20):
            slope = _window_slope(soh, unit, cycle, w)
            cols[f"soh{SEP}extrap{w}"] = np.clip((soh - eol) / np.maximum(-slope, 1e-4), 0, 300)
        parts.append(pd.DataFrame(cols, index=df.index))
    return pd.concat(parts, axis=1) if parts else None


def model_features(df, sensors, spec):
    """All model inputs: generic sensor statistics plus the component's extra features."""
    X = build_features(df, sensors)
    extra = extra_features(df, spec)
    return pd.concat([X, extra], axis=1) if extra is not None else X
