"""Check an uploaded dataset before any processing happens."""

import pandas as pd

from src.config import ID_COLS
from src.errors import InvalidDataError


def validate_dataset(df, sensors):
    """Raise InvalidDataError for problems that block analysis; return a report with warnings."""
    if df.empty:
        raise InvalidDataError("The dataset has no rows.")

    required = ID_COLS + list(sensors)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise InvalidDataError(f"Missing required columns: {', '.join(missing)}")

    numeric = df[required].apply(pd.to_numeric, errors="coerce")
    empty_cols = [c for c in required if numeric[c].isna().all()]
    if empty_cols:
        raise InvalidDataError(f"Columns with no numeric values: {', '.join(empty_cols)}")

    warnings = []
    bad_values = int(numeric.isna().sum().sum() - df[required].isna().sum().sum())
    if bad_values:
        warnings.append(f"{bad_values} non-numeric values will be treated as missing.")
    missing_values = int(df[required].isna().sum().sum())
    if missing_values:
        warnings.append(f"{missing_values} missing values will be filled.")
    duplicates = int(df.duplicated(subset=ID_COLS).sum())
    if duplicates:
        warnings.append(f"{duplicates} duplicate (unit, cycle) rows will be removed.")

    return {
        "rows": len(df),
        "units": int(numeric["unit"].nunique()),
        "warnings": warnings,
    }
