import plotly.graph_objects as go
import streamlit as st

from app import theme
from app.components import require_model, require_result, unit_banner, unit_picker
from app.engine3d import Z_SMOOTHING, engine_twin, twin_payload
from app.theme import CYAN, esc
from src.explainability.sensor_names import SENSOR_INFO, describe

theme.page_header("Digital twin · holographic life replay", "3D Digital Twin",
                  "Every C-MAPSS sensor pinned to its station on a live turbofan model. The replay walks the engine "
                  "through its whole recorded life: watch sensors drift, modules heat up and the risk band escalate.")
artifacts = require_model()
result = require_result()

row = unit_picker(result.units, key="twin")
unit = int(row["unit"])
payload = twin_payload(result, unit, artifacts.health, st.session_state.get("source_name", ""))
picked = engine_twin(payload, height=840, key="twin_view")

st.html("""<div class="as-card" style="padding:12px 18px"><div style="display:flex;flex-wrap:wrap;gap:22px;font-family:'Rajdhani';
font-weight:600;letter-spacing:.06em;color:#9fb3d6;font-size:.92rem">
<span>🖱️ DRAG · orbit</span><span>⚙️ SCROLL · zoom</span><span>🎯 CLICK a sensor · focus + deep-dive</span>
<span>⎵ SPACE · play/pause</span><span>E · exploded view</span><span>S · diagnostic scan</span><span>C · cinema mode</span>
<span>ESC / double-click · reset camera</span><span style="color:#b388ff">◆ = top SHAP driver</span></div></div>""")

unit_banner(row)

# ---------------------------------------------------------------- sensor deep-dive
hist = result.history[result.history["unit"] == unit].sort_values("cycle")
factors = row["rul_factors"] if isinstance(row.get("rul_factors"), list) else []
default = next((f["sensor"] for f in factors if f["sensor"] in artifacts.sensors), artifacts.sensors[0])
sensor = picked["sensor"] if isinstance(picked, dict) and picked.get("unit") == unit and picked.get("sensor") in hist else default
code, name, unit_label, _ = SENSOR_INFO[sensor]

theme.section("Sensor deep-dive", f"{code} · {name}")
left, right = st.columns([1.6, 1])
with left:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["cycle"], y=hist[sensor], mode="lines", line=dict(color=CYAN, width=1), opacity=0.35,
                             name="raw"))
    fig.add_trace(go.Scatter(x=hist["cycle"], y=hist[sensor].rolling(10, min_periods=1).mean(), mode="lines",
                             line=dict(color=CYAN, width=3), name="10-cycle mean"))
    if sensor in artifacts.health.sensors:
        h = artifacts.health
        base = h.mean[sensor]
        fig.add_hline(y=base, line_dash="dot", line_color="#19f5a0", annotation_text="healthy baseline",
                      annotation_font_color="#19f5a0")
        for k, color in [(2.4, "#ff8a1f"), (3.2, "#ff2e4d")]:
            fig.add_hline(y=base + k * h.std[sensor] * h.direction[sensor], line_dash="dash", line_color=color,
                          annotation_text=f"{k}σ drift", annotation_font_color=color)
    fig.update_layout(height=360, xaxis_title="cycle", yaxis_title=f"{code} ({unit_label})" if unit_label else code,
                      legend=dict(orientation="h", y=1.08))
    theme.chart(fig, key="twin_sensor")
with right:
    if sensor in artifacts.health.sensors:
        drift = artifacts.health.sensor_deviation(hist).rolling(Z_SMOOTHING, min_periods=1).mean()[sensor]
        now, peak = float(drift.iloc[-1]), float(drift.max())
        # Same bands as the 3D HUD (engine.js zSev): nominal / elevated / warning / critical.
        color = "#19f5a0" if now < 1.6 else "#ffd23f" if now < 2.4 else "#ff8a1f" if now < 3.2 else "#ff2e4d"
        theme.gauge_row([
            theme.gauge("Drift now", now / 5, f"{now:+.1f}σ", color, "directed z-score vs. healthy baseline"),
            theme.gauge("Peak drift", peak / 5, f"{peak:+.1f}σ", theme.VIOLET, "highest over the replay"),
        ])
    else:
        theme.card("Constant channel", f"<p>{esc(describe(sensor))} does not change in FD001 (single operating condition), "
                   "so the model does not use it. It is shown on the twin for completeness.</p>")
    impact = next((f["impact"] for f in factors if f["sensor"] == sensor), None)
    note = (f"Pushed this unit's predicted RUL by <b>{impact:+.1f} cycles</b> (SHAP)." if impact is not None
            else "Not among this unit's top-5 RUL drivers.")
    theme.card("Model attribution", f"<p>{note}</p><p style='color:#7f95bd;font-size:.85rem'>SHAP shows correlation "
               "with the prediction, not proof of a root cause.</p>")
