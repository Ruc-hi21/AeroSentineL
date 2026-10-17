"""Error analysis: where each model is wrong on its test set."""

import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.components import PROFILE_LABELS, active_subset, band_label
from app.theme import BAND_COLORS, BAND_TEXT, TOKENS
from src.components import PROFILES, spec_of_profile
from src.config import RISK_BANDS
from src.evaluation.error_analysis import load_test_predictions, predictions_file, summary

if __name__ == "__main__":  # own heading only as a page of its own, not as an admin tab
    theme.page_head("Error analysis", "Errors on the held-out test sets, each unit scored at its last recorded cycle or minute.")
ready = [s for s in PROFILES if predictions_file(s).exists()]
if not ready:
    theme.empty("No test predictions yet", "Run <code>python -m training.train</code> to generate test-set predictions.")
    st.stop()
default = active_subset() if active_subset() in ready else ready[0]
subset = st.pills("Test set", ready, default=default, key="errors_subset", format_func=PROFILE_LABELS.get) or default
spec = spec_of_profile(subset)
u, lu = spec.unit_plural, spec.life_unit
df = load_test_predictions(subset)
st.caption(f"{PROFILE_LABELS[subset]}: {len(df)} {u}. {int((df['true_rul'] > spec.rul_cap).sum())} have more than "
           f"{spec.rul_cap} {lu} left, where the model is trained to report {spec.rul_cap}.")

s = summary(df)
theme.stats([
    theme.stat(f"RUL over-estimated by more than 20 {lu}", s["over_estimates"], foot="the riskier error: more life than real",
               color=theme.STATES["CRITICAL"]["color"] if s["over_estimates"] else None),
    theme.stat(f"RUL under-estimated by more than 20 {lu}", s["under_estimates"], foot="conservative error"),
    theme.stat("True RUL outside 80% range", s["outside_range"], foot=f"of {len(df)} {u}"),
    theme.stat("Wrong risk band", s["wrong_band"], foot=f"of {len(df)} {u}"),
    theme.stat(f"Severe {u} missed", s["missed_severe"], foot="true high or failure, predicted lower",
               color=theme.STATES["CRITICAL"]["color"] if s["missed_severe"] else None),
])

theme.section("Predicted against true RUL", "diagonal is a perfect prediction; bars are the 80% range")
fig = go.Figure()
limit = max(df["true_rul"].max(), df["predicted_rul"].max()) + 5
fig.add_trace(go.Scatter(x=[0, limit], y=[0, limit], mode="lines", line=dict(color=TOKENS["line_strong"], dash="dash", width=1),
                         hoverinfo="skip", showlegend=False))
for band in [b for b in RISK_BANDS if b in set(df["true_band"])]:  # legend in severity order
    part = df[df["true_band"] == band]
    fig.add_trace(go.Scatter(
        x=part["true_rul"], y=part["predicted_rul"], mode="markers", name=f"true band: {BAND_TEXT.get(band, band).lower()}",
        marker=dict(size=7, color=BAND_COLORS.get(band), line=dict(color=TOKENS["bg"], width=1)),
        error_y=dict(type="data", symmetric=False, array=part["rul_high"] - part["predicted_rul"],
                     arrayminus=part["predicted_rul"] - part["rul_low"], color=TOKENS["line_strong"], thickness=1, width=0),
        customdata=part[["unit", "predicted_band", "error"]],
        hovertemplate=spec.unit_title + " %{customdata[0]}<br>true %{x}, predicted %{y:.0f}<br>error %{customdata[2]:+.0f}"
                      "<br>predicted band %{customdata[1]}<extra></extra>"))
fig.update_layout(height=460, xaxis_title=f"true RUL ({lu})", yaxis_title=f"predicted RUL ({lu})")
theme.chart(fig, key="pred_vs_true")

left, right = st.columns(2, gap="large")
with left:
    theme.section("Largest RUL errors")
    st.dataframe(df.nlargest(10, "abs_error")[["unit", "true_rul", "predicted_rul", "error", "rul_low", "rul_high"]],
                 hide_index=True, width="stretch", column_config={
                     "unit": st.column_config.NumberColumn(spec.unit_title, format="%d"),
                     "true_rul": "True RUL", "predicted_rul": st.column_config.NumberColumn("Predicted", format="%.0f"),
                     "error": st.column_config.NumberColumn("Error", format="%+.0f"),
                     "rul_low": st.column_config.NumberColumn("80% low", format="%.0f"),
                     "rul_high": st.column_config.NumberColumn("80% high", format="%.0f")})
with right:
    theme.section("Wrong risk bands", "negative gap means the risk was understated")
    wrong = df[df["band_gap"] != 0].assign(
        true=lambda d: d["true_band"].map(band_label),
        predicted=lambda d: d["predicted_band"].map(band_label),
    ).sort_values("band_gap")
    st.dataframe(wrong[["unit", "true_rul", "true", "predicted", "band_gap"]], hide_index=True, width="stretch", column_config={
        "unit": st.column_config.NumberColumn(spec.unit_title, format="%d"), "true_rul": "True RUL", "true": "True band",
        "predicted": "Predicted band", "band_gap": st.column_config.NumberColumn("Gap", format="%+d")})
