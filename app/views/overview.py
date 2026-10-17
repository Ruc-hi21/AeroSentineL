"""Fleet overview: the landing page before anything is loaded; afterwards, the maintainer's fleet view
(conditions, what needs attention, time left). Ranges, history and drivers are in Admin, fleet detail."""

import pandas as pd
import streamlit as st

from app import insights, theme
from app.components import (
    SAMPLES, fleet, fleet_bars, get_result, load_benchmark, load_sample, sample_button, sample_for,
)
from app.engine3d import engine_twin
from app.theme import esc
from src.components import spec_of_profile
from src.config import DATASET
from src.models.artifacts import model_status


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


# A card link (?sample=<profile>, or a sample key like FD001_healthy) opens that sample unit's page.
_sample = st.query_params.get("sample")
_sample = _sample if _sample in SAMPLES else sample_for(_sample) if _sample else None
if _sample in SAMPLES and SAMPLES[_sample].exists():
    st.query_params.clear()
    load_sample(_sample, then="views/engine.py")

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
            sample_button(key="hero_sample", subset=DATASET, label="Try a NASA engine", width="stretch",
                          then="views/engine.py")
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
    theme.section("Five component models", "open a sample unit; the recognition model picks the component on its own")
    # One responsive grid (5, 3, 2 or 1 across); each card is a link that opens its sample unit.
    st.html('<div class="as-cards">' + "".join(
        f'<a class="as-card" href="?sample={profile}" target="_self">'
        f'<div class="img"><img src="app/static/brand/thumb_{key}.jpg" alt="3D model of the {esc(name)}"></div>'
        f'<div class="body"><b>{esc(name)}</b><p>{esc(shows)}</p><span class="data">{esc(data)}</span>'
        f'<span class="metric">{esc(card_metric(bench, profile))}</span><span class="go">Open a sample {esc(spec_of_profile(profile).unit_title.lower())}</span></div></a>'
        for key, profile, name, shows, data in CARDS) + "</div>")
    st.stop()

# ---------------------------------------------------------------- fleet (maintainer view: three simple things)
units = fleet(result)
spec = result.spec
noun = spec.actions.get("noun", "unit")
theme.page_head("Fleet overview", f"Which {spec.unit_plural} need attention first. Select one to open its status.",
                f"<b>{esc(st.session_state.get('source_name', ''))}</b><br>{insights.count(len(units), spec)}")

# 1. How the fleet stands: one count per condition.
theme.section(f"1. {spec.unit_plural.capitalize()} by condition")
theme.distribution(insights.state_counts(units))

left, right = st.columns([1.15, 1], gap="large")
with left:
    # 2. What to do first: the units that are not healthy, most urgent first, in plain words.
    attention = units[units["state"] != "HEALTHY"]
    theme.section("2. Needs attention", f"{insights.count(len(attention), spec)}, most urgent first; select a row")
    if len(attention):
        table = attention.head(15).reset_index(drop=True)
        view = pd.DataFrame({
            spec.unit_title: table["unit"].map(spec.unit_id),
            "Condition": table["state"].map(lambda s: theme.STATES[s]["label"]),
            f"{spec.rul_short} left": [insights.life(v, spec) if pd.notna(v) else "n/a" for v in table.get("predicted_rul", [None] * len(table))],
            "Next step": [insights.recommendations(r, r["state"])[0]["action"] for _, r in table.iterrows()],
        })
        event = st.dataframe(view.style.map(lambda v: f"color: {next((x['color'] for x in theme.STATES.values() if x['label'] == v), '')}",
                                            subset=["Condition"]),
                             hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                             key="fleet_simple_queue", height=min(36 * (len(view) + 1) + 4, 560))
        rows = event.selection.rows if event and event.selection else []
        if rows:
            open_engine(table.iloc[rows[0]]["unit"])
    else:
        st.success(f"Every {noun} is healthy. No action needed.")
with right:
    # 3. Time left at a glance: one bar per unit, coloured by condition.
    theme.section(f"3. {spec.rul_short} left", f"{insights.count(min(15, len(units)), spec)}, most urgent first")
    if "predicted_rul" in units:
        theme.chart(fleet_bars(units.head(15), spec), key="fleet_simple_bars")
        theme.note(f"Shorter bar = less {insights.life_word(spec)} left. Colours match the conditions above.")
st.page_link("views/admin_fleet.py", label="Fleet detail (admin): forecast ranges, health history and drivers",
             icon=":material/admin_panel_settings:")
