"""Evaluation: how well the models perform on engines they never saw, per subset and across subsets."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.components import (
    active_subset, band_label, confusion_chart, cross_chart, get_result, load_benchmark, require_model, subset_summary,
)
from app.theme import MONO, TOKENS
from src.models.artifacts import available_subsets

theme.page_head("Evaluation", "Engines are split by unit, so no engine appears in both training and evaluation. Final "
                "models are refit on all training engines, then scored once on the NASA test set.")

# ---------------------------------------------------------------- across subsets
bench = load_benchmark()
if bench and bench.get("subsets"):
    theme.section("Across the four NASA subsets", "one model per subset, each scored on its own test fleet")
    rows = []
    for s, r in bench["subsets"].items():
        rows.append({"Subset": s, "Conditions": r["conditions"], "Fault modes": " and ".join(r["fault_modes"]),
                     "Train engines": r["train_engines"], "Test engines": r["test_engines"],
                     "Risk accuracy": r["test_accuracy"] * 100, "Macro-F1": r["test_macro_f1"],
                     "RMSE": r["test_rmse"], "RMSE capped": r["test_rmse_capped"], "R²": r["test_r2"],
                     "Validation accuracy": r["val_accuracy"] * 100})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "Risk accuracy": st.column_config.NumberColumn("Risk accuracy, test", format="%.1f%%"),
        "Macro-F1": st.column_config.NumberColumn("Macro-F1, test", format="%.3f"),
        "RMSE": st.column_config.NumberColumn("RUL RMSE, test", format="%.1f",
                                              help="Against the true remaining life, uncapped"),
        "RMSE capped": st.column_config.NumberColumn("RMSE, true RUL capped", format="%.1f",
                                                     help="True RUL capped at 125 like the training target: the "
                                                          "convention most C-MAPSS papers report"),
        "R²": st.column_config.NumberColumn("R², test", format="%.3f"),
        "Validation accuracy": st.column_config.NumberColumn("Accuracy, held-out engines", format="%.1f%%"),
    })
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        metric = st.segmented_control("Generalisation matrix", ["Risk accuracy", "RUL RMSE, capped"],
                                      default="Risk accuracy", key="cross_metric")
        key = "rmse_capped" if metric == "RUL RMSE, capped" else "accuracy"
        theme.chart(cross_chart(bench["cross"], key), key="cross_matrix")
    with right:
        theme.section("Reading the matrix")
        theme.note("Each row is one subset's model, each column one subset's NASA test fleet. The diagonal is the "
                   "headline result. Off the diagonal, a model meets engines from another subset: a single-condition "
                   "model cannot score multi-condition data (marked untrained conditions), while a model trained on two "
                   "fault modes usually holds up on single-fault data. This is why files without a subset in their "
                   "name go to FD003 or FD004.")
        theme.note("RMSE is reported two ways. Uncapped compares against the true remaining life; engines with more "
                   "than 125 cycles left inflate it because the model is trained to top out at 125. Capped applies the "
                   "same limit to the truth, which is how most published C-MAPSS results are scored.")

# ---------------------------------------------------------------- one subset in detail
trained = available_subsets()
default = active_subset() if active_subset() in trained else (trained[0] if trained else None)
subset = st.segmented_control("Subset in detail", trained, default=default, key="eval_subset") or default
artifacts = require_model(subset)
meta = artifacts.metadata
metrics = meta["metrics"]
theme.section(f"{subset} in detail", f"{subset_summary(subset)}; model {meta['version']}, trained {meta['trained_at'][:10]}, "
              f"{len(meta['train_units'])} train / {len(meta['val_units'])} validation engines")

result = get_result()
if result is not None and result.duration_ms is not None:
    st.caption(f"Latest analysis took {result.duration_ms:.0f} ms for {len(result.units)} engines.")

val_rul, test_rul = metrics["validation"]["rul"]["xgboost"], metrics["test"]["rul"]
val_risk, test_risk = metrics["validation"]["risk"]["xgboost"], metrics["test"]["risk"]
n_test = sum(v["support"] for v in test_risk["per_band"].values())
n_val = len(meta["val_units"])

items = [theme.stat("Accuracy, NASA test", f"{test_risk['accuracy']:.1%}", foot=f"{n_test} engines, last cycle each"),
         theme.stat("Accuracy, validation", f"{val_risk['accuracy']:.1%}", foot=f"{n_val} unseen engines, every cycle")]
if val_risk.get("cv_accuracy") is not None:
    items.append(theme.stat("Accuracy, 5-fold CV", f"{val_risk['cv_accuracy']:.1%}", foot="grouped by engine"))
items += [theme.stat("Macro-F1, NASA test", f"{test_risk['macro_f1']:.2f}", foot="bands weighted equally"),
          theme.stat("Macro-F1, validation", f"{val_risk['macro_f1']:.2f}")]
theme.stats(items)

rul_items = [theme.stat("RMSE, NASA test", f"{test_rul['rmse']:.1f}", "cycles", foot="against true RUL")]
if test_rul.get("rmse_capped") is not None:
    rul_items.append(theme.stat("RMSE, capped truth", f"{test_rul['rmse_capped']:.1f}", "cycles", foot="true RUL capped at 125"))
rul_items += [theme.stat("MAE, NASA test", f"{test_rul['mae']:.1f}", "cycles"),
              theme.stat("R², NASA test", f"{test_rul['r2']:.2f}"),
              (theme.stat("80% range coverage", f"{test_rul['interval_coverage_capped']:.0%}",
                          foot=f"target 80%; {test_rul['interval_coverage']:.0%} against uncapped truth")
               if test_rul.get("interval_coverage_capped") is not None
               else theme.stat("80% range coverage", f"{test_rul['interval_coverage']:.0%}", foot="target 80%")),
              theme.stat("RMSE, validation", f"{val_rul['rmse']:.1f}", "cycles")]
theme.stats(rul_items)

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
    low = min(r["accuracy"] for r in risk_rows.values())
    theme.chart(dot_plot(risk_rows, "accuracy", "risk accuracy", "higher is better", lambda v: f"{v:.1%}",
                         [min(0.85, low - 0.02), 1.0]), key="risk_baselines")
with right:
    rul_rows = {**metrics["validation"]["rul"]["baselines"], "xgboost": val_rul}
    high = max(r["rmse"] for r in rul_rows.values())
    theme.chart(dot_plot(rul_rows, "rmse", "RUL RMSE, cycles", "lower is better", lambda v: f"{v:.2f}",
                         [0, max(20, high * 1.2)]), key="rul_baselines")

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

conditions = meta.get("conditions") or []
if len(conditions) > 1:
    theme.section("Operating conditions learned", "condition 1 is the sea-level reference every reading is corrected to")
    st.dataframe(pd.DataFrame(conditions).rename(columns={
        "id": "Condition", "altitude_kft": "Altitude (kft)", "mach": "Mach", "throttle": "Throttle (TRA)",
        "share": "Share of training cycles", "reference": "Reference"}), hide_index=True, width="stretch",
        column_config={"Share of training cycles": st.column_config.NumberColumn(format="%.3f")})

with st.expander("Model configuration"):
    st.json({"subset": subset, "sensors": meta["sensors"], "n_features": len(meta["features"]), "config": meta["config"],
             "params": meta["params"], "seed": meta["seed"], "final_fit": meta.get("final_fit"),
             "environment": meta["environment"]})
