"""Fleet overview: which engines need attention, and how the fleet is distributed."""

import plotly.graph_objects as go
import streamlit as st

from app import insights, theme
from app.components import fleet, get_result, health_heatmap, ladder_chart, sample_button, sensor_label, show_table
from app.engine3d import engine_twin
from app.theme import MONO, SANS, TOKENS, esc
from src.config import CRITICAL_HEALTH_MULTIPLE
from src.models.artifacts import load_artifacts, model_status


def open_engine(unit):
    st.session_state["selected_unit"] = int(unit)
    st.switch_page("views/engine.py")


result = get_result()
status = model_status()

# ---------------------------------------------------------------- empty state
if result is None or result.units is None:
    left, right = st.columns([1, 1.25], gap="large", vertical_alignment="center")
    with left:
        st.html("""<div style="max-width:520px">
<h1 style="font-size:28px;font-weight:600;margin:0 0 10px;padding:0;line-height:1.2">Turbofan health, remaining life and failure risk</h1>
<p style="font-size:15px;color:#a6adb6;margin:0;line-height:1.55">Load engine sensor data to see which engines need attention,
how long each has left and why the model thinks so.</p></div>""")
        b1, b2, _ = st.columns([1.3, 1.1, 1])
        with b1:
            sample_button(key="hero_sample")
        with b2:
            st.page_link("views/upload.py", label="Upload a file", icon=":material/upload:")
        if status["ready"]:
            m = load_artifacts().metadata["metrics"]
            theme.stats([
                theme.stat("Risk accuracy, unseen engines", f"{m['validation']['risk']['xgboost']['accuracy']:.1%}"),
                theme.stat("Risk accuracy, NASA test", f"{m['test']['risk']['accuracy']:.1%}"),
                theme.stat("RUL error, NASA test", f"{m['test']['rul']['rmse']:.1f}", "cycles RMSE"),
            ])
        theme.note("Input: NASA C-MAPSS format, one row per engine cycle with 21 sensors. Output per engine: condition, "
                   "RUL with an 80% range, a four-level risk band and the sensors that drove the prediction.")
    with right:
        engine_twin(mode="hero", height=440, key="hero_engine")
    st.stop()

# ---------------------------------------------------------------- fleet
units = fleet(result)
source = st.session_state.get("source_name", "")
theme.page_head("Fleet overview", "Engines ranked by urgency. Select an engine in the chart or the queue to open it.",
                f"<b>{esc(source)}</b><br>{len(units)} engines, {len(result.history):,} cycles<br>"
                f"job {esc(result.job_id)}, {result.duration_ms:.0f} ms")
theme.distribution(insights.state_counts(units))

has_rul = "predicted_rul" in units
left, right = st.columns([1.3, 1], gap="large")
with left:
    show_all = st.session_state.get("fleet_all", False)
    theme.section("RUL forecast", f"80% range and point estimate, {'all engines' if show_all else 'top 25 by urgency'}")
    st.toggle("Show all engines", key="fleet_all")
    limit = None if show_all else 25
    if has_rul:
        event = theme.chart(ladder_chart(units, limit), key="fleet_ladder", on_select="rerun")
        points = event.selection.points if event and event.selection else []
        if points:
            point = points[0]
            open_engine(point["customdata"][0] if point.get("customdata") else int(point["y"]))
    else:
        st.warning("RUL prediction failed for this analysis, so the forecast is unavailable.")
with right:
    attention = units[units["state"] != "HEALTHY"]
    theme.section("Attention queue", f"{len(attention)} engines not healthy, select a row to open")
    df, event = show_table(attention if len(attention) else units.head(10),
                           ["Engine", "State", "RUL", "Range", "Confidence"],
                           key="fleet_queue", on_select="rerun", height=min(36 * (len(attention) + 1) + 4, 560))
    rows = event.selection.rows if event and event.selection else []
    if rows:
        open_engine(df.iloc[rows[0]]["Engine"])

left, right = st.columns([1.3, 1], gap="large")
with left:
    theme.section("Health trend", "health score over the last 60 cycles, 20 most urgent engines")
    threshold = load_artifacts().health.threshold if status["ready"] else 1.0
    theme.chart(health_heatmap(units, result.history, threshold, CRITICAL_HEALTH_MULTIPLE * threshold), key="fleet_heat")
    theme.note(f"Grey is within the healthy baseline. Colour starts at the abnormal threshold ({threshold:.2f}) "
               f"and reaches red at the critical level ({CRITICAL_HEALTH_MULTIPLE * threshold:.2f}).")
with right:
    theme.section("Fleet drivers", "mean |SHAP| on predicted RUL, cycles per engine")
    if "rul_factors" in units:
        total = {}
        for factors in units["rul_factors"]:
            for f in factors if isinstance(factors, list) else []:
                total[f["sensor"]] = total.get(f["sensor"], 0.0) + abs(f["impact"])
        ranked = sorted(total.items(), key=lambda kv: kv[1])[-8:]
        fig = go.Figure(go.Bar(
            x=[v / len(units) for _, v in ranked], y=[sensor_label(s) for s, _ in ranked], orientation="h", width=0.55,
            marker_color=TOKENS["accent"], text=[f"{v / len(units):.1f}" for _, v in ranked], textposition="outside",
            cliponaxis=False, textfont=dict(family=MONO, size=11, color=TOKENS["text_2"]),
            hovertemplate="%{y}<br>%{x:.2f} cycles<extra></extra>"))
        fig.update_layout(height=320, margin=dict(t=8, b=40, l=8, r=40), xaxis_title="mean |SHAP| (cycles)",
                          yaxis=dict(ticks="", tickfont=dict(family=SANS, size=12, color=TOKENS["text_2"])))
        theme.chart(fig, key="fleet_drivers")
        theme.note("FD001 has a single fault mode, high-pressure compressor degradation, so HPC pressure and "
                   "temperature channels are expected to lead.")
    else:
        st.info("Explanations are unavailable for this analysis.")
