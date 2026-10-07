"""Degradation: how far the engine has drifted from a healthy baseline, and which sensors moved."""

import streamlit as st

from app import insights, theme
from app.components import (
    CONDITION_LABELS, drift_table, health_chart, require_model, require_result, sensor_chart, show_table, unit_picker,
)
from src.config import CRITICAL_HEALTH_MULTIPLE
from src.explainability.sensor_names import describe

theme.page_head("Degradation", "The health score measures drift from a healthy, new-engine baseline (0 = like new, "
                "higher = more degraded). Above the abnormal threshold the engine is flagged.")
artifacts = require_model()
result = require_result()
threshold = artifacts.health.threshold
critical = CRITICAL_HEALTH_MULTIPLE * threshold

row = unit_picker(result.units, key="health")
unit_history = result.history[result.history["unit"] == row["unit"]].sort_values("cycle")
score = row["health_score"]
status = "CRITICAL" if score > critical else "DEGRADING" if score > threshold else "HEALTHY"
theme.stats([
    theme.stat("Health score", f"{score:.2f}", foot=f"abnormal above {threshold:.2f}, critical above {critical:.2f}",
               color=theme.STATES[status]["color"]),
    theme.stat("Condition", CONDITION_LABELS[row["health_condition"]]),
    theme.stat("Cycles observed", int(row["cycle"])),
    theme.stat("Readings outside training range", int(unit_history["out_of_range"].sum())),
])

theme.section("Health score over the engine's life")
theme.chart(health_chart(unit_history, threshold, critical), key="health_curve")

theme.section("Sensor drift", "latest cycle, strongest first")
drift_table(insights.sensor_drift(unit_history, artifacts.health))

theme.section("Degradation curves", "raw reading and 10-cycle mean")
# Start with the sensors that most influenced this unit's RUL prediction.
factors = row["rul_factors"] if isinstance(row.get("rul_factors"), list) else []
default = [f["sensor"] for f in factors if f["sensor"] in artifacts.sensors][:3] or artifacts.sensors[:3]
chosen = st.multiselect("Sensors", artifacts.sensors, default=default, format_func=describe)
if chosen:
    theme.chart(sensor_chart(unit_history, chosen), key="sensor_curves")

theme.section("All engines", "by health score")
abnormal_only = st.toggle("Abnormal engines only")
units = result.units[result.units["health_condition"] == "abnormal"] if abnormal_only else result.units
show_table(units.sort_values("health_score", ascending=False), ["Engine", "State", "Cycles", "Health", "Condition", "Flags"])
