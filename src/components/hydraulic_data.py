"""Build the per-cycle hydraulic table from the UCI 'Condition monitoring of hydraulic systems' files.

Each raw file is one sensor: 2205 rows (60 s load cycles) by its samples within the cycle (100, 10 or
1 Hz). A cycle becomes one row: every sensor's mean, plus PS2 and FS1 in six 10-second windows.
Consecutive cycles at the same cooler / valve / pump / accumulator setting form a session (the unit).
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.components.hydraulic import HYDRAULIC, WINDOWS, margin

RAW = ["PS1", "PS2", "PS3", "PS4", "PS5", "PS6", "EPS1", "FS1", "FS2", "TS1", "TS2", "TS3", "TS4", "VS1", "CE", "CP", "SE"]
PROFILED = ("PS2", "FS1")
LABELS = ["cooler", "valve", "pump", "accumulator", "stable"]


def build(folder):
    folder = Path(folder)
    rows = {}
    for name in RAW:
        a = np.loadtxt(folder / f"{name}.txt")
        rows[name.lower()] = a.mean(axis=1)
        if name in PROFILED:
            for i, ix in enumerate(np.array_split(np.arange(a.shape[1]), WINDOWS)):
                rows[f"{name.lower()}_w{i}"] = a[:, ix].mean(axis=1)
    df = pd.DataFrame(rows)
    labels = pd.read_csv(folder / "profile.txt", sep="\t", header=None, names=LABELS)
    df = pd.concat([labels, df], axis=1)
    # A session: consecutive cycles at one setting. A block: one cooler and accumulator setting.
    setting = df[["cooler", "valve", "pump", "accumulator"]]
    df.insert(0, "session", (setting.diff().abs().sum(axis=1) > 0).cumsum() + 1)
    df.insert(1, "cycle", df.groupby("session").cumcount() + 1)
    df["block"] = (df[["cooler", "accumulator"]].diff().abs().sum(axis=1) > 0).cumsum()
    df["margin"] = [round(margin(c, v, p), 2) for c, v, p in zip(df["cooler"], df["valve"], df["pump"])]
    assert set(HYDRAULIC.channel_keys) <= set(df.columns)
    return df.round({k: 4 for k in HYDRAULIC.channel_keys})
