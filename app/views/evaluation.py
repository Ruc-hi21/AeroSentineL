import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.components import band_label, confusion_chart, get_result, require_model
from app.theme import CYAN, VIOLET, esc

artifacts = require_model()
meta = artifacts.metadata
metrics = meta["metrics"]
theme.page_header("Model performance · verified", "Model Evaluation",
                  f"Model <b>{esc(meta['version'])}</b> · trained {esc(meta['trained_at'])} · dataset {esc(meta['dataset'])} · "
                  f"{len(meta['train_units'])} training / {len(meta['val_units'])} validation engines (split by engine, "
                  "no engine in both). Final models are refit on all training engines, then scored once on the official test set.")

result = get_result()
if result is not None and result.duration_ms is not None:
    st.caption(f"Latest analysis took **{result.duration_ms:.0f} ms** for {len(result.units)} units.")

val_rul, test_rul = metrics["validation"]["rul"]["xgboost"], metrics["test"]["rul"]
val_risk, test_risk = metrics["validation"]["risk"]["xgboost"], metrics["test"]["risk"]


def tone(ok):
    return "#19f5a0" if ok else "#ffd23f"


theme.section("Risk-band classification", "4 bands")
gauges = [
    theme.gauge("Test accuracy", test_risk["accuracy"], f"{test_risk['accuracy']:.1%}", tone(test_risk["accuracy"] >= 0.9),
                "official test set · last cycle"),
    theme.gauge("Validation accuracy", val_risk["accuracy"], f"{val_risk['accuracy']:.1%}", tone(val_risk["accuracy"] >= 0.9),
                "20 held-out engines · every cycle"),
]
if val_risk.get("cv_accuracy") is not None:
    gauges.append(theme.gauge("CV accuracy", val_risk["cv_accuracy"], f"{val_risk['cv_accuracy']:.1%}",
                              tone(val_risk["cv_accuracy"] >= 0.9), "5-fold by engine"))
gauges += [
    theme.gauge("Test macro-F1", test_risk["macro_f1"], f"{test_risk['macro_f1']:.2f}", VIOLET, "balanced over 4 bands"),
    theme.gauge("Validation macro-F1", val_risk["macro_f1"], f"{val_risk['macro_f1']:.2f}", VIOLET, "every cycle"),
]
theme.gauge_row(gauges)

theme.section("RUL regression", "cycles")
theme.gauge_row([
    theme.gauge("Test RMSE", 1 - min(1, test_rul["rmse"] / 40), f"{test_rul['rmse']:.1f}", CYAN, "lower is better"),
    theme.gauge("Test MAE", 1 - min(1, test_rul["mae"] / 40), f"{test_rul['mae']:.1f}", CYAN, "lower is better"),
    theme.gauge("Test R²", max(0, test_rul["r2"]), f"{test_rul['r2']:.2f}", "#19f5a0", "variance explained"),
    theme.gauge("80% range coverage", test_rul["interval_coverage"], f"{test_rul['interval_coverage']:.0%}", VIOLET,
                "true RUL inside the range"),
    theme.gauge("Validation RMSE", 1 - min(1, val_rul["rmse"] / 40), f"{val_rul['rmse']:.1f}", CYAN, "held-out engines"),
])

theme.section("XGBoost vs. baselines", "validation engines")
left, right = st.columns(2)
with left:
    risk_rows = {**metrics["validation"]["risk"]["baselines"],
                 "xgboost ensemble": {"accuracy": val_risk["accuracy"], "macro_f1": val_risk["macro_f1"]}}
    names = list(risk_rows)
    fig = go.Figure()
    for metric, color in [("accuracy", CYAN), ("macro_f1", VIOLET)]:
        fig.add_trace(go.Bar(y=names, x=[risk_rows[n][metric] for n in names], orientation="h", name=metric,
                             marker_color=color, text=[f"{risk_rows[n][metric]:.3f}" for n in names], textposition="outside"))
    fig.update_layout(height=340, barmode="group", xaxis_range=[0.5, 1.02], legend=dict(orientation="h", y=1.1),
                      title=dict(text="Risk band — higher is better", font=dict(size=13)))
    theme.chart(fig, key="risk_baselines")
with right:
    rul_rows = {**metrics["validation"]["rul"]["baselines"], "xgboost": val_rul}
    names = list(rul_rows)
    fig = go.Figure(go.Bar(y=names, x=[rul_rows[n]["rmse"] for n in names], orientation="h",
                           marker_color=[CYAN if n == "xgboost" else "rgba(127,149,189,.55)" for n in names],
                           text=[f"{rul_rows[n]['rmse']:.2f}" for n in names], textposition="outside"))
    fig.update_layout(height=340, title=dict(text="RUL RMSE (cycles) — lower is better", font=dict(size=13)))
    theme.chart(fig, key="rul_baselines")

if val_risk.get("blend_scores"):
    blend = val_risk.get("blend", 0)
    theme.card("How the risk ensemble was chosen", f"<p>The risk band blends the XGBoost classifier with band probabilities "
               f"implied by the XGBoost RUL regressor. The weight on the regressor was picked by 5-fold CV accuracy on the "
               f"training engines only: <b>{blend:g}</b>.</p><p class='as-mono' style='color:#7f95bd'>"
               + " · ".join(f"w={k}: {v:.3f}" for k, v in val_risk["blend_scores"].items()) + "</p>")

theme.section("Per-band detail")
tab_val, tab_test = st.tabs(["Validation engines (every cycle)", "Test set (last cycle per engine)"])
for tab, m, key in [(tab_val, val_risk, "val"), (tab_test, test_risk, "test")]:
    with tab:
        left, right = st.columns([1, 1])
        per_band = pd.DataFrame(m["per_band"]).T
        per_band.index = per_band.index.map(band_label)
        with left:
            st.dataframe(per_band, width="stretch")
        with right:
            theme.chart(confusion_chart(m["confusion_matrix"]), key=f"cm_{key}")

with st.expander("Model configuration"):
    st.json({"sensors": meta["sensors"], "n_features": len(meta["features"]), "config": meta["config"],
             "params": meta["params"], "seed": meta["seed"], "final_fit": meta.get("final_fit"),
             "environment": meta["environment"]})
