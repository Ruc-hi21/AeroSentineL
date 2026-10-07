"""3D model: every C-MAPSS sensor at its engine station, with a replay of the recorded life."""

import plotly.graph_objects as go
import streamlit as st

from app import insights, theme
from app.components import require_model, require_result, unit_picker
from app.engine3d import Z_SMOOTHING, engine_twin, twin_payload
from app.theme import TOKENS, esc
from src.explainability.sensor_names import SENSOR_INFO, describe

theme.page_head("3D model", "Sectioned turbofan with each sensor at its station. Opens on the latest reading; "
                "Replay steps through the recorded history cycle by cycle.")
artifacts = require_model()
result = require_result()

row = unit_picker(result.units, key="twin")
unit = int(row["unit"])
payload = twin_payload(result, unit, artifacts.health, st.session_state.get("source_name", ""))
picked = engine_twin(payload, height=800, key="twin_view")

hist = result.history[result.history["unit"] == unit].sort_values("cycle")
factors = row["rul_factors"] if isinstance(row.get("rul_factors"), list) else []
default = next((f["sensor"] for f in factors if f["sensor"] in artifacts.sensors), artifacts.sensors[0])
sensor = picked["sensor"] if isinstance(picked, dict) and picked.get("unit") == unit and picked.get("sensor") in hist else default
code, name, unit_label, _ = SENSOR_INFO[sensor]

theme.section(f"{code}  {name}", "selected in the model; click another sensor to change")
left, right = st.columns([1.6, 1], gap="large")
with left:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["cycle"], y=hist[sensor], mode="lines", name="Reading",
                             line=dict(color=TOKENS["text_3"], width=1), opacity=0.7))
    fig.add_trace(go.Scatter(x=hist["cycle"], y=hist[sensor].rolling(10, min_periods=1).mean(), mode="lines",
                             name="10-cycle mean", line=dict(color=TOKENS["accent"], width=2)))
    if sensor in artifacts.health.sensors:
        h = artifacts.health
        base = h.mean[sensor]
        fig.add_hline(y=base, line=dict(color=TOKENS["text_2"], width=1, dash="dot"), annotation_text="healthy baseline",
                      annotation_position="top left")
        for k, color in [(2.4, "#ff832b"), (3.2, "#fa4d56")]:
            fig.add_hline(y=base + k * h.std[sensor] * h.direction[sensor], line=dict(color=color, width=1, dash="dash"),
                          annotation_text=f"{k} sigma", annotation_position="top left", annotation_font=dict(color=color))
    fig.update_layout(height=340, xaxis_title="cycle", yaxis_title=f"{code} ({unit_label})" if unit_label else code)
    theme.chart(fig, key="twin_sensor")
with right:
    if sensor in artifacts.health.sensors:
        drift = artifacts.health.sensor_deviation(hist).rolling(Z_SMOOTHING, min_periods=1).mean()[sensor]
        now, peak = float(drift.iloc[-1]), float(drift.max())
        level = next((label for limit, label in insights.DRIFT_LEVELS if now >= limit), "Nominal")
        theme.stats([
            theme.stat("Drift now", f"{now:+.1f}", "sigma", foot=level),
            theme.stat("Peak drift", f"{peak:+.1f}", "sigma"),
        ])
        theme.kv([("Module", esc(insights.MODULE_NAMES[insights.SENSOR_MODULE[sensor]])),
                  ("Latest reading", f"{hist[sensor].iloc[-1]:.2f} {esc(unit_label)}"),
                  ("Healthy baseline", f"{artifacts.health.mean[sensor]:.2f} {esc(unit_label)}")])
    else:
        theme.empty("Constant channel", f"{esc(describe(sensor))} does not change in FD001 (single operating condition), "
                    "so the model does not use it. It is shown for completeness.")
    impact = next((f["impact"] for f in factors if f["sensor"] == sensor), None)
    theme.note(f"SHAP: this sensor changed the predicted RUL by {impact:+.1f} cycles." if impact is not None
               else "Not among this engine's top five RUL drivers.")
