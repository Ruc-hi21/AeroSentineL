"""Flatten an AnalysisResult into files people can download."""

import json

import pandas as pd


def _factor_names(factors):
    return "; ".join(f["sensor"] for f in factors) if isinstance(factors, list) else ""


def units_table(units):
    """One flat row per unit, ready for CSV/Excel."""
    table = units.copy()
    for col in ("rul_factors", "risk_factors"):
        if col in table:
            table[col] = table[col].apply(_factor_names)
    table["review_reasons"] = table["review_reasons"].apply("; ".join)
    return table


def result_json(result):
    """Full result summary (no raw sensor history) as a JSON string."""
    units = result.units if result.units is not None else pd.DataFrame()
    payload = {
        "jobId": result.job_id,
        "status": result.status,
        "modelVersion": result.model_version,
        "durationMs": result.duration_ms,
        "stages": result.stages,
        "validation": result.validation,
        "cleaning": result.cleaning,
        "error": result.error,
        "results": json.loads(units.to_json(orient="records")),
    }
    return json.dumps(payload, indent=2)
