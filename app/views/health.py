"""Degradation, told through the sensors: which part is affected, how many sensors are past the warning level,
which one is rising fastest and since when; then the drift now, how it built up (the strongest sensors as lines,
or every sensor as a timeline), and an inspector that opens any one sensor in full."""

import streamlit as st

from app import insights, theme
from app.components import drift_bars, drift_heatmap, drift_lines, focus_chart, require_model, require_result, unit_picker
from app.theme import STATES, esc
from src.explainability.sensor_names import SENSOR_INFO

LEVEL_STATE = {"Critical": "CRITICAL", "Warning": "WARNING", "Elevated": "DEGRADING"}
TOP_BARS = 10  # sensors on the drift chart; components have 7 to 29
INSPECT = 8  # sensors offered as one-click chips in the inspector

artifacts = require_model()
result = require_result()
spec = result.spec
noun = spec.actions.get("noun", "unit")
t = spec.time_title.lower()
theme.page_head("Degradation", f"Which part of the {noun} is wearing, which sensors show it, and how fast it is moving.",
                kicker=f"{spec.name} · sensor evidence")

pick, _, help_col = st.columns([3.2, 4.0, 1.8], vertical_alignment="bottom")
with pick:
    row = unit_picker(result.units, key="health")
with help_col:
    theme.guide([
        ("Drift", "How far a reading sits from a healthy one, in standard deviations (σ), in the direction wear pushes that sensor."),
        ("Levels", "Elevated from 1.6σ, warning from 2.4σ, critical from 3.2σ."),
        ("Ranking", "Drift of each sensor at the latest reading, strongest first."),
        ("Build-up", "Switch between the three strongest sensors as lines and every sensor as a timeline."),
        ("Inspector", "Click a sensor chip to see its raw reading above its drift, on one time axis."),
    ])
hist = result.history[result.history["unit"] == row["unit"]].sort_values("cycle")
drift = insights.sensor_drift(hist, artifacts.health)  # strongest first
now = int(row["cycle"])

# Where, how many, how fast, since when.
counts = drift["status"].value_counts()
crit, warn, elev = (int(counts.get(k, 0)) for k in ("Critical", "Warning", "Elevated"))
worst = drift.iloc[0]
rising = drift.sort_values("trend", ascending=False).iloc[0]
z = artifacts.health.sensor_deviation(hist).rolling(insights.DRIFT_SMOOTHING, min_periods=1).mean()
past = hist.loc[(z >= 2.4).any(axis=1).to_numpy(), "cycle"]
ago = now - int(past.iloc[0]) if len(past) else 0
theme.section("Sensor condition", f"{len(drift)} sensors at {t} {now}", kicker="Latest reading")
theme.stats([
    theme.stat("Most affected part", worst["module"] if worst["status"] != "Nominal" else "None",
               foot=f"{esc(worst['name'])} ({esc(worst['code'])}) at {worst['drift']:+.1f}σ",
               color=STATES[LEVEL_STATE[worst["status"]]]["color"] if worst["status"] != "Nominal" else None,
               tip="The part that carries the most-drifted sensor. It shows where the evidence is measured, not a confirmed root cause."),
    theme.stat("Past the warning level", f"{crit + warn} of {len(drift)}", meter=(crit + warn) / max(1, len(drift)),
               foot=f"{crit} critical, {warn} warning; {elev} more elevated",
               color=STATES["CRITICAL" if crit else "WARNING"]["color"] if crit + warn else None,
               tip="Sensors whose drift is 2.4 standard deviations or more from a healthy reading."),
    theme.stat("Rising fastest", rising["code"] if rising["trend"] >= 0.1 else "None",
               foot=f"{esc(rising['name'])}: {rising['trend']:+.1f}σ per 10 {t}s" if rising["trend"] >= 0.1
               else "no sensor is moving away from healthy",
               tip=f"The sensor whose drift grew most over the latest 20 {t}s."),
    theme.stat("Warning since", f"{spec.time_title} {int(past.iloc[0])}" if len(past) else "Not yet",
               foot=f"{ago} {t}{'' if ago == 1 else 's'} ago" if len(past) else "no sensor has passed 2.4σ yet",
               tip="The first reading at which any sensor crossed the warning level."),
])

top = drift.head(3)["sensor"].tolist()
left, right = st.columns([1, 1.1], gap="large")
with left:
    # Every sensor's drift now (the strongest ones when there are many).
    theme.section("Drift ranking", f"the {TOP_BARS} strongest of {len(drift)} sensors" if len(drift) > TOP_BARS
                  else "every sensor, strongest first", kicker="Now")
    theme.chart(drift_bars(drift, spec, top=TOP_BARS), key="health_drift_bars")
with right:
    # How it got there: the strongest sensors as lines, or every sensor as a timeline.
    theme.section("Drift build-up", f"over the {noun}'s life", kicker="History")
    view = st.segmented_control("Build-up view", ["Strongest sensors", "Every sensor"], default="Strongest sensors",
                                key="health_buildup", label_visibility="collapsed") or "Strongest sensors"
    if view == "Strongest sensors":
        theme.chart(drift_lines(hist, artifacts.health, top, spec, height=6 + 26 * min(len(drift), TOP_BARS)),
                    key="health_drift_lines")
    else:
        theme.chart(drift_heatmap(hist, artifacts.health, spec), key="health_drift_heatmap")
theme.note("Drift is how far a reading sits from a healthy one, in the direction wear pushes that sensor. "
           "Elevated from 1.6σ, warning from 2.4σ, critical from 3.2σ.")

# One sensor in full: the raw reading above its drift.
theme.section("Sensor inspector", "pick a sensor: its reading above its drift, on one time axis", kicker="Inspect")
offered = drift.head(INSPECT)["sensor"].tolist()
chosen = st.pills("Sensor", offered, default=offered[0], key=f"health_inspect_{spec.key}", label_visibility="collapsed",
                  format_func=lambda s: f"{SENSOR_INFO[s][0]}  {SENSOR_INFO[s][1]}") or offered[0]
picked = drift.set_index("sensor").loc[chosen]
theme.chart(focus_chart(hist, artifacts.health, chosen, spec), key="health_focus")
theme.note(f"{esc(picked['name'])} ({esc(picked['code'])}) sits on the {esc(picked['module'])}. It reads {picked['value']:.2f} "
           f"{esc(picked['unit'])} now, {picked['drift']:+.1f}σ from healthy, and peaked at {picked['peak']:+.1f}σ. "
           "Grey is the raw reading, blue its 10-reading mean.")
out = int(hist["out_of_range"].sum())
if out:
    theme.note(f"{out} readings of this {noun} fall outside the range seen in training.")
