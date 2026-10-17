"""Admin, sensor history: health score over the unit's life, every sensor's drift and curves, all units."""

import streamlit as st

from app import insights, theme
from app.components import (
    CONDITION_LABELS, drift_table, health_chart, require_model, require_result, sensor_chart, show_table, unit_picker,
)
from src.config import CRITICAL_HEALTH_MULTIPLE
from src.explainability.sensor_names import describe

artifacts = require_model()
result = require_result()
spec = result.spec
noun = spec.actions.get("noun", "unit")
theme.page_head("Sensor history", f"The health score measures drift from a healthy, new-{noun} baseline (0 = like new, "
                f"higher = more degraded). Above the abnormal threshold the {noun} is flagged.")
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
    theme.stat(f"{spec.time_title}s observed", int(row["cycle"])),
    theme.stat("Readings outside training range", int(unit_history["out_of_range"].sum())),
])

theme.section(f"Health score over the {noun}'s life")
theme.chart(health_chart(unit_history, threshold, critical), key="health_curve")

theme.section("Sensor drift", f"latest {spec.time_title.lower()}, strongest first")
drift_table(insights.sensor_drift(unit_history, artifacts.health), unit=spec.life_unit)

theme.section("Degradation curves", f"raw reading and 10-{spec.time_title.lower()} mean")
# Start with the sensors that most influenced this unit's RUL prediction.
factors = row["rul_factors"] if isinstance(row.get("rul_factors"), list) else []
default = [f["sensor"] for f in factors if f["sensor"] in artifacts.sensors][:3] or artifacts.sensors[:3]
chosen = st.multiselect("Sensors", artifacts.sensors, default=default, format_func=describe)
if chosen:
    theme.chart(sensor_chart(unit_history, chosen), key="sensor_curves")

theme.section(f"All {spec.unit_plural}", "by health score")
abnormal_only = st.toggle(f"Abnormal {spec.unit_plural} only")
units = result.units[result.units["health_condition"] == "abnormal"] if abnormal_only else result.units
show_table(units.sort_values("health_score", ascending=False), ["Engine", "State", "Cycles", "Health", "Condition", "Flags"])
