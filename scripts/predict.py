"""Run the full pipeline on a sensor file and print units ranked by risk.

Usage: python -m scripts.predict [path]   (default: the FD001 test set)
"""

import sys

import pandas as pd

from src.config import DATASET, RAW_DATA_DIR, REPORTS_DIR, RISK_BANDS
from src.pipeline import analyze


def _sensors(factors, n=3):
    return ", ".join(f["sensor"] for f in factors[:n]) if isinstance(factors, list) else "-"


def main(path):
    result = analyze(path)
    print(f"\nJob {result.job_id} | model {result.model_version} | status {result.status}")
    print(f"Stages: {result.stages}")
    if result.status == "FAILED":
        print(f"Error {result.error['code']}: {result.error['message']}")
        sys.exit(1)
    for warning in result.validation["warnings"]:
        print(f"Warning: {warning}")

    units = result.units.copy()
    units["severity"] = units["risk_band"].map(RISK_BANDS.index)
    units = units.sort_values(["severity", "predicted_rul"], ascending=[False, True])

    table = pd.DataFrame({
        "unit": units["unit"],
        "cycle": units["cycle"],
        "health": units["health_condition"],
        "RUL": units["predicted_rul"].round().astype(int),
        "RUL 80% range": [f"{lo:.0f}-{hi:.0f}" for lo, hi in zip(units["rul_low"], units["rul_high"])],
        "risk band": units["risk_band"],
        "prob": units["risk_probability"],
        "top sensors (risk)": units["risk_factors"].apply(_sensors),
        "review": units["review_reasons"].apply(lambda r: "; ".join(r) or "-"),
    })
    print(f"\n{len(units)} units. Band counts: {units['risk_band'].value_counts().to_dict()}")
    print(f"Units flagged for review: {int(units['needs_review'].sum())}\n")
    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print(table.head(15).to_string(index=False))

    out = REPORTS_DIR / "latest_predictions.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)
    print(f"\nFull table saved to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else RAW_DATA_DIR / f"test_{DATASET}.txt")
