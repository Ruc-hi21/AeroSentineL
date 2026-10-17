"""Fleet overview: the landing page, the same whether or not a file is loaded. What the console does, how a file
flows through it, and the five component models. The loaded fleet itself is on Fleet details."""

import streamlit as st

from app import theme
from app.components import load_benchmark
from app.engine3d import engine_twin
from app.theme import esc
from src.models.artifacts import model_status


status = model_status()

# ---------------------------------------------------------------- landing page (nothing loaded yet)
# Each card: component key, model profile, name, what the 3D model shows, the data behind the model.
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
    b1, _ = st.columns([1, 1.25])
    with b1:
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

# The five components: what the model sees and how well it does.
theme.section("Five component models", "the recognition model picks the component on its own")
# One responsive grid (5, 3, 2 or 1 across).
st.html('<div class="as-cards">' + "".join(
    f'<div class="as-card">'
    f'<div class="img"><img src="app/static/brand/thumb_{key}.jpg" alt="3D model of the {esc(name)}"></div>'
    f'<div class="body"><b>{esc(name)}</b><p>{esc(shows)}</p><span class="data">{esc(data)}</span>'
    f'<span class="metric">{esc(card_metric(bench, profile))}</span></div></div>'
    for key, profile, name, shows, data in CARDS) + "</div>")
