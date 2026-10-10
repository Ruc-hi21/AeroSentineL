"""Build per-minute bearing tables from the FEMTO-ST PRONOSTIA run-to-failure data (IEEE PHM 2012).

Each snapshot is 0.1 s of vibration (2560 samples at 25.6 kHz) on a horizontal and a vertical
accelerometer, taken every 10 s until the bearing failed (vibration above 20 g). Each snapshot
is reduced to standard condition-monitoring features per axis, and the six snapshots of every
minute are averaged into one row.
"""

import io
import zipfile

import numpy as np
import pandas as pd

FS = 25600.0  # sampling rate, Hz
BANDS = ((0, 1000), (1000, 3000), (3000, 6000), (6000, 12800))  # Hz
SNAPSHOTS_PER_MINUTE = 6
# PRONOSTIA operating conditions: shaft speed (rpm) and radial load (kN)
CONDITIONS = {1: (1800.0, 4.0), 2: (1650.0, 4.2), 3: (1500.0, 5.0)}


def axis_features(x, prefix):
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x * x)))
    peak = float(np.max(np.abs(x)))
    sd = x.std() or 1e-12
    z = x / sd
    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1.0 / FS)
    out = {f"{prefix}_rms": rms, f"{prefix}_peak": peak, f"{prefix}_kurt": float(np.mean(z ** 4)),
           f"{prefix}_skew": float(np.mean(z ** 3)), f"{prefix}_crest": peak / (rms or 1e-12)}
    total = spec.sum() or 1e-12
    for k, (lo, hi) in enumerate(BANDS, start=1):
        band = spec[(freqs >= lo) & (freqs < hi)].sum()
        out[f"{prefix}_band{k}"] = float(np.sqrt(band * 2) / len(x))  # band RMS, g
    out[f"{prefix}_centroid_khz"] = float((freqs * spec).sum() / total / 1000.0)
    return out


def _read_snapshot(raw):
    text = raw.decode("ascii", errors="ignore")
    sep = ";" if ";" in text.split("\n", 1)[0] else ","
    arr = pd.read_csv(io.StringIO(text), sep=sep, header=None).to_numpy(dtype=float)
    return arr[:, 4], arr[:, 5]


def read_bearing(zf, folder):
    """Per-minute feature rows for one bearing folder inside a FEMTO zip."""
    files = sorted(n for n in zf.namelist() if n.startswith(folder + "/") and n.split("/")[-1].startswith("acc_"))
    rows = []
    for k, name in enumerate(files):
        h, v = _read_snapshot(zf.read(name))
        rows.append({"snapshot": k + 1, **axis_features(h, "h"), **axis_features(v, "v")})
    df = pd.DataFrame(rows)
    df["minute"] = (df["snapshot"] - 1) // SNAPSHOTS_PER_MINUTE + 1
    return df.drop(columns="snapshot").groupby("minute", as_index=False).mean()


def build(femto_zip):
    """Per-minute table of every full run-to-failure bearing (learning set and full test set)."""
    outer = zipfile.ZipFile(femto_zip)
    frames = []
    for part, root in (("Training_set.zip", "Learning_set"), ("Validation_Set.zip", "Full_Test_Set")):
        zf = zipfile.ZipFile(io.BytesIO(outer.read(part)))
        folders = sorted({n.split("/")[1] for n in zf.namelist() if n.count("/") >= 2 and n.split("/")[1].startswith("Bearing")})
        for folder in folders:
            cond, idx = (int(x) for x in folder.replace("Bearing", "").split("_"))
            df = read_bearing(zf, f"{root}/{folder}")
            speed, load = CONDITIONS[cond]
            df.insert(0, "bearing", cond * 10 + idx)
            df.insert(2, "speed_rpm", speed)
            df.insert(3, "load_kn", load)
            frames.append(df)
            print(f"  {folder}: {len(df)} minutes", flush=True)
    return pd.concat(frames, ignore_index=True)
