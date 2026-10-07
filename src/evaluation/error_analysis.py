"""Where the models go wrong, from reports/test_predictions.csv (written by training)."""

import pandas as pd

from src.config import REPORTS_DIR, RISK_BANDS

PREDICTIONS_FILE = REPORTS_DIR / "test_predictions.csv"


def load_test_predictions():
    """Test-set predictions with error columns, or None if training has not run."""
    if not PREDICTIONS_FILE.exists():
        return None
    df = pd.read_csv(PREDICTIONS_FILE)
    df["error"] = df["predicted_rul"] - df["true_rul"]  # > 0 = model thinks engine has more life left
    df["abs_error"] = df["error"].abs()
    df["band_gap"] = df["predicted_band"].map(RISK_BANDS.index) - df["true_band"].map(RISK_BANDS.index)
    df["in_range"] = df["true_rul"].between(df["rul_low"], df["rul_high"])
    return df


def summary(df):
    severe = ["HIGH_RISK", "FAILURE_LIKELY"]
    return {
        "over_estimates": int((df["error"] > 20).sum()),  # dangerous: predicts more life than real
        "under_estimates": int((df["error"] < -20).sum()),
        "wrong_band": int((df["band_gap"] != 0).sum()),
        "missed_severe": int((df["true_band"].isin(severe) & ~df["predicted_band"].isin(severe)).sum()),
        "high_vs_failure_confusion": int(
            ((df["true_band"] == "HIGH_RISK") & (df["predicted_band"] == "FAILURE_LIKELY")).sum()
            + ((df["true_band"] == "FAILURE_LIKELY") & (df["predicted_band"] == "HIGH_RISK")).sum()
        ),
        "outside_range": int((~df["in_range"]).sum()),
    }
