"""Evaluation metrics. Regression and classification are reported separately."""

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_recall_fscore_support,
    r2_score,
    roc_auc_score,
    root_mean_squared_error,
)

from src.config import RISK_BANDS


def regression_metrics(y_true, y_pred):
    return {
        "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 3),  # primary metric
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "r2": round(float(r2_score(y_true, y_pred)), 3),
    }


def interval_coverage(y_true, low, high):
    """Share of true values inside the predicted interval."""
    y_true = np.asarray(y_true)
    return round(float(np.mean((y_true >= low) & (y_true <= high))), 3)


def classification_metrics(y_true, proba):
    y_true = np.asarray(y_true)
    labels = list(range(len(RISK_BANDS)))
    y_pred = proba.argmax(axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )

    per_band = {}
    for code, band in enumerate(RISK_BANDS):
        is_band = y_true == code
        # ROC-AUC is undefined when a band is absent (or the only one) in y_true.
        auc = roc_auc_score(is_band, proba[:, code]) if 0 < is_band.sum() < len(y_true) else None
        per_band[band] = {
            "precision": round(float(precision[code]), 3),
            "recall": round(float(recall[code]), 3),
            "f1": round(float(f1[code]), 3),
            "roc_auc": None if auc is None else round(float(auc), 3),
            "support": int(support[code]),
        }

    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 3),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 3),
        "per_band": per_band,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),  # nested list for JSON
    }


def format_regression_summary(metrics: dict) -> str:
    """Render concise string representation of core regression metrics."""
    return f"RMSE: {metrics.get('rmse', 0.0):.2f} | MAE: {metrics.get('mae', 0.0):.2f} | R2: {metrics.get('r2', 0.0):.3f}"
