"""RUL labels and the engine-unit train/validation split."""

import numpy as np

from src.config import RUL_CAP, SEED, TEST_SIZE


def add_rul(df, cap=RUL_CAP):
    """RUL = cycles left until the unit's last recorded cycle, capped at `cap`."""
    df = df.copy()  # avoid mutating the caller's DataFrame
    last_cycle = df.groupby("unit")["cycle"].transform("max")
    df["rul"] = (last_cycle - df["cycle"]).clip(upper=cap)
    return df


def split_by_unit(df, test_size=TEST_SIZE, seed=SEED):
    """Split whole engines (never individual cycles) into train and validation sets."""
    units = np.sort(df["unit"].unique())
    rng = np.random.default_rng(seed)
    val_units = rng.choice(units, size=max(1, round(len(units) * test_size)), replace=False)

    val_mask = df["unit"].isin(val_units)
    train, val = df[~val_mask].copy(), df[val_mask].copy()
    assert not set(train["unit"]) & set(val["unit"]), "Engine unit leaked across the split"
    return train, val
