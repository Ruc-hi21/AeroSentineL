"""Degradation, told through the sensors: how many are drifting and how far, which ones, how their drift built up
over the unit's life, and their raw readings."""

import streamlit as st

from app import insights, theme
from app.components import drift_bars, drift_heatmap, require_model, require_result, sensor_chart, unit_picker
from app.theme import STATES
from src.explainability.sensor_names import describe

artifacts = require_model()
result = require_result()
spec = result.spec
noun = spec.actions.get("noun", "unit")
t = spec.time_title.lower()
theme.page_head("Degradation", f"How the {noun}'s sensors have moved away from a healthy reading, which ones, and since when. "
                "Drift is counted in standard deviations from a healthy unit.")

row = unit_picker(result.units, key="health")
hist = result.history[result.history["unit"] == row["unit"]].sort_values("cycle")
drift = insights.sensor_drift(hist, artifacts.health)

# 1. Sensor condition today: how many sensors sit at each level, and since when any has been past the warning limit.
counts = drift["status"].value_counts()
z = artifacts.health.sensor_deviation(hist).rolling(5, min_periods=1).mean()
past = hist.loc[(z >= 2.4).any(axis=1).to_numpy(), "cycle"]
theme.section("1. Sensor condition today", f"{len(drift)} sensors at {t} {int(row['cycle'])}")
theme.stats([
    theme.stat("Critical", int(counts.get("Critical", 0)), foot="3.2 standard deviations or more",
               color=STATES["CRITICAL"]["color"] if counts.get("Critical", 0) else None),
    theme.stat("Warning", int(counts.get("Warning", 0)), foot="2.4 or more",
               color=STATES["WARNING"]["color"] if counts.get("Warning", 0) else None),
    theme.stat("Elevated", int(counts.get("Elevated", 0)), foot="1.6 or more",
               color=STATES["DEGRADING"]["color"] if counts.get("Elevated", 0) else None),
    theme.stat("Normal", int(counts.get("Nominal", 0)), foot="below 1.6"),
    theme.stat("Warning since", f"{t} {int(past.iloc[0])}" if len(past) else "not yet",
               foot="first reading with a sensor past 2.4"),
])

left, right = st.columns([1.4, 1], gap="large")
with left:
    # 2. Every sensor's drift now.
    theme.section("2. Drift now", "every sensor, strongest first; dotted lines are the levels")
    theme.chart(drift_bars(drift, spec), key="health_drift_bars")
with right:
    # 3. The sensors that moved most, in words.
    theme.section("3. Sensors that show it", "furthest from a healthy reading")
    level = {"Critical": "far from normal", "Warning": "clearly drifting", "Elevated": "starting to drift",
             "Nominal": "normal"}
    theme.actions([{"action": f"{d['name']} ({d['code']})",
                    "why": f"{level[d['status']].capitalize()}: {d['drift']:+.1f} standard deviations from a healthy "
                           f"{noun}, peak {d['peak']:+.1f}."}
                   for _, d in drift.head(3).iterrows()])

# 4. How the drift built up over the unit's life, sensor by sensor.
theme.section(f"4. Drift over the {noun}'s life", "each row a sensor, strongest now on top; red = drifting with wear, "
              "blue = moving the other way")
theme.chart(drift_heatmap(hist, artifacts.health, spec), key="health_drift_heatmap")

# 5. The raw readings behind it.
theme.section("5. Raw readings", f"reading and 10-{t} mean")
factors = row["rul_factors"] if isinstance(row.get("rul_factors"), list) else []
default = [f["sensor"] for f in factors if f["sensor"] in artifacts.sensors][:3] or artifacts.sensors[:3]
chosen = st.multiselect("Sensors", artifacts.sensors, default=default, format_func=describe, key="health_curves")
if chosen:
    theme.chart(sensor_chart(hist, chosen), key="sensor_curves")
out = int(hist["out_of_range"].sum())
if out:
    theme.note(f"{out} readings of this {noun} fall outside the range seen in training.")
