"""Home: the landing page, the same whether or not a file is loaded. An animated title band, the live 3D showcase
(switch components inside the view), and the five component models by name. Everything about the loaded data is on
the other pages."""

import streamlit as st

from app import theme
from app.engine3d import engine_twin
from app.theme import esc

# Each card: component key and its name.
CARDS = [
    ("turbofan", "Turbofan engine"),
    ("battery", "Li-ion battery cell"),
    ("bearing", "Engine gearbox"),
    ("hydraulic", "Hydraulic system"),
    ("power", "Power electronics"),
]
# Sensor channel codes drifting past in the title band: decoration drawn from the real channels, never values.
TICKER = ["T24", "T30", "T50", "P30", "Ps30", "Nf", "Nc", "phi", "BPR", "W31", "W32", "Cap", "SoH", "RMS", "Kurt",
          "PS1", "FS1", "TS1", "Vce", "Ic", "Rce"]
WORD = "AEROSENTINEL"

ticker = "".join(f"<span>{esc(c)}</span>" for c in TICKER) * 2  # two copies, so the loop is seamless
letters = "".join(f'<i style="--i:{n}">{esc(ch)}</i>' for n, ch in enumerate(WORD))
st.html(f"""<div class="as-home">
<div class="grid"></div><div class="glow"></div><div class="scan"></div>
<div class="body">
  <div class="mark"><img src="app/static/brand/logo_mark.svg" alt=""><span>Predictive maintenance console</span></div>
  <h1 aria-label="AeroSentinel">{letters}</h1>
  <div class="line"><b>Five components.</b> <b>One console.</b> <b class="hl">Failures seen before they happen.</b></div>
</div>
<div class="ticker" aria-hidden="true"><div class="track">{ticker}</div></div>
</div>""")

# What the console is, in a few lines, before the showcase.
PILLARS = [
    ("Recognise", "Five components identified from the data itself, not from the column names."),
    ("Forecast", "Remaining useful life with an 80% range, and one of four risk bands for every unit."),
    ("Explain", "The sensors behind each forecast, their drift, and a 3D model of every part."),
]
st.html('<div class="as-intro"><div class="lead"><div class="k">What it does</div>'
        '<h2>Predictive maintenance for the parts that keep an aircraft flying</h2></div>'
        '<div class="text"><p>AeroSentinel reads raw sensor logs from turbofan engines, Li-ion battery cells, engine gearboxes, '
        'hydraulic systems and power electronics. It corrects every reading for the operating condition it was taken in, '
        'forecasts how long each unit has left, and shows the evidence behind every call.</p>'
        '<div class="pillars">' + "".join(f'<div><b>{esc(t)}</b><span>{esc(d)}</span></div>' for t, d in PILLARS)
        + '</div></div></div>')

# The live 3D showcase: every component, switchable inside the view.
engine_twin(mode="hero", height=560, key="hero_engine", component="turbofan")

theme.section("Five component models", kicker="Coverage")
st.html('<div class="as-cards as-home-cards">' + "".join(
    f'<div class="as-card"><div class="img"><img src="app/static/brand/thumb_{key}.jpg" alt="3D model of the {esc(name)}"></div>'
    f'<div class="body"><b>{esc(name)}</b></div></div>' for key, name in CARDS) + "</div>")
