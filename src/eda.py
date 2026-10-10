"""Exploratory profile of an uploaded table, computed before any model sees it.

Shape, missing values, duplicates, per-column statistics with a small histogram, outliers and
the most strongly related column pairs. The console shows it on the Ingest page.
"""

import numpy as np
import pandas as pd

HIST_BINS = 16
MAX_CORR_COLUMNS = 30
OUTLIER_Z = 4.0


def profile(df):
    num = df.apply(pd.to_numeric, errors="coerce")
    text_cols = [c for c in df.columns if num[c].isna().all() and df[c].notna().any()]
    columns = []
    for c in df.columns:
        s = num[c]
        valid = s.dropna()
        entry = {"name": str(c), "kind": "text" if c in text_cols else "numeric",
                 "missing": int(df[c].isna().sum()), "unique": int(df[c].nunique())}
        if len(valid):
            std = float(valid.std()) if len(valid) > 1 else 0.0
            counts, edges = np.histogram(valid, bins=HIST_BINS)
            z = (valid - valid.mean()) / (std or 1.0)
            entry.update({
                "min": float(valid.min()), "max": float(valid.max()), "mean": float(valid.mean()), "std": std,
                "median": float(valid.median()), "constant": std < 1e-9 * (abs(float(valid.mean())) + 1e-9),
                "outliers": int((z.abs() > OUTLIER_Z).sum()), "non_numeric": int(s.isna().sum() - df[c].isna().sum()),
                "hist": counts.tolist(), "edges": [float(edges[0]), float(edges[-1])],
            })
        columns.append(entry)

    numeric = [e["name"] for e in columns if e["kind"] == "numeric" and not e.get("constant", True)]
    corr_pairs, corr = [], None
    if len(numeric) > 1:
        cols = numeric[:MAX_CORR_COLUMNS]
        corr = num[[c for c in df.columns if str(c) in cols]].corr()
        corr.index = corr.columns = cols
        upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
        top = upper.abs().sort_values(ascending=False).head(6)
        corr_pairs = [{"a": a, "b": b, "r": round(float(upper[(a, b)]), 3)} for a, b in top.index]
    return {
        "rows": int(len(df)), "columns": int(df.shape[1]),
        "numeric_columns": int(sum(e["kind"] == "numeric" for e in columns)),
        "missing_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "constant_columns": [e["name"] for e in columns if e.get("constant")],
        "outlier_cells": int(sum(e.get("outliers", 0) for e in columns)),
        "column_stats": columns,
        "top_correlations": corr_pairs,
        "correlation": corr.round(3).to_dict() if corr is not None else None,
    }
