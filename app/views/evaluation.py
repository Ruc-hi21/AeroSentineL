"""Evaluation: how well the models perform on units they never saw, per component and profile, and how well the
recognition model routes files."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import insights, theme
from app.components import (
    PROFILE_LABELS, active_subset, band_label, confusion_chart, cross_chart, get_result, load_benchmark, require_model,
    subset_summary,
)
from app.theme import MONO, TOKENS, esc
from src.components import get, spec_of_profile
from src.models.artifacts import available_subsets

theme.page_head("Evaluation", "Units are split by engine, cell or bearing, so none appears in both training and evaluation. "
                "Final models are refit on all training units, then scored once on the test set.")

# ---------------------------------------------------------------- across components
bench = load_benchmark()
if bench and bench.get("subsets"):
    theme.section("All component models", "one model per profile, each scored on its own held-out test units")
    rows = []
    for s, r in bench["subsets"].items():
        spec = spec_of_profile(s)
        rows.append({"Component": spec.unit_title, "Profile": s, "Conditions": r["conditions"],
                     "Train units": r["train_engines"], "Test units": r["test_engines"], "Life unit": spec.life_unit,
                     "CV accuracy": r["cv_accuracy"] * 100, "CV RMSE": r.get("cv_rmse"),
                     "Risk accuracy": r["test_accuracy"] * 100, "Macro-F1": r["test_macro_f1"],
                     "RMSE": r["test_rmse"], "RMSE capped": r["test_rmse_capped"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "CV accuracy": st.column_config.NumberColumn("Risk accuracy, 5-fold CV", format="%.1f%%",
                                                     help="Grouped by unit, on the training units"),
        "CV RMSE": st.column_config.NumberColumn("RUL RMSE, CV", format="%.1f"),
        "Risk accuracy": st.column_config.NumberColumn("Risk accuracy, test", format="%.1f%%"),
        "Macro-F1": st.column_config.NumberColumn("Macro-F1, test", format="%.3f"),
        "RMSE": st.column_config.NumberColumn("RUL RMSE, test", format="%.1f", help="Against the true remaining life, uncapped"),
        "RMSE capped": st.column_config.NumberColumn("RMSE, capped truth", format="%.1f",
                                                     help="True RUL capped like the training target"),
    })
    theme.note("Battery and bearing test sets hold 4 cells and 5 bearings, so one unit moves test accuracy by 20 to 25 "
               "points; read their cross-validated numbers first. The turbofan test sets hold 100 to 259 engines.")

    router = bench.get("router")
    if router:
        theme.section("Component recognition", f"{router['test_examples']} test files from units the model never saw, "
                      "plus unrelated tables it must reject")
        left, right = st.columns([1, 1.15], gap="large")
        with left:
            theme.stats([
                theme.stat("Routed to the right model", f"{router['known_routed_correctly']:.1%}", foot="known components"),
                theme.stat("Sent to a wrong model", f"{router['known_misrouted']:.1%}", foot="the error that matters"),
                theme.stat("Held back for a person", f"{router['known_held_back']:.1%}", foot="below the confidence threshold"),
                theme.stat("Unrelated tables rejected", f"{router['unknown_rejected']:.1%}"),
            ])
            theme.note(f"A file is routed only when the most likely component reaches {router['threshold']:.0%} "
                       "probability. Anything else stops with UNKNOWN_COMPONENT, so data never reaches a model it does "
                       "not belong to.")
        with right:
            classes = router["classes"]
            names = [get(c).unit_title if c != "unknown" else "Unknown" for c in classes]
            cm = np.asarray(router["confusion_matrix"], dtype=float)
            norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
            fig = go.Figure(go.Heatmap(z=norm, x=names, y=names, text=cm.astype(int), texttemplate="%{text}", showscale=False,
                                       colorscale=[[0, TOKENS["surface"]], [0.5, "#24406b"], [1, "#3a6cc2"]], zmin=0, zmax=1,
                                       textfont=dict(family=MONO, size=13, color=TOKENS["text_1"]), xgap=2, ygap=2,
                                       hovertemplate="true %{y}<br>predicted %{x}<br>%{text} files<extra></extra>"))
            fig.update_layout(height=300, xaxis_title="predicted component", yaxis_title="true component",
                              yaxis_autorange="reversed", margin=dict(t=8, b=48, l=96, r=8))
            theme.chart(fig, key="router_cm")

    if bench.get("cross"):
        theme.section("Turbofan generalisation", "each C-MAPSS subset's model scored on every subset's test fleet")
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
                       "fault modes usually holds up on single-fault data. This is why turbofan files without a subset in "
                       "their name go to FD003 or FD004.")
            theme.note("RMSE is reported two ways. Uncapped compares against the true remaining life; engines with more "
                       "than 125 cycles left inflate it because the model is trained to top out at 125. Capped applies the "
                       "same limit to the truth, which is how most published C-MAPSS results are scored.")

# ---------------------------------------------------------------- one subset in detail
trained = available_subsets()
default = active_subset() if active_subset() in trained else (trained[0] if trained else None)
subset = st.pills("Model in detail", trained, default=default, key="eval_subset",
                              format_func=PROFILE_LABELS.get) or default
artifacts = require_model(subset)
spec = spec_of_profile(subset)
meta = artifacts.metadata
metrics = meta["metrics"]
theme.section(f"{PROFILE_LABELS[subset]} in detail", f"{subset_summary(subset)}; model {meta['version']}, trained "
              f"{meta['trained_at'][:10]}, {len(meta['train_units'])} train / {len(meta['val_units'])} validation {spec.unit_plural}")

result = get_result()
if result is not None and result.duration_ms is not None:
    st.caption(f"Latest analysis took {result.duration_ms:.0f} ms for {insights.count(len(result.units), result.spec)}.")

val_rul, test_rul = metrics["validation"]["rul"]["xgboost"], metrics["test"]["rul"]
val_risk, test_risk = metrics["validation"]["risk"]["xgboost"], metrics["test"]["risk"]
n_test = sum(v["support"] for v in test_risk["per_band"].values())
n_val = len(meta["val_units"])

u, t, lu = spec.unit_plural, spec.time_title.lower(), spec.life_unit
items = [theme.stat("Accuracy, test", f"{test_risk['accuracy']:.1%}", foot=f"{n_test} {u}, last {t} each"),
         theme.stat("Accuracy, validation", f"{val_risk['accuracy']:.1%}", foot=f"{n_val} unseen {u}, every {t}")]
if val_risk.get("cv_accuracy") is not None:
    items.append(theme.stat("Accuracy, 5-fold CV", f"{val_risk['cv_accuracy']:.1%}", foot=f"grouped by {spec.actions.get('noun', 'unit')}"))
items += [theme.stat("Macro-F1, test", f"{test_risk['macro_f1']:.2f}", foot="bands weighted equally"),
          theme.stat("Macro-F1, validation", f"{val_risk['macro_f1']:.2f}")]
theme.stats(items)

rul_items = [theme.stat("RMSE, test", f"{test_rul['rmse']:.1f}", lu, foot="against true RUL")]
if test_rul.get("rmse_capped") is not None:
    rul_items.append(theme.stat("RMSE, capped truth", f"{test_rul['rmse_capped']:.1f}", lu, foot=f"true RUL capped at {spec.rul_cap}"))
if val_rul.get("cv_rmse") is not None:
    rul_items.append(theme.stat("RMSE, 5-fold CV", f"{val_rul['cv_rmse']:.1f}", lu, foot="training units, every reading"))
rul_items += [theme.stat("MAE, test", f"{test_rul['mae']:.1f}", lu),
              theme.stat("R², test", f"{test_rul['r2']:.2f}"),
              (theme.stat("80% range coverage", f"{test_rul['interval_coverage_capped']:.0%}",
                          foot=f"target 80%; {test_rul['interval_coverage']:.0%} against uncapped truth")
               if test_rul.get("interval_coverage_capped") is not None
               else theme.stat("80% range coverage", f"{test_rul['interval_coverage']:.0%}", foot="target 80%")),
              theme.stat("RMSE, validation", f"{val_rul['rmse']:.1f}", lu)]
theme.stats(rul_items)

theme.section("Compared with baselines", f"validation {u}")
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
                         [min(0.85, low - 0.05), 1.0]), key="risk_baselines")
with right:
    rul_rows = {**metrics["validation"]["rul"]["baselines"], "xgboost": val_rul}
    high = max(r["rmse"] for r in rul_rows.values())
    theme.chart(dot_plot(rul_rows, "rmse", f"RUL RMSE, {lu}", "lower is better", lambda v: f"{v:.2f}",
                         [0, max(20, high * 1.2)]), key="rul_baselines")

if val_risk.get("blend_scores"):
    theme.note(f"The risk band blends the XGBoost classifier with band probabilities implied by the XGBoost RUL regressor. "
               f"The regressor weight ({val_risk.get('blend', 0):g}) was chosen by 5-fold CV accuracy on training {u}: "
               + ", ".join(f"weight {k} gives {v:.1%}" for k, v in val_risk["blend_scores"].items()) + ".")

theme.section("Per band")
tab_val, tab_test = st.tabs([f"Validation {u}, every {t}", f"Test set, last {t} per {spec.actions.get('noun', 'unit')}"])
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
            theme.note(f"Recall on failure likely matters most: it is the share of {u} close to failure that were caught.")
        with right:
            theme.chart(confusion_chart(m["confusion_matrix"], u), key=f"cm_{key}")

diagnosis = metrics.get("diagnosis")
if diagnosis:
    theme.section("Part condition classifiers", "one XGBoost classifier per part; test = every load cycle of the held-out blocks")
    theme.stats([theme.stat(d["name"], f"{d['test_accuracy']:.1%}", foot=f"test; grouped CV {d['cv_accuracy']:.1%}")
                 for d in diagnosis.values()])
    cols = st.columns(len(diagnosis), gap="large")
    for col, (key, d) in zip(cols, diagnosis.items()):
        with col:
            cm = pd.DataFrame(d["confusion_matrix"], index=d["labels"], columns=d["labels"])
            st.caption(f"{d['name']}: rows true, columns predicted")
            st.dataframe(cm, width="stretch")
    if spec.not_assessed:
        theme.note(esc(spec.not_assessed))
    theme.note("Grouped CV holds out whole test blocks; when a fold holds out every block at one cooler level, that "
               "level is unseen in training, which is why the cooler's CV accuracy sits below its test accuracy.")

conditions = meta.get("conditions") or []
if len(conditions) > 1:
    theme.section("Operating conditions learned", "the reference condition is the one every reading is corrected to")
    labels = dict(zip(spec.settings, spec.setting_labels))
    table = pd.DataFrame([{"Condition": c["id"],
                           **{labels.get(k, k): v for k, v in (c.get("settings") or {
                               "setting_1": c.get("altitude_kft"), "setting_2": c.get("mach"), "setting_3": c.get("throttle")}).items()},
                           f"Share of training {t}s": c["share"], "Reference": c["reference"]} for c in conditions])
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={f"Share of training {t}s": st.column_config.NumberColumn(format="%.3f")})

with st.expander("Model configuration"):
    st.json({"subset": subset, "sensors": meta["sensors"], "n_features": len(meta["features"]), "config": meta["config"],
             "params": meta["params"], "seed": meta["seed"], "final_fit": meta.get("final_fit"),
             "environment": meta["environment"]})
