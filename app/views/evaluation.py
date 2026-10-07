"""Evaluation: how well the models perform on engines they never saw."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.components import band_label, confusion_chart, get_result, require_model
from app.theme import MONO, TOKENS, esc

artifacts = require_model()
meta = artifacts.metadata
metrics = meta["metrics"]
theme.page_head("Evaluation", "Engines are split by unit, so no engine appears in both training and evaluation. Final "
                "models are refit on all training engines, then scored once on the NASA test set.",
                f"model <b>{esc(meta['version'])}</b><br>trained {esc(meta['trained_at'][:10])}<br>"
                f"{len(meta['train_units'])} train / {len(meta['val_units'])} validation engines")

result = get_result()
if result is not None and result.duration_ms is not None:
    st.caption(f"Latest analysis took {result.duration_ms:.0f} ms for {len(result.units)} engines.")

val_rul, test_rul = metrics["validation"]["rul"]["xgboost"], metrics["test"]["rul"]
val_risk, test_risk = metrics["validation"]["risk"]["xgboost"], metrics["test"]["risk"]

theme.section("Risk band classification", "four bands: normal, at risk, high risk, failure likely")
items = [theme.stat("Accuracy, NASA test", f"{test_risk['accuracy']:.1%}", foot="100 engines, last cycle each"),
         theme.stat("Accuracy, validation", f"{val_risk['accuracy']:.1%}", foot="20 unseen engines, every cycle")]
if val_risk.get("cv_accuracy") is not None:
    items.append(theme.stat("Accuracy, 5-fold CV", f"{val_risk['cv_accuracy']:.1%}", foot="grouped by engine"))
items += [theme.stat("Macro-F1, NASA test", f"{test_risk['macro_f1']:.2f}", foot="bands weighted equally"),
          theme.stat("Macro-F1, validation", f"{val_risk['macro_f1']:.2f}")]
theme.stats(items)

theme.section("RUL regression", "cycles")
theme.stats([
    theme.stat("RMSE, NASA test", f"{test_rul['rmse']:.1f}", "cycles"),
    theme.stat("MAE, NASA test", f"{test_rul['mae']:.1f}", "cycles"),
    theme.stat("R², NASA test", f"{test_rul['r2']:.2f}"),
    theme.stat("80% range coverage", f"{test_rul['interval_coverage']:.0%}", foot="target 80%"),
    theme.stat("RMSE, validation", f"{val_rul['rmse']:.1f}", "cycles"),
])

theme.section("Compared with baselines", "validation engines")
left, right = st.columns(2, gap="large")


def dot_plot(rows, metric, title, better, fmt, x_range):
    """One dot per model; the shipped model is the only coloured one."""
    names = list(rows)
    vals = [rows[n][metric] for n in names]
    colors = [TOKENS["accent"] if n.startswith("xgboost") and "only" not in n else TOKENS["text_3"] for n in names]
    fig = go.Figure(go.Scatter(x=vals, y=[n.replace("_", " ") for n in names], mode="markers+text", text=[fmt(v) for v in vals],
                               textposition="middle right", textfont=dict(family=MONO, size=11, color=TOKENS["text_2"]),
                               marker=dict(size=10, color=colors), cliponaxis=False,
                               hovertemplate="%{y}<br>%{x:.3f}<extra></extra>"))
    fig.update_layout(height=60 + 46 * len(names), margin=dict(t=8, b=40, l=8, r=60), xaxis_title=f"{title} ({better})",
                      xaxis_range=x_range, yaxis=dict(ticks="", showgrid=False, tickfont=dict(size=12, color=TOKENS["text_2"])))
    return fig


with left:
    risk_rows = {**metrics["validation"]["risk"]["baselines"],
                 "xgboost_ensemble": {"accuracy": val_risk["accuracy"], "macro_f1": val_risk["macro_f1"]}}
    theme.chart(dot_plot(risk_rows, "accuracy", "risk accuracy", "higher is better", lambda v: f"{v:.1%}", [0.85, 1.0]),
                key="risk_baselines")
with right:
    rul_rows = {**metrics["validation"]["rul"]["baselines"], "xgboost": val_rul}
    theme.chart(dot_plot(rul_rows, "rmse", "RUL RMSE, cycles", "lower is better", lambda v: f"{v:.2f}", [0, 20]),
                key="rul_baselines")

if val_risk.get("blend_scores"):
    theme.note(f"The risk band blends the XGBoost classifier with band probabilities implied by the XGBoost RUL regressor. "
               f"The regressor weight ({val_risk.get('blend', 0):g}) was chosen by 5-fold CV accuracy on training engines: "
               + ", ".join(f"weight {k} gives {v:.1%}" for k, v in val_risk["blend_scores"].items()) + ".")

theme.section("Per band")
tab_val, tab_test = st.tabs(["Validation engines, every cycle", "NASA test set, last cycle per engine"])
for tab, m, key in [(tab_val, val_risk, "val"), (tab_test, test_risk, "test")]:
    with tab:
        left, right = st.columns([1, 1], gap="large")
        per_band = pd.DataFrame(m["per_band"]).T
        per_band.index = per_band.index.map(band_label)
        with left:
            st.dataframe(per_band, width="stretch", column_config={
                "precision": st.column_config.NumberColumn("Precision", format="%.3f"),
                "recall": st.column_config.NumberColumn("Recall", format="%.3f"),
                "f1": st.column_config.NumberColumn("F1", format="%.3f"),
                "roc_auc": st.column_config.NumberColumn("ROC AUC", format="%.3f"),
                "support": st.column_config.NumberColumn("Support", format="%d")})
            theme.note("Recall on failure likely matters most: it is the share of engines close to failure that were caught.")
        with right:
            theme.chart(confusion_chart(m["confusion_matrix"]), key=f"cm_{key}")

with st.expander("Model configuration"):
    st.json({"sensors": meta["sensors"], "n_features": len(meta["features"]), "config": meta["config"],
             "params": meta["params"], "seed": meta["seed"], "final_fit": meta.get("final_fit"),
             "environment": meta["environment"]})
