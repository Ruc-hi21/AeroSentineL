"""Turn a validated dataset into a clean, sorted, fully numeric table."""

import pandas as pd

from src.config import ID_COLS, RAW_COLUMNS
from src.errors import InvalidDataError


def clean_data(df):
    """Coerce types, drop unusable/duplicate rows, fill gaps per unit. Returns (df, report)."""
    df = df[[c for c in RAW_COLUMNS if c in df.columns]].apply(pd.to_numeric, errors="coerce")
    rows_in = len(df)

    df = df.dropna(subset=ID_COLS)  # rows where unit or cycle is NaN are unidentifiable
    df = df[df["cycle"] >= 1]
    dropped_invalid = rows_in - len(df)

    df = df.astype({"unit": int, "cycle": int})  # ensure integer keys for groupby consistency
    before = len(df)
    df = df.drop_duplicates(subset=ID_COLS, keep="first")
    dropped_duplicates = before - len(df)

    df = df.sort_values(ID_COLS).reset_index(drop=True)  # chronological order within each unit
    value_cols = [c for c in df.columns if c not in ID_COLS]
    filled = int(df[value_cols].isna().sum().sum())  # count NaNs before filling
    df[value_cols] = df.groupby("unit")[value_cols].transform(lambda s: s.ffill().bfill())
    df[value_cols] = df[value_cols].fillna(df[value_cols].median())  # fallback: dataset-wide median

    if df.empty:
        raise InvalidDataError("No usable rows left after cleaning.")

    report = {
        "rows_in": rows_in,
        "rows_out": len(df),
        "dropped_invalid_rows": dropped_invalid,
        "dropped_duplicates": dropped_duplicates,
        "filled_values": filled,
    }
    return df, report
