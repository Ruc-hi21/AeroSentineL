"""Engine status: for one engine, answer in order: condition, what is changing, time left,
risk, and what to do next. Detail lives one click away (progressive disclosure)."""

import streamlit as st

from app import insights, theme
from app.components import (
    drift_table, factor_chart, require_model, require_result, step_unit, trend_chart, unit_picker,
)
from app.instruments import engine_status, status_payload
from app.theme import TOKENS, esc
from src.config import CRITICAL_HEALTH_MULTIPLE

artifacts = require_model()
result = require_result()
units = result.units

theme.page_head("Engine status", "Condition, remaining useful life, failure risk and the suggested next step for one engine.",
                f"<b>{esc(st.session_state.get('source_name', ''))}</b><br>{len(units)} engines, model {esc(result.model_version)}")

pick, prev, nxt, _ = st.columns([3.2, 0.7, 0.7, 4.4], vertical_alignment="bottom")
with pick:
    row = unit_picker(units, key="engine", label="Engine (most urgent first)")
prev.button("Previous", key="engine_prev", on_click=step_unit, args=(units, "engine", -1), width="stretch")
nxt.button("Next", key="engine_next", on_click=step_unit, args=(units, "engine", 1), width="stretch")

unit = int(row["unit"])
hist = result.history[result.history["unit"] == unit].sort_values("cycle")
drift = insights.sensor_drift(hist, artifacts.health)
state = insights.engine_state(row)

# 1-3. Condition, time left, risk and the single most important action.
engine_status(status_payload(row, drift), key="engine_status")

# 4-5. What is changing.
left, right = st.columns([1.5, 1], gap="large")
with left:
    theme.section("Trend", "predicted RUL above health score, per cycle")
    threshold = artifacts.health.threshold
    theme.chart(trend_chart(hist, row, threshold, CRITICAL_HEALTH_MULTIPLE * threshold), key="engine_trend")
with right:
    hot = int(drift["status"].isin(["Critical", "Warning"]).sum())
    theme.section("Sensor drift", f"{hot} of {len(drift)} sensors beyond 2.4 sigma" if hot else "all sensors within 2.4 sigma")
    show_all = st.toggle("Show all sensors", key="engine_all_sensors")
    drift_table(drift, rows=None if show_all else 8, compact=True)
    theme.note("Drift is the directed z-score against the healthy baseline learned from the first cycles of the "
               "training engines. Positive values move in the direction degradation pushes that sensor.")

# 6-7. Why, and what to do.
left, right = st.columns([1, 1], gap="large")
with left:
    theme.section("Suggested actions")
    theme.actions(insights.recommendations(row, state, drift))
    theme.note("Frontend guidance derived from AeroSentinel's risk thresholds and sensor drift. "
               "Confirm against approved maintenance data before acting.")
with right:
    factors = row.get("rul_factors")
    theme.section("Why the model predicts this", "SHAP contribution to the RUL estimate, cycles")
    if isinstance(factors, list):
        theme.chart(factor_chart(factors, "change in predicted RUL (cycles)", "#ff832b", TOKENS["accent"]), key="engine_shap")
        theme.note("Bars to the left shortened the predicted life. SHAP shows correlation with the prediction, "
                   "not proof of a root cause.")
    else:
        st.info("No explanation available for this analysis.")

st.divider()
links = st.columns(4)
links[0].page_link("views/health.py", label="Degradation detail", icon=":material/trending_down:")
links[1].page_link("views/rul_risk.py", label="RUL and risk detail", icon=":material/timelapse:")
links[2].page_link("views/explainability.py", label="Full explanation", icon=":material/account_tree:")
links[3].page_link("views/twin.py", label="Open 3D model", icon=":material/view_in_ar:")
