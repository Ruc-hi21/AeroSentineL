"""Unit status, the maintainer view: three simple things for one unit. Its condition and time left, what to
do, and why. The engineering detail (instruments, trend, drift, outlook, SHAP) is in Admin, unit detail."""

import streamlit as st

from app import insights, theme
from app.components import (
    reason_text, require_model, require_result, step_unit, unit_picker,
)
from app.theme import BAND_COLORS, BAND_TEXT, STATES, esc

artifacts = require_model()
result = require_result()
units = result.units
spec = result.spec
noun = spec.actions.get("noun", "unit")
theme.page_head(f"{spec.unit_title} status", f"Is this {noun} all right, how long has it got, and what should be done.",
                f"<b>{esc(st.session_state.get('source_name', ''))}</b><br>{insights.count(len(units), spec)}")

pick, prev, nxt, _ = st.columns([3.2, 0.7, 0.7, 4.4], vertical_alignment="bottom")
with pick:
    row = unit_picker(units, key="engine", label=f"{spec.unit_title} (most urgent first)")
prev.button("Previous", key="engine_prev", on_click=step_unit, args=(units, "engine", -1), width="stretch")
nxt.button("Next", key="engine_next", on_click=step_unit, args=(units, "engine", 1), width="stretch")

unit = int(row["unit"])
hist = result.history[result.history["unit"] == unit].sort_values("cycle")
drift = insights.sensor_drift(hist, artifacts.health)
state = insights.engine_state(row)
has_rul = "predicted_rul" in row and row["predicted_rul"] == row["predicted_rul"]


# 1. Condition and time left.
theme.section(f"1. Condition and {insights.life_word(spec)} left", f"at its latest reading, {spec.time_title.lower()} {int(row['cycle'])}")
items = [theme.stat("Condition", STATES[state]["label"], color=STATES[state]["color"])]
if has_rul:
    items.append(theme.stat(f"{spec.rul_short} left", insights.life(row["predicted_rul"], spec),
                            foot=f"likely between {insights.life(row['rul_low'], spec)} and {insights.life(row['rul_high'], spec)}"))
if isinstance(row.get("risk_band"), str):
    items.append(theme.stat("Risk", BAND_TEXT[row["risk_band"]], color=BAND_COLORS[row["risk_band"]],
                            foot=f"the model is {row['risk_probability']:.0%} sure"))
theme.stats(items)
theme.note(esc(insights.state_reason(row, state)))
found = insights.parts(row)
if found:  # hydraulic: the condition of each assessed part, in words
    sev = {0: "HEALTHY", 1: "DEGRADING", 2: "WARNING", 3: "CRITICAL"}
    theme.stats([theme.stat(p["name"], p["label"], color=STATES[sev[p["severity"]]]["color"]) for p in found])

left, right = st.columns(2, gap="large")
with left:
    # 2. What to do.
    theme.section("2. What to do")
    theme.actions(insights.recommendations(row, state, drift)[:3])
with right:
    # 3. Why: the sensors that moved the prediction most, in words.
    theme.section("3. Why", "the three sensors that moved the prediction most")
    factors = row.get("rul_factors")
    if isinstance(factors, list) and factors:
        theme.actions([{"action": what, "why": why} for what, why in (reason_text(f, spec) for f in factors[:3])])
    else:
        st.info("No explanation is available for this analysis.")
theme.note("Guidance from AeroSentinel's risk limits and sensor drift. Confirm against approved maintenance data before acting.")

st.divider()
links = st.columns(4)
links[0].page_link("views/health.py", label="Degradation", icon=":material/trending_down:")
links[1].page_link("views/rul_risk.py", label=f"{spec.rul_short} and risk", icon=":material/timelapse:")
links[2].page_link("views/explainability.py", label="Explanations", icon=":material/account_tree:")
links[3].page_link("views/twin.py", label="3D model", icon=":material/view_in_ar:")
st.page_link("views/engine_detail.py", label=f"{spec.unit_title} detail: instruments, trend, every sensor, outlook and SHAP",
             icon=":material/monitor_heart:")
