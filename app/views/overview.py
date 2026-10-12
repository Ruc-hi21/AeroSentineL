"""Fleet overview: which engines need attention, and how the fleet is distributed."""

import plotly.graph_objects as go
import streamlit as st

from app import insights, theme
from app.components import (
    FAULT_TEXT, PROFILE_LABELS, SAMPLES, fleet, get_result, health_heatmap, ladder_chart, load_benchmark, profile_spec,
    require_model, run_analysis, sample_button, sensor_label, show_table,
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

# ---------------------------------------------------------------- landing page (nothing loaded yet)
# Each card: component key, sample profile, name, what the 3D model shows, the data behind the model.
CARDS = [
    ("turbofan", "FD001", "Turbofan engine", "Two-spool turbofan, 21 sensors along the gas path",
     "NASA C-MAPSS, 4 fleets, 709 engines"),
    ("battery", "PCOE", "Li-ion battery cell", "Sectioned 18650 cell in its module with BMS and cooling",
     "NASA PCoE ageing tests, 34 cells"),
    ("bearing", "FEMTO", "Engine gearbox", "Two-stage helical gearbox with casing accelerometers",
     "FEMTO-ST PRONOSTIA run-to-failure, 17 tests"),
    ("hydraulic", "UCI", "Hydraulic system", "Test rig with pump, valve, accumulator, cooler and cylinder",
     "ZeMA hydraulic rig, 2,205 load cycles"),
    ("power", "IGBT", "Power electronics", "Three-phase IGBT inverter, monitored module cut open",
     "NASA PCoE IGBT thermal-overstress ageing"),
]


def card_metric(bench, profile):
    """The honest headline for a card: test and cross-validated risk-band accuracy of its model."""
    rows = (bench or {}).get("subsets", {})
    row = rows.get(profile)
    if not row:
        return "model not trained"
    if profile == "FD001":
        turbo = [r["test_accuracy"] for r in rows.values() if r.get("component", "turbofan") == "turbofan"]
        return f"{min(turbo):.0%} to {max(turbo):.0%} risk band, test"
    if profile == "IGBT":
        return f"{row['cv_accuracy']:.0%} cross-validated; 4 devices, indicative"
    return f"{row['test_accuracy']:.0%} risk band test, {row['cv_accuracy']:.0%} cross-validated"


# A card link (?sample=<profile>) opens that sample fleet: load it, clear the link, show the fleet.
_sample = st.query_params.get("sample")
if _sample in SAMPLES and SAMPLES[_sample].exists():
    with st.spinner(f"Analyzing the {PROFILE_LABELS[_sample].lower()} sample fleet"):
        run_analysis(SAMPLES[_sample].name, SAMPLES[_sample].read_bytes(), subset=_sample)
    st.query_params.clear()
    st.rerun()

if result is None or result.units is None:
    bench = load_benchmark()
    router = (bench or {}).get("router") or {}
    left, right = st.columns([1, 1.2], gap="large", vertical_alignment="center")
    with left:
        st.html("""<div class="as-hero" style="max-width:580px">
<div class="eyebrow"><img src="app/static/brand/logo_mark.svg" alt=""><div><b>AEROSENTINEL</b><i>Predictive maintenance console</i></div></div>
<h1>Which component fails next, <span>how soon</span>, and why</h1>
<p>Drop in a sensor log. A recognition model works out whether it comes from a turbofan, a battery cell, a gearbox, a
hydraulic system or power electronics; that component's own models forecast remaining life and risk, point to the
sensors driving it, and suggest what to do.</p></div>""")
        b1, b2 = st.columns([1.25, 1])
        with b1:
            sample_button(key="hero_sample", subset=DATASET, label="Try the NASA fleet", width="stretch")
        with b2:
            st.page_link("views/upload.py", label="Upload data", icon=":material/upload:", width="stretch")
        kpis = [(str(len(CARDS)), "component models", "public run-to-failure and test-rig data")]
        if router:
            wrong = round(router["known_misrouted"] * router["test_examples"])
            kpis.append((str(wrong), "files sent to a wrong model", f"of {router['test_examples']} unseen test files"))
        turbo = [r["test_accuracy"] for r in (bench or {}).get("subsets", {}).values() if r.get("component", "turbofan") == "turbofan"]
        if turbo:
            kpis.append((f"{max(turbo):.0%}", "turbofan risk band", f"best NASA test fleet; worst {min(turbo):.0%}"))
        st.html('<div class="as-kpis">' + "".join(
            f'<div class="as-stat"><div class="v">{esc(v)}</div><div class="l">{esc(l)}</div><div class="f">{esc(f)}</div></div>'
            for v, l, f in kpis) + "</div>")
    with right:
        engine_twin(mode="hero", height=500, key="hero_engine", component="turbofan")

    # How it works: four steps with a pulse travelling along them (the path a file takes).
    theme.section("How it works", "from a raw sensor log to a maintenance decision, in about a second")
    steps = [
        ("01", "Profile", "Read any table and check its shape, gaps, outliers and correlations.", "EDA before any model"),
        ("02", "Recognise", "Fingerprint the data and route it to the right component, or stop.",
         f"{router['test_examples']} unseen files, none misrouted" if router else "XGBoost with an 80% gate"),
        ("03", "Predict", "Correct for the operating condition, score health, forecast life or margin and risk.",
         "XGBoost, 80% range, 4 risk bands"),
        ("04", "Explain and act", "Rank the sensors behind each forecast and suggest the next step.", "SHAP for every unit"),
    ]
    st.html('<div class="as-flow">' + "".join(
        f'<div class="st"><span class="n">{n}</span><b>{esc(t)}</b><p>{esc(d)}</p><i>{esc(m)}</i></div>' for n, t, d, m in steps)
        + '<div class="pulse"></div></div>')

    # The five components: what the model sees, how well it does, and a one-click sample.
    theme.section("Five component models", "open any sample fleet; the recognition model picks the component on its own")
    # One responsive grid (5, 3, 2 or 1 across); each card is a link that opens its sample fleet.
    st.html('<div class="as-cards">' + "".join(
        f'<a class="as-card" href="?sample={profile}" target="_self">'
        f'<div class="img"><img src="app/static/brand/thumb_{key}.jpg" alt="3D model of the {esc(name)}"></div>'
        f'<div class="body"><b>{esc(name)}</b><p>{esc(shows)}</p><span class="data">{esc(data)}</span>'
        f'<span class="metric">{esc(card_metric(bench, profile))}</span><span class="go">Open sample fleet</span></div></a>'
        for key, profile, name, shows, data in CARDS) + "</div>")
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
