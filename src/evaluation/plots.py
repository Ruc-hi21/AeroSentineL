"""Static figures saved to reports/figures by the training run."""

import matplotlib

matplotlib.use("Agg")  # non-interactive backend; must be set before pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.config import RISK_BANDS  # noqa: E402


def _save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=120)  # 120 dpi: readable in reports without huge file size
    plt.close(fig)


def sensor_trends(df, sensors, path, n_units=5):
    """Each kept sensor against RUL for a few training units (EDA view)."""
    cols = 4
    rows = int(np.ceil(len(sensors) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(14, 2.6 * rows), squeeze=False)
    units = df["unit"].unique()[:n_units]
    for ax, sensor in zip(axes.flat, sensors):
        for unit in units:
            part = df[df["unit"] == unit]
            ax.plot(part["rul"], part[sensor], linewidth=0.8)
        ax.set_title(sensor, fontsize=9)
        ax.invert_xaxis()
    for ax in axes.flat[len(sensors):]:
        ax.axis("off")
    fig.supxlabel("RUL (cycles, capped) — failure is on the right")
    _save(fig, path)


def health_scores(df, threshold, path, n_units=5):
    fig, ax = plt.subplots(figsize=(8, 4))
    for unit in df["unit"].unique()[:n_units]:
        part = df[df["unit"] == unit]
        ax.plot(part["cycle"], part["health_score"], label=f"unit {unit}", linewidth=1)
    ax.axhline(threshold, color="black", linestyle="--", label="abnormal threshold")
    ax.set(xlabel="cycle", ylabel="health score (0 = healthy)", title="Health score over engine life")
    ax.legend(fontsize=8)
    _save(fig, path)


def rul_predictions(y_true, y_pred, low, high, path):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.errorbar(y_true, y_pred, yerr=[y_pred - low, high - y_pred], fmt="o", markersize=3,
                alpha=0.6, elinewidth=0.6)
    limit = max(np.max(y_true), np.max(y_pred)) + 5
    ax.plot([0, limit], [0, limit], color="black", linestyle="--", linewidth=1)
    ax.set(xlabel="true RUL", ylabel="predicted RUL (80% interval)", title="Test set: last cycle per engine")
    _save(fig, path)


def confusion(matrix, path, title):
    matrix = np.asarray(matrix)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(range(len(RISK_BANDS)), RISK_BANDS, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(RISK_BANDS)), RISK_BANDS, fontsize=8)
    for i in range(len(matrix)):
        for j in range(len(matrix)):
            color = "white" if matrix[i, j] > matrix.max() / 2 else "black"
            ax.text(j, i, matrix[i, j], ha="center", va="center", color=color, fontsize=9)
    ax.set(xlabel="predicted", ylabel="true", title=title)
    _save(fig, path)


def sensor_importance(importance, path, title):
    """Horizontal bar chart of mean |SHAP| per sensor."""
    importance = importance.sort_values()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(importance.index, importance.values)
    ax.set(xlabel="mean |SHAP value|", title=title)
    _save(fig, path)
