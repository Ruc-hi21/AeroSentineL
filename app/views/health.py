"""Degradation, the maintainer view: how worn the unit is, since when, and which sensors show it.
Every sensor's drift and curves, and the all-units table, are in Admin, sensor history."""

import streamlit as st

from app import insights, theme
from app.components import require_model, require_result, simple_health_chart, unit_picker
from app.theme import STATES
from src.config import CRITICAL_HEALTH_MULTIPLE

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

st.page_link("views/admin_degradation.py", label="Sensor history (admin): every sensor, curves and all units",
             icon=":material/admin_panel_settings:")
