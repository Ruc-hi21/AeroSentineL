import streamlit as st

from app import theme
from app.components import (
    CONDITION_LABELS, health_chart, require_model, require_result, sensor_chart, show_table, unit_picker,
)
from src.config import CRITICAL_HEALTH_MULTIPLE
from src.explainability.sensor_names import describe

theme.page_header("Component health · drift from healthy baseline", "Component Health",
                  "The health score measures how far an engine's sensors have drifted from a healthy, new-engine "
                  "baseline (0 = like new, higher = more degraded). Above the dashed line the engine is flagged "
                  "<b>abnormal</b>.")
artifacts = require_model()
result = require_result()
threshold = artifacts.health.threshold
critical = CRITICAL_HEALTH_MULTIPLE * threshold

row = unit_picker(result.units, key="health")
unit_history = result.history[result.history["unit"] == row["unit"]]

score = row["health_score"]
color = "#19f5a0" if score <= threshold else "#ff8a1f" if score <= critical else "#ff2e4d"
theme.gauge_row([
    theme.gauge("Health score", score / (critical * 1.4), f"{score:.2f}", color, f"abnormal above {threshold:.2f}"),
    theme.gauge("Condition", 1.0 if row["health_condition"] == "abnormal" else 0.25,
                CONDITION_LABELS[row["health_condition"]].split(" ", 1)[1].upper(), color, "latest cycle"),
    theme.gauge("Cycles observed", min(1.0, row["cycle"] / 360), f"{int(row['cycle'])}", theme.VIOLET, "operating history"),
    theme.gauge("Out-of-range", min(1.0, unit_history["out_of_range"].sum() / 10),
                f"{int(unit_history['out_of_range'].sum())}", "#ffd23f", "readings beyond training range"),
])

theme.section("Health score", "over the engine's life")
theme.chart(health_chart(unit_history, threshold, critical), key="health_curve")

theme.section("Degradation curves", "sensor readings over time")
# Start with the sensors that most influenced this unit's RUL prediction.
factors = row["rul_factors"] if isinstance(row.get("rul_factors"), list) else []
default = [f["sensor"] for f in factors if f["sensor"] in artifacts.sensors][:3] or artifacts.sensors[:3]
chosen = st.multiselect("Sensors", artifacts.sensors, default=default, format_func=describe)
if chosen:
    theme.chart(sensor_chart(unit_history, chosen), key="sensor_curves")

theme.section("All units")
abnormal_only = st.toggle("Abnormal units only")
units = result.units[result.units["health_condition"] == "abnormal"] if abnormal_only else result.units
show_table(units.sort_values("health_score", ascending=False), ["unit", "cycle", "health", "health_score", "review"])
