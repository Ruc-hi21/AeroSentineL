"""Degradation: how worn the unit is, since when, and which sensors show it; then the detail (every sensor's
drift and raw curves, and every unit by health) in two tabs."""

import streamlit as st

from app import insights, theme
from app.components import (
    drift_table, require_model, require_result, sensor_chart, show_table, simple_health_chart, unit_picker,
)
from app.theme import STATES
from src.config import CRITICAL_HEALTH_MULTIPLE
from src.explainability.sensor_names import describe

artifacts = require_model()
result = require_result()
spec = result.spec
noun = spec.actions.get("noun", "unit")
theme.page_head("Degradation", f"How far this {noun} has moved away from a new, healthy {noun}. "
                "0 means like new; the higher the score, the more worn.")
threshold = artifacts.health.threshold
critical = CRITICAL_HEALTH_MULTIPLE * threshold

row = unit_picker(result.units, key="health")
hist = result.history[result.history["unit"] == row["unit"]].sort_values("cycle")
score = float(row["health_score"])
status = "CRITICAL" if score > critical else "DEGRADING" if score > threshold else "HEALTHY"
words = {"CRITICAL": "Critical", "DEGRADING": "Abnormal", "HEALTHY": "Healthy"}
t = spec.time_title.lower()

# 1. How worn, and since when.
over = hist.loc[hist["health_score"] > threshold, "cycle"]
since = f"{t} {int(over.iloc[0])}" if len(over) else "not yet"
theme.section("1. Wear today")
theme.stats([
    theme.stat("Health score", f"{score:.2f}", foot=f"healthy up to {threshold:.2f}, critical above {critical:.2f}",
               color=STATES[status]["color"]),
    theme.stat("Condition", words[status], color=STATES[status]["color"]),
    theme.stat("Abnormal since", since, foot=f"first {t} above the healthy limit"),
])

left, right = st.columns([1.5, 1], gap="large")
with left:
    # 2. The score over the unit's life, on plain zones.
    theme.section(f"2. Health over the {noun}'s life", f"one point per {t}")
    theme.chart(simple_health_chart(hist, threshold, critical, spec), key="health_simple")
    theme.note(f"The line climbs as the {noun} wears. Green is healthy, amber is abnormal, red is critical.")
    if spec.diagnosis:
        theme.note(f"The score averages every sensor, so one failed part can leave it low. The part-by-part condition is "
                   f"on the {spec.unit_title.lower()} status page.")
with right:
    # 3. The sensors that moved most, in words.
    theme.section("3. Sensors that show it", "furthest from a healthy reading")
    drift = insights.sensor_drift(hist, artifacts.health)
    level = {"Critical": "far from normal", "Warning": "clearly drifting", "Elevated": "starting to drift",
             "Nominal": "normal"}
    theme.actions([{"action": f"{d['name']} ({d['code']})",
                    "why": f"{level[d['status']].capitalize()}: {d['drift']:+.1f} standard deviations from a healthy {noun}."}
                   for _, d in drift.head(3).iterrows()])

# Detail (formerly Sensor history): every sensor for this unit, and every unit by health.
theme.section("More detail")
tab_sensors, tab_units = st.tabs(["Every sensor", f"All {spec.unit_plural}"])
with tab_sensors:
    left, right = st.columns([1, 1.2], gap="large")
    with left:
        theme.section("Sensor drift", f"latest {t}, strongest first")
        drift_table(drift, unit=spec.life_unit)
    with right:
        theme.section("Raw curves", f"reading and 10-{t} mean")
        # Start with the sensors that most influenced this unit's RUL prediction.
        factors = row["rul_factors"] if isinstance(row.get("rul_factors"), list) else []
        default = [f["sensor"] for f in factors if f["sensor"] in artifacts.sensors][:3] or artifacts.sensors[:3]
        chosen = st.multiselect("Sensors", artifacts.sensors, default=default, format_func=describe, key="health_curves")
        if chosen:
            theme.chart(sensor_chart(hist, chosen), key="sensor_curves")
    theme.note(f"{int(hist['out_of_range'].sum())} readings of this {noun} fall outside the range seen in training.")
with tab_units:
    abnormal_only = st.toggle(f"Abnormal {spec.unit_plural} only", key="health_abnormal_only")
    units = result.units[result.units["health_condition"] == "abnormal"] if abnormal_only else result.units
    show_table(units.sort_values("health_score", ascending=False), ["Engine", "State", "Cycles", "Health", "Condition", "Flags"])
