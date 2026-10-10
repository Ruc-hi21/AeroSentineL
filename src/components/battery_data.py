"""Build per-cycle battery tables from the NASA PCoE Li-ion ageing data (.mat files).

Each discharge cycle becomes one row: capacity, timing, voltage and temperature features of that
discharge, timings of the charge before it, and the latest impedance estimate. Glitch cycles
(capacity at or near zero, or far off the cell's running median) are dropped, cells with too few
valid cycles are left out.
"""

import glob
import os

import numpy as np
import pandas as pd

GLITCH_AH = 0.1  # a discharge this far from the 5-cycle median capacity is a logging glitch
MIN_VALID_CYCLES = 20
EOL_SOH = 0.8  # end of life: capacity below 80% of the cell's starting capacity


def _arr(x):
    return np.atleast_1d(np.asarray(x, dtype=float)).ravel()


def _discharge_features(d):
    t, v, i, temp = _arr(d["Time"]), _arr(d["Voltage_measured"]), _arr(d["Current_measured"]), _arr(d["Temperature_measured"])
    cap = _arr(d.get("Capacity", np.nan))[0] if np.size(d.get("Capacity", [])) else np.nan
    if len(t) < 10:
        return None
    dur = t[-1] - t[0]
    loaded = np.abs(i) > 0.5
    mid = (t >= t[0] + 0.2 * dur) & (t <= t[0] + 0.8 * dur)
    slope = np.polyfit(t[mid] / 60.0, v[mid], 1)[0] if mid.sum() > 5 else np.nan
    k = int(np.nanargmax(temp))
    return {
        "load_a": float(np.median(np.abs(i[loaded]))) if loaded.any() else np.nan,
        "capacity_ah": float(cap),
        "discharge_min": dur / 60.0,
        "v_start": float(v[loaded][0]) if loaded.any() else float(v[0]),
        "v_mean": float(np.mean(v[loaded])) if loaded.any() else float(np.mean(v)),
        "dvdt_mid": float(slope) * 1000.0,  # mV per minute
        "temp_max_c": float(temp[k]),
        "temp_rise_c": float(temp[k] - temp[0]),
        "t_tmax_min": float((t[k] - t[0]) / 60.0),
    }


def _charge_features(d):
    t, v, i, temp = _arr(d["Time"]), _arr(d["Voltage_measured"]), _arr(d["Current_measured"]), _arr(d["Temperature_measured"])
    if len(t) < 10:
        return {}
    cv = np.nonzero(v >= 4.19)[0]  # constant current until the cell reaches 4.2 V, then constant voltage
    t_cc = (t[cv[0]] - t[0]) / 60.0 if len(cv) else np.nan
    t_cv = (t[-1] - t[cv[0]]) / 60.0 if len(cv) else np.nan
    return {"cc_charge_min": float(t_cc), "cv_charge_min": float(t_cv), "charge_temp_max_c": float(np.nanmax(temp))}


def _impedance(d):
    out = {}
    for src, dst in (("Re", "re_ohm"), ("Rct", "rct_ohm")):
        if src in d and np.size(d[src]):
            val = np.atleast_1d(d[src]).ravel()[0]
            val = float(np.real(val))
            if np.isfinite(val) and 0 < val < 1:
                out[dst] = val
    return out


def read_cell(path):
    """All discharge cycles of one cell (one row each), before glitch filtering."""
    from scipy.io import loadmat

    name = os.path.basename(path)[:-4]
    cycles = loadmat(path, simplify_cells=True)[name]["cycle"]
    rows, charge, imp, n = [], {}, {}, 0
    for c in cycles:
        kind, d = c["type"], c["data"]
        if kind == "charge":
            charge = _charge_features(d)
        elif kind == "impedance":
            imp.update(_impedance(d))
        elif kind == "discharge":
            n += 1
            f = _discharge_features(d)
            if f is None:
                continue
            rows.append({"cell": int(name[1:]), "cycle": n, "ambient_c": float(c["ambient_temperature"]),
                         **f, **charge, **imp})
    return pd.DataFrame(rows)


def clean_cell(df):
    """Drop glitch discharges and add state of health and end of life. Returns (rows, eol cycle or None)."""
    df = df[df["capacity_ah"] > 0.3].copy()
    med = df["capacity_ah"].rolling(5, center=True, min_periods=1).median()
    df = df[(df["capacity_ah"] - med).abs() < GLITCH_AH]
    if len(df) < MIN_VALID_CYCLES:
        return None, None
    start = df["capacity_ah"].iloc[:3].median()
    soh = df["capacity_ah"].rolling(3, min_periods=1).median() / start
    below = df.loc[soh < EOL_SOH, "cycle"]
    return df.reset_index(drop=True), (int(below.iloc[0]) if len(below) else None)


def build(mat_dir):
    """Clean per-cycle table of every usable cell, plus {cell: end-of-life cycle or None}."""
    frames, eol = [], {}
    for path in sorted(glob.glob(os.path.join(mat_dir, "B00*.mat"))):
        df, end = clean_cell(read_cell(path))
        if df is None:
            continue
        cell = int(df["cell"].iloc[0])
        eol[cell] = end
        frames.append(df)
    table = pd.concat(frames, ignore_index=True)
    table["load_a"] = table.groupby("cell")["load_a"].transform("median").round(1)  # one load per cell
    table["ambient_c"] = table["ambient_c"].round(0)
    for col in ("re_ohm", "rct_ohm", "cc_charge_min", "cv_charge_min", "charge_temp_max_c"):
        if col in table:
            table[col] = table.groupby("cell")[col].transform(lambda s: s.ffill().bfill())
    return table, eol
