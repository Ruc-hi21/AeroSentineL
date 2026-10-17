"""Write battery, gearbox, hydraulic and power-electronics data in the same shape as NASA C-MAPSS.

train_<profile>.csv  every training unit, run until end of life
test_<profile>.csv   held-out units cut off at a random point before end of life
RUL_<profile>.txt    true remaining life of each test unit at its cut-off, one per line

Files use the component's upload columns (e.g. cell, cycle, ambient_c, load_a, capacity_ah, ...),
so they double as sample files for the console.
"""

import numpy as np
import pandas as pd

from src.components import get
from src.config import SEED

# Held-out units, chosen to cover each operating condition that has more than one unit.
BATTERY_TEST_CELLS = (6, 34, 44, 47)
BATTERY_EXCLUDED = (41, 49, 51)  # too few valid discharges, or end of life within 8 cycles of the start
BEARING_TEST = (13, 17, 24, 26, 33)  # Bearing1_3, 1_7, 2_4, 2_6, 3_3
CUT_RANGE = (0.3, 0.9)  # test units stop between 30% and 90% of their life
# Hydraulic: hold out whole blocks (one cooler and accumulator setting each), one per cooler level,
# so test sessions come from setting combinations the model never saw.
HYDRAULIC_TEST_BLOCKS = (2, 6, 10)
POWER_TEST = (3,)  # IGBT device 3


def _cut(df, units, rng):
    """Truncate each test unit at a random point; return (truncated rows, true RUL per unit in unit order)."""
    parts, rul = [], []
    for u in units:
        part = df[df["unit"] == u].sort_values("cycle")
        life = int(part["cycle"].max())
        k = int(rng.uniform(*CUT_RANGE) * len(part))
        kept = part.iloc[: max(k, 2)]
        parts.append(kept)
        rul.append(life - int(kept["cycle"].max()))
    return pd.concat(parts), rul


def _write(spec, profile, train, test, rul, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    rename = {"unit": spec.id_column, "cycle": spec.time_column}
    cols = spec.upload_columns
    train.rename(columns=rename)[cols].to_csv(out_dir / f"train_{profile}.csv", index=False)
    test.rename(columns=rename)[cols].to_csv(out_dir / f"test_{profile}.csv", index=False)
    (out_dir / f"RUL_{profile}.txt").write_text("\n".join(str(r) for r in rul) + "\n")
    # Every unit, including ones that never reached end of life: extra examples for component recognition.
    return out_dir


def write_battery(table, eol, out_dir):
    spec = get("battery")
    df = table.rename(columns={"cell": "unit"})
    usable = [c for c, e in eol.items() if e and c not in BATTERY_EXCLUDED]
    df_life = pd.concat([df[(df["unit"] == c) & (df["cycle"] <= eol[c])] for c in usable])
    rng = np.random.default_rng(SEED)
    train = df_life[~df_life["unit"].isin(BATTERY_TEST_CELLS)]
    test, rul = _cut(df_life, [c for c in usable if c in BATTERY_TEST_CELLS], rng)
    _write(spec, "PCOE", train, test, rul, out_dir)
    # Sample fleet for the console: the held-out cells plus cells that never reached end of life.
    # The model saw none of them in training.
    unseen = df[~df["unit"].isin(set(eol) - set(BATTERY_TEST_CELLS)) | df["unit"].isin([c for c, e in eol.items() if not e])]
    sample = pd.concat([test, unseen[~unseen["unit"].isin(BATTERY_TEST_CELLS)]]).sort_values(["unit", "cycle"])
    sample.rename(columns={"unit": spec.id_column})[spec.upload_columns].to_csv(out_dir / "sample_PCOE.csv", index=False)
    return len(train["unit"].unique()), len(rul)


def write_bearing(table, out_dir):
    spec = get("bearing")
    df = table.rename(columns={"bearing": "unit", "minute": "cycle"})
    rng = np.random.default_rng(SEED)
    train = df[~df["unit"].isin(BEARING_TEST)]
    test, rul = _cut(df, [u for u in sorted(df["unit"].unique()) if u in BEARING_TEST], rng)
    _write(spec, "FEMTO", train, test, rul, out_dir)
    return len(train["unit"].unique()), len(rul)


def write_hydraulic(table, out_dir):
    """Sessions of the held-out blocks are the test set, whole (the target is a condition, not a life)."""
    spec = get("hydraulic")
    df = table.rename(columns={"session": "unit"})
    test_mask = df["block"].isin(HYDRAULIC_TEST_BLOCKS)
    train, test = df[~test_mask], df[test_mask]
    out_dir.mkdir(parents=True, exist_ok=True)
    rename = {"unit": spec.id_column, "cycle": spec.time_column}
    labels = spec.label_columns
    train.rename(columns=rename)[spec.upload_columns + labels].to_csv(out_dir / "train_UCI.csv", index=False)
    test.rename(columns=rename)[spec.upload_columns].to_csv(out_dir / "test_UCI.csv", index=False)
    last = test.groupby("unit").tail(1)
    (out_dir / "RUL_UCI.txt").write_text("\n".join(f"{m:g}" for m in last["margin"]) + "\n")
    test.rename(columns=rename)[[spec.id_column, spec.time_column, *labels]].to_csv(out_dir / "labels_UCI.csv", index=False)
    return train["unit"].nunique(), test["unit"].nunique()


def write_power(table, out_dir):
    spec = get("power")
    df = table.rename(columns={"device": "unit", "minute": "cycle"})
    rng = np.random.default_rng(SEED)
    train = df[~df["unit"].isin(POWER_TEST)]
    test, rul = _cut(df, [u for u in sorted(df["unit"].unique()) if u in POWER_TEST], rng)
    _write(spec, "IGBT", train, test, rul, out_dir)
    # Sample fleet for the console: every device, cut part-way, so each shows a different state.
    sample, _ = _cut(df, sorted(df["unit"].unique()), np.random.default_rng(SEED + 1))
    sample.rename(columns={"unit": spec.id_column, "cycle": spec.time_column})[spec.upload_columns].to_csv(
        out_dir / "sample_IGBT.csv", index=False)
    return train["unit"].nunique(), len(rul)


def sample_path(profile, samples_dir=None):
    """Path of a profile's one-unit sample file, e.g. data/samples/FD001_engine_034.txt."""
    from src.components import spec_of_profile
    from src.config import SAMPLE_UNITS, SAMPLES_DIR
    spec = spec_of_profile(profile)
    ext = "txt" if spec.key == "turbofan" else "csv"
    return (samples_dir or SAMPLES_DIR) / f"{profile}_{spec.unit_title.lower()}_{SAMPLE_UNITS[profile]:03d}.{ext}"


def write_samples(raw_dir, samples_dir):
    """One held-out test unit per profile (src.config.SAMPLE_UNITS), in the test file's own format.

    Returns {profile: (path, rows, true remaining life)} for the profiles whose test file exists.
    """
    from src.config import SAMPLE_UNITS
    samples_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for profile, unit in SAMPLE_UNITS.items():
        ext = "txt" if profile.startswith("FD") else "csv"
        source = raw_dir / f"test_{profile}.{ext}"
        if not source.exists():
            continue
        lines = source.read_text().splitlines()
        if ext == "txt":  # C-MAPSS: no header, unit id is the first field
            rows = [l for l in lines if l.strip() and int(float(l.split()[0])) == unit]
            body = rows
        else:  # header + rows, unit id in the first column
            rows = [l for l in lines[1:] if l.strip() and int(float(l.split(",")[0])) == unit]
            body = [lines[0], *rows]
        units = sorted({int(float((l.split() if ext == "txt" else l.split(","))[0])) for l in
                        (lines if ext == "txt" else lines[1:]) if l.strip()})
        true = (raw_dir / f"RUL_{profile}.txt").read_text().split()[units.index(unit)]
        path = sample_path(profile, samples_dir)
        path.write_text("\n".join(body) + "\n")
        written[profile] = (path, len(rows), float(true))
    return written
