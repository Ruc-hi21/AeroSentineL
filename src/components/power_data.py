"""Build per-minute IGBT tables from the NASA PCoE IGBT accelerated-ageing data (thermal overstress).

Each device (IRG4BC30K, TO-220) was switched with a square gate signal while its package was held
above its rated temperature until it failed (latch-up). Every 20 to 30 s a high-speed oscilloscope
captured 2 ms of gate-emitter voltage, collector-emitter voltage and collector current; a slower
logger recorded package and heat-sink temperature. Each capture is reduced to switching features,
joined to the temperature at that moment, and averaged per minute of ageing. Sessions of the same
device ("Device4" and "Device4b") are joined on ageing time, gaps removed.

The DC-gate device has no switching captures, and the April A17 run's captures carry no timestamps
(so they cannot be placed on the ageing clock); neither is used, which leaves four devices.
Known limitations of the recordings (from NASA's readme): some captures are missing, the current
sensor drifts by about 0.6 A, and the slow logger's temperatures are not scaled properly; they are
used as relative trends only.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio

SQUARE_SMU = "Thermal Overstress Aging with Square Signal at gate and SMU data/Aging Data"
DEVICES = {  # device id -> session files in ageing order
    2: [f"{SQUARE_SMU}/Device 2/Device2  1.mat", f"{SQUARE_SMU}/Device 2/Device2b  1.mat"],
    3: [f"{SQUARE_SMU}/Device 3/Device3  1.mat", f"{SQUARE_SMU}/Device 3/Device3b  1.mat"],
    4: [f"{SQUARE_SMU}/Device 4/Device4  1.mat", f"{SQUARE_SMU}/Device 4/Device4b  1.mat"],
    5: [f"{SQUARE_SMU}/Device 5/Device5  1.mat"],
}
MAX_GAP_S = 120  # a pause longer than this between captures is removed from the ageing clock


def _f(x):
    return np.asarray(x, dtype=float).ravel()


def capture_features(td):
    """Switching features of one 2 ms oscilloscope capture."""
    vge, vce, ice = _f(td.gateEmitterVoltage), _f(td.collectorEmitterVoltage), _f(td.collectorEmitterCurrentSignal)
    dt = float(td.dt)
    if vge.size < 1000 or not np.isfinite(vge).any():
        return None
    hi = np.nanpercentile(vge, 95)
    on = vge > 0.6 * hi
    off = vge < 0.2 * hi
    if on.sum() < 100 or off.sum() < 100:
        return None
    # edges of the gate signal and the collector-voltage response after each turn-off
    edges_off = np.flatnonzero(on[:-1] & ~on[1:])
    v_on, v_off = np.nanmedian(vce[on]), np.nanmedian(vce[off])
    swing = v_off - v_on
    t_off = []
    for e in edges_off[:4]:
        seg = vce[e:e + int(50e-6 / dt)]
        if seg.size < 10 or swing <= 0:
            continue
        lo_i = np.argmax(seg > v_on + 0.1 * swing)
        hi_i = np.argmax(seg > v_on + 0.9 * swing)
        if hi_i > lo_i:
            t_off.append((hi_i - lo_i) * dt * 1e6)
    return {
        "vce_on": float(v_on), "vce_off": float(v_off), "vce_ripple": float(np.nanstd(vce[on])),
        "vge_on": float(np.nanmedian(vge[on])), "ice_on": float(np.nanmedian(ice[on])),
        "t_off_us": float(np.median(t_off)) if t_off else np.nan,
    }


def _steady(m):
    """Package and heat-sink temperature with their epoch times (field spellings differ by file)."""
    ss = np.atleast_1d(m.steadyState)
    t, pkg, hs = [], [], []
    for s in ss:
        td = s.timeDomain
        ep = float(getattr(s, "timeEpoch", 0) or 0)
        if ep <= 0:
            continue
        p = getattr(td, "packageTemperature", getattr(td, "packageTempurature", np.nan))
        h = getattr(td, "heatSinkTemperature", getattr(td, "heatSinkTempurature", np.nan))
        t.append(ep); pkg.append(float(np.nanmean(_f(p))) if np.size(p) else np.nan)
        hs.append(float(np.nanmean(_f(h))) if np.size(h) else np.nan)
    return np.array(t), np.array(pkg), np.array(hs)


def read_session(path):
    m = sio.loadmat(path, squeeze_me=True, struct_as_record=False)["measurement"]
    st, pkg, hs = _steady(m)
    rows = []
    for tr in np.atleast_1d(m.transient):
        ep = float(getattr(tr, "timeEpoch", getattr(tr, "timeSinceEpoch", 0)) or 0)
        feats = capture_features(tr.timeDomain)
        if feats is None or ep <= 0:
            continue
        if st.size:
            k = np.searchsorted(st, ep).clip(1, st.size - 1)
            win = slice(max(0, k - 20), k + 20)
            feats["pkg_temp"] = float(np.nanmedian(pkg[win]))
            feats["sink_temp"] = float(np.nanmedian(hs[win]))
        rows.append({"epoch": ep, **feats})
    return pd.DataFrame(rows)


def read_device(root, files):
    parts = [read_session(Path(root) / f) for f in files]
    df = pd.concat([p for p in parts if len(p)], ignore_index=True).sort_values("epoch")
    gaps = df["epoch"].diff().fillna(0).to_numpy().copy()
    gaps[gaps > MAX_GAP_S] = 0  # remove pauses between sessions from the ageing clock
    df["age_s"] = np.cumsum(gaps)
    df["minute"] = (df["age_s"] // 60).astype(int) + 1
    out = df.drop(columns=["epoch", "age_s"]).groupby("minute", as_index=False).mean()
    out["r_on"] = out["vce_on"] / out["ice_on"].where(out["ice_on"].abs() > 0.1)
    # Heat-sink readings are constant (logger scaling) and turn-off times are mostly missing: not used.
    return out.drop(columns=["sink_temp", "t_off_us"], errors="ignore").round(5)


def build(root):
    """Per-minute table of every square-gate device, keyed device / minute."""
    tables = []
    for dev, files in DEVICES.items():
        d = read_device(root, files)
        d.insert(0, "device", dev)
        tables.append(d)
    return pd.concat(tables, ignore_index=True)
