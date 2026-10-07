import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.components import band_label
from app.theme import BAND_COLORS, BAND_TEXT
from src.evaluation.error_analysis import load_test_predictions, summary

theme.page_header("Model forensics · where it goes wrong", "Error Analysis",
                  "Errors on the official FD001 test set (100 engines, last cycle each).")

df = load_test_predictions()
if df is None:
    st.info("Run `python -m training.train` to generate test-set predictions.")
    st.stop()

s = summary(df)
theme.kpi_row([
    theme.kpi("RUL over-estimated > 20", s["over_estimates"], "⬆️", "the riskier error: more life than real", "#ff2e4d"),
    theme.kpi("RUL under-estimated > 20", s["under_estimates"], "⬇️", "conservative error", "#ffd23f"),
    theme.kpi("Outside 80% range", s["outside_range"], "🎯", "true RUL missed by the interval", theme.VIOLET),
    theme.kpi("Wrong risk band", s["wrong_band"], "🔀", f"of {len(df)} engines", "#ff8a1f"),
    theme.kpi("Severe engines missed", s["missed_severe"], "🚨", "true high/failure, predicted lower", "#ff2e4d"),
    theme.kpi("High ↔ Failure mix-ups", s["high_vs_failure_confusion"], "⇄", "adjacent severe bands", theme.CYAN),
])

theme.section("Predicted vs. true RUL")
fig = go.Figure()
limit = max(df["true_rul"].max(), df["predicted_rul"].max()) + 5
fig.add_trace(go.Scatter(x=[0, limit], y=[0, limit], mode="lines", line=dict(dash="dash", color="rgba(219,232,255,.4)"),
                         hoverinfo="skip", showlegend=False))
for band, part in df.groupby("true_band"):
    fig.add_trace(go.Scatter(
        x=part["true_rul"], y=part["predicted_rul"], mode="markers", name=BAND_TEXT.get(band, band),
        marker=dict(size=10, color=BAND_COLORS.get(band), line=dict(color="#fff", width=0.5), opacity=0.9),
        error_y=dict(type="data", symmetric=False, array=part["rul_high"] - part["predicted_rul"],
                     arrayminus=part["predicted_rul"] - part["rul_low"], color="rgba(219,232,255,.25)", thickness=1),
        customdata=part[["unit", "predicted_band", "error"]],
        hovertemplate="unit %{customdata[0]}<br>true %{x} · predicted %{y:.0f}<br>error %{customdata[2]:+.0f}"
                      "<br>predicted band %{customdata[1]}<extra></extra>",
    ))
fig.update_layout(height=470, xaxis_title="true RUL", yaxis_title="predicted RUL", legend=dict(orientation="h", y=1.06))
theme.chart(fig, key="pred_vs_true")

left, right = st.columns(2)
with left:
    theme.section("Largest RUL errors")
    st.dataframe(df.nlargest(10, "abs_error")[["unit", "true_rul", "predicted_rul", "error", "rul_low", "rul_high"]],
                 hide_index=True, width="stretch")
with right:
    theme.section("Wrong risk bands")
    wrong = df[df["band_gap"] != 0].assign(
        true=lambda d: d["true_band"].map(band_label),
        predicted=lambda d: d["predicted_band"].map(band_label),
    ).sort_values("band_gap")
    st.dataframe(wrong[["unit", "true_rul", "true", "predicted", "band_gap"]], hide_index=True, width="stretch")
    st.caption("band_gap < 0: predicted less severe than reality (missed risk); > 0: false alarm.")
