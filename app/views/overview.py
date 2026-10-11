"""Fleet overview: which engines need attention, and how the fleet is distributed."""

import plotly.graph_objects as go
import streamlit as st

from app import insights, theme
from app.components import (
    FAULT_TEXT, fleet, get_result, health_heatmap, ladder_chart, load_benchmark, profile_spec, require_model, sample_button,
    sample_choice, sensor_label, show_table,
)
from app.engine3d import engine_twin
from app.theme import MONO, SANS, TOKENS, esc
from src.config import CRITICAL_HEALTH_MULTIPLE, DATASET, SUBSETS
from src.models.artifacts import load_artifacts, model_status


def open_engine(unit):
    st.session_state["selected_unit"] = int(unit)
    st.switch_page("views/engine.py")


result = get_result()
status = model_status()

# ---------------------------------------------------------------- empty state
HERO = {"turbofan": "Turbofan", "battery": "Battery cell", "bearing": "Gearbox", "hydraulic": "Hydraulics",
        "power": "Power electronics"}
if result is None or result.units is None:
    left, right = st.columns([1, 1.25], gap="large", vertical_alignment="center")
    with left:
        st.html("""<div class="as-hero" style="max-width:560px">
<div class="eyebrow"><img src="app/static/brand/logo_mark.svg" alt=""><div><b>AEROSENTINEL</b><i>Predictive maintenance console</i></div></div>
<h1>Component health, <span>remaining life</span> and failure risk</h1>
<p>Turbofan engines, Li-ion battery cells, engine gearboxes, hydraulic systems and power electronics.
Upload sensor data and a recognition model decides which component it comes from, then that component's own models
predict condition, remaining life (or condition margin) and risk, and explain why.</p></div>""")
        choice = sample_choice("hero_choice")
        b1, b2, _ = st.columns([1.3, 1.1, 1])
        with b1:
            sample_button(key="hero_sample", subset=choice)
        with b2:
            st.page_link("views/upload.py", label="Upload a file", icon=":material/upload:")
        bench = load_benchmark()
        if bench and bench.get("subsets"):
            rows = bench["subsets"]
            turbo = [r for r in rows.values() if r.get("component", "turbofan") == "turbofan"]
            acc = [r["test_accuracy"] for r in turbo]
            router = bench.get("router") or {}
            items = [theme.stat("Component models", f"{len({r.get('component', 'turbofan') for r in rows.values()})}",
                                foot=f"{len(rows)} trained profiles")]
            if router:
                items.append(theme.stat("Files routed correctly", f"{router['known_routed_correctly']:.0%}",
                                        foot=f"recognition model, {router['test_examples']} unseen test files"))
            if acc:
                items.append(theme.stat("Turbofan risk accuracy", f"{min(acc):.0%} to {max(acc):.0%}", foot="NASA test sets"))
            theme.stats(items)
        theme.note("Input: one row per unit and cycle (or minute), with the component's channels. Turbofan files use the "
                   "NASA C-MAPSS layout; battery and bearing files are CSV with a header row (see Ingest data).")
    with right:
        hero = st.pills("3D model", list(HERO), default="turbofan", format_func=HERO.get, key="hero_component",
                                    label_visibility="collapsed")
        engine_twin(mode="hero", height=440, key="hero_engine", component=hero or "turbofan")
    st.stop()

# ---------------------------------------------------------------- fleet
units = fleet(result)
source = st.session_state.get("source_name", "")
spec = result.spec
theme.page_head("Fleet overview", f"{spec.unit_plural.capitalize()} ranked by urgency. Select one in the chart or the queue to open it.",
                f"<b>{esc(source)}</b><br>{len(units)} {spec.unit_plural}, {len(result.history):,} {spec.time_title.lower()}s<br>"
                f"job {esc(result.job_id)}, {result.duration_ms:.0f} ms")
theme.spec(profile_spec(result))
theme.distribution(insights.state_counts(units))

has_rul = "predicted_rul" in units
left, right = st.columns([1.3, 1], gap="large")
with left:
    show_all = st.session_state.get("fleet_all", False)
    theme.section(f"{spec.rul_short} forecast", f"80% range and point estimate, {'all ' + spec.unit_plural if show_all else 'top 25 by urgency'}")
    st.toggle(f"Show all {spec.unit_plural}", key="fleet_all")
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
    theme.section("Attention queue", f"{len(attention)} {spec.unit_plural} not healthy, select a row to open")
    df, event = show_table(attention if len(attention) else units.head(10),
                           ["Engine", "State", "RUL", "Range", "Confidence"],
                           key="fleet_queue", on_select="rerun", height=min(36 * (len(attention) + 1) + 4, 560))
    rows = event.selection.rows if event and event.selection else []
    if rows:
        open_engine(df.iloc[rows[0]]["_unit"])

left, right = st.columns([1.3, 1], gap="large")
with left:
    theme.section("Health trend", f"health score over the last 60 {spec.time_title.lower()}s, 20 most urgent {spec.unit_plural}")
    threshold = require_model().health.threshold
    theme.chart(health_heatmap(units, result.history, threshold, CRITICAL_HEALTH_MULTIPLE * threshold), key="fleet_heat")
    theme.note(f"Grey is within the healthy baseline. Colour starts at the abnormal threshold ({threshold:.2f}) "
               f"and reaches red at the critical level ({CRITICAL_HEALTH_MULTIPLE * threshold:.2f}).")
with right:
    theme.section("Fleet drivers", f"mean |SHAP| on predicted {spec.rul_short}, {spec.life_unit} per {spec.actions.get('noun', 'unit')}")
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
            hovertemplate="%{y}<br>%{x:.2f} " + spec.life_unit + "<extra></extra>"))
        fig.update_layout(height=320, margin=dict(t=8, b=40, l=8, r=40), xaxis_title=f"mean |SHAP| ({spec.life_unit})",
                          yaxis=dict(ticks="", tickfont=dict(family=SANS, size=12, color=TOKENS["text_2"])))
        theme.chart(fig, key="fleet_drivers")
        comp = result.component or "turbofan"
        faults = SUBSETS.get(result.subset, {}).get("fault_modes", ())
        if comp == "battery":
            theme.note("Battery life is set by capacity fade, so state of health, capacity and the charge timings that "
                       "track it are expected to lead; the operating settings show how temperature and load speed it up.")
        elif comp == "bearing":
            theme.note("Gearbox bearing damage shows up as rising vibration energy and impulsiveness on the casing, so RMS, "
                       "band energies and kurtosis are expected to lead, mostly in the last hour before failure.")
        elif comp == "hydraulic":
            theme.note("Cooler fouling shows in the oil temperatures and cooling efficiency, valve lag in the pressure profile "
                       "after the valve, and pump leakage in the main flow profile, so those channels are expected to lead.")
        elif comp == "power":
            theme.note("Thermal overstress wears the die attach and bond wires, so the on-state voltage, on-resistance and "
                       "package temperature are expected to lead. Four devices only: read the drivers as indicative.")
        elif "Fan" in faults:
            theme.note(f"{esc(result.subset)} has two fault modes, {FAULT_TEXT['HPC']} and {FAULT_TEXT['Fan']}, so fan speed "
                       "and bypass channels can lead alongside the compressor pressures and temperatures.")
        else:
            theme.note(f"{esc(result.subset)} has a single fault mode, high-pressure compressor degradation, so HPC "
                       "pressure and temperature channels are expected to lead.")
    else:
        st.info("Explanations are unavailable for this analysis.")
