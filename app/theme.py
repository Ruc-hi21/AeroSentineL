"""Mission-control look for the dashboard: global CSS, Plotly template and HTML building blocks.

Everything here is presentation only. Numbers shown come from src/ via the pages.
"""

import html
import itertools

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

CYAN = "#00e5ff"
BLUE = "#3d8bff"
VIOLET = "#9b6bff"
PINK = "#ff5fb8"
INK = "#dbe8ff"
MUTED = "#7f95bd"
BAND_COLORS = {"NORMAL": "#19f5a0", "AT_RISK": "#ffd23f", "HIGH_RISK": "#ff8a1f", "FAILURE_LIKELY": "#ff2e4d"}
BAND_TEXT = {"NORMAL": "Normal", "AT_RISK": "At risk", "HIGH_RISK": "High risk", "FAILURE_LIKELY": "Failure likely"}
_ids = itertools.count()

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Exo+2:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&family=Rajdhani:wght@500;600;700&display=swap');

:root {
  --as-cyan: #00e5ff; --as-blue: #3d8bff; --as-violet: #9b6bff; --as-ink: #dbe8ff; --as-muted: #7f95bd;
  --as-glass: linear-gradient(145deg, rgba(14, 30, 64, .72), rgba(6, 14, 32, .62));
  --as-edge: rgba(0, 229, 255, .16); --as-edge-hi: rgba(0, 229, 255, .45);
  --as-ok: #19f5a0; --as-warn: #ffd23f; --as-high: #ff8a1f; --as-crit: #ff2e4d;
}

/* ---------- space backdrop: stars drift, grid breathes ---------- */
[data-testid="stApp"] { background: radial-gradient(1200px 700px at 70% -10%, #0f2a5c 0%, transparent 60%),
  radial-gradient(900px 600px at -10% 110%, rgba(0, 229, 255, .10) 0%, transparent 60%),
  linear-gradient(180deg, #040a18 0%, #030712 100%) !important; }
[data-testid="stApp"]::before {
  content: ""; position: fixed; inset: -50%; z-index: 0; pointer-events: none; opacity: .55;
  background-image:
    radial-gradient(1px 1px at 20px 30px, #fff, transparent), radial-gradient(1px 1px at 120px 80px, #9fd8ff, transparent),
    radial-gradient(1.5px 1.5px at 220px 160px, #fff, transparent), radial-gradient(1px 1px at 330px 40px, #c8b6ff, transparent),
    radial-gradient(1px 1px at 400px 220px, #fff, transparent), radial-gradient(1.5px 1.5px at 60px 260px, #9fd8ff, transparent);
  background-size: 460px 300px; animation: as-stars 160s linear infinite;
}
[data-testid="stApp"]::after {
  content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image: linear-gradient(rgba(0, 229, 255, .035) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 229, 255, .035) 1px, transparent 1px);
  background-size: 56px 56px; mask-image: radial-gradient(ellipse at 50% 30%, #000 20%, transparent 75%);
  animation: as-grid 9s ease-in-out infinite;
}
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: transparent !important; position: relative; z-index: 1; }
[data-testid="stHeader"] { background: rgba(4, 10, 24, .35) !important; backdrop-filter: blur(10px); border-bottom: 1px solid rgba(0, 229, 255, .08); }
[data-testid="stMainBlockContainer"] { padding-top: 2.6rem; padding-bottom: 4rem; max-width: 1500px; }
[data-testid="stAppDeployButton"] { display: none; }
[data-testid="stElementContainer"]:has(.as-css-anchor) { display: none; }

/* ---------- page-load cascade ---------- */
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"],
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"],
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
  animation: as-rise .7s cubic-bezier(.2, .8, .2, 1) both;
}
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > *:nth-child(2) { animation-delay: .05s; }
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > *:nth-child(3) { animation-delay: .1s; }
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > *:nth-child(4) { animation-delay: .15s; }
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > *:nth-child(5) { animation-delay: .2s; }
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > *:nth-child(6) { animation-delay: .25s; }
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > *:nth-child(7) { animation-delay: .3s; }
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] > *:nth-child(n+8) { animation-delay: .35s; }

/* ---------- typography ---------- */
h1, h2, h3, h4 { font-family: 'Orbitron', sans-serif !important; letter-spacing: .06em; }
h1 { background: linear-gradient(90deg, #fff 0%, #9fe9ff 45%, var(--as-cyan) 70%, var(--as-violet) 100%);
     -webkit-background-clip: text; background-clip: text; color: transparent !important; filter: drop-shadow(0 0 18px rgba(0, 229, 255, .25)); }
h2, h3 { color: #eaf4ff !important; }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { font-family: 'Exo 2', sans-serif; }
[data-testid="stCaptionContainer"] { color: var(--as-muted) !important; }
code { font-family: 'JetBrains Mono', monospace !important; color: #9fe9ff !important; background: rgba(0, 229, 255, .08) !important; border-radius: 6px; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background: linear-gradient(180deg, rgba(8, 18, 42, .96), rgba(3, 8, 20, .98)) !important;
  border-right: 1px solid rgba(0, 229, 255, .14); box-shadow: 8px 0 40px rgba(0, 0, 0, .35); }
[data-testid="stSidebarNavLink"] { border-radius: 10px; margin: 1px 6px; transition: all .25s; border: 1px solid transparent; }
[data-testid="stSidebarNavLink"]:hover { background: rgba(0, 229, 255, .08) !important; border-color: rgba(0, 229, 255, .25); transform: translateX(3px); }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: linear-gradient(90deg, rgba(0, 229, 255, .22), rgba(61, 139, 255, .08)) !important;
  border-color: rgba(0, 229, 255, .45); box-shadow: 0 0 22px rgba(0, 229, 255, .22), inset 3px 0 0 var(--as-cyan); }
[data-testid="stSidebarNavLink"] span:not([data-testid="stIconMaterial"]) { font-weight: 600; }
/* Material icons are font ligatures: if any rule changes their font, the icon name shows as text. */
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }
[data-testid="stNavSectionHeader"] { font-family: 'Orbitron', sans-serif !important; letter-spacing: .18em; font-size: .62rem !important; color: var(--as-cyan) !important; opacity: .75; }

/* ---------- metrics, buttons, inputs ---------- */
[data-testid="stMetric"] { background: var(--as-glass); border: 1px solid var(--as-edge); border-radius: 16px; padding: 14px 18px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, .3), inset 0 1px 0 rgba(255, 255, 255, .04); transition: all .3s; position: relative; overflow: hidden; }
[data-testid="stMetric"]::after { content: ""; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(0, 229, 255, .10), transparent); animation: as-sheen 6s ease-in-out infinite; }
[data-testid="stMetric"]:hover { border-color: var(--as-edge-hi); box-shadow: 0 0 26px rgba(0, 229, 255, .18); transform: translateY(-2px); }
[data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; color: #fff; text-shadow: 0 0 16px rgba(0, 229, 255, .35); }
[data-testid="stMetricLabel"] { color: var(--as-muted) !important; text-transform: uppercase; letter-spacing: .08em; }

[data-testid="stButton"] button, [data-testid="stDownloadButton"] button, [data-testid="stPageLink-NavLink"] {
  border-radius: 12px !important; border: 1px solid rgba(0, 229, 255, .35) !important; background: rgba(0, 229, 255, .06) !important;
  font-family: 'Orbitron', sans-serif !important; letter-spacing: .08em; transition: all .25s !important; }
[data-testid="stButton"] button p, [data-testid="stDownloadButton"] button p { font-family: 'Orbitron', sans-serif !important; font-size: .78rem; }
[data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover, [data-testid="stPageLink-NavLink"]:hover {
  background: rgba(0, 229, 255, .16) !important; box-shadow: 0 0 24px rgba(0, 229, 255, .35); transform: translateY(-1px); }
[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(90deg, #00b8d9, #3d6bff 60%, #7c4dff) !important; border: none !important;
  box-shadow: 0 0 26px rgba(0, 229, 255, .35); background-size: 200% 100% !important; animation: as-flow 5s ease infinite; }
[data-testid="stButton"] button[kind="primary"] p { color: #fff; font-weight: 700; }

[data-testid="stFileUploaderDropzone"] { background: rgba(0, 229, 255, .04) !important; border: 1.5px dashed rgba(0, 229, 255, .45) !important; border-radius: 18px !important;
  position: relative; overflow: hidden; transition: all .3s; }
[data-testid="stFileUploaderDropzone"]::before { content: ""; position: absolute; left: 0; right: 0; height: 40%; top: -40%; pointer-events: none;
  background: linear-gradient(180deg, transparent, rgba(0, 229, 255, .14), transparent); animation: as-scan 3.2s linear infinite; }
[data-testid="stFileUploaderDropzone"]:hover { box-shadow: 0 0 30px rgba(0, 229, 255, .25); border-color: var(--as-cyan) !important; }

[data-testid="stExpander"] details { background: var(--as-glass); border: 1px solid var(--as-edge) !important; border-radius: 14px !important; }
[data-testid="stTabs"] [data-baseweb="tab"] { font-family: 'Orbitron', sans-serif; font-size: .72rem; letter-spacing: .08em; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--as-cyan) !important; box-shadow: 0 0 12px var(--as-cyan); }
[data-testid="stAlert"] { border-radius: 14px; backdrop-filter: blur(6px); }
[data-testid="stDataFrame"], [data-testid="stPlotlyChart"] { border-radius: 16px; }
[data-testid="stPlotlyChart"] { background: var(--as-glass); border: 1px solid var(--as-edge); padding: 6px 4px 0; }
[data-testid="stCustomComponentV1"] { border-radius: 18px; }
[data-testid="stSelectbox"] > div > div, [data-testid="stMultiSelect"] > div > div { border-radius: 12px; }
hr { border-color: rgba(0, 229, 255, .15) !important; }

::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-track { background: #050b1a; }
::-webkit-scrollbar-thumb { background: linear-gradient(180deg, #0c4a6e, #3d2a7a); border-radius: 6px; }

/* ---------- building blocks (app/theme.py helpers) ---------- */
.as-head { position: relative; margin: 0 0 1.2rem; padding-bottom: .9rem; }
.as-kicker { font-family: 'JetBrains Mono', monospace; font-size: .72rem; letter-spacing: .28em; color: var(--as-cyan); text-transform: uppercase; display: flex; align-items: center; gap: .6rem; }
.as-kicker i { width: 8px; height: 8px; border-radius: 50%; background: var(--as-ok); box-shadow: 0 0 10px var(--as-ok); animation: as-blink 1.6s ease-in-out infinite; }
.as-title { font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: clamp(1.7rem, 3.2vw, 2.7rem); letter-spacing: .06em; margin: .35rem 0 .3rem; line-height: 1.1;
  background: linear-gradient(90deg, #fff 0%, #a6ecff 40%, var(--as-cyan) 65%, var(--as-violet) 100%); background-size: 200% 100%;
  -webkit-background-clip: text; background-clip: text; color: transparent; animation: as-flow 8s ease infinite; filter: drop-shadow(0 0 18px rgba(0, 229, 255, .3)); }
.as-sub { font-family: 'Exo 2', sans-serif; color: var(--as-muted); font-size: 1rem; max-width: 900px; }
.as-head::after { content: ""; position: absolute; left: 0; bottom: 0; height: 2px; width: 100%;
  background: linear-gradient(90deg, var(--as-cyan), rgba(155, 107, 255, .6) 35%, transparent 70%); box-shadow: 0 0 12px var(--as-cyan);
  transform-origin: left; animation: as-draw 1.2s cubic-bezier(.2, .8, .2, 1) both; }

.as-section { display: flex; align-items: center; gap: .8rem; margin: 1.6rem 0 .8rem; font-family: 'Orbitron', sans-serif; font-size: .85rem;
  letter-spacing: .2em; text-transform: uppercase; color: #eaf4ff; }
.as-section b { color: var(--as-cyan); text-shadow: 0 0 10px var(--as-cyan); font-weight: 700; }
.as-section::after { content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, rgba(0, 229, 255, .45), transparent); }

.as-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: .4rem 0 1rem; }
.as-kpi { --c: var(--as-cyan); position: relative; overflow: hidden; padding: 16px 18px 14px; border-radius: 18px; background: var(--as-glass);
  border: 1px solid color-mix(in srgb, var(--c) 30%, transparent); box-shadow: 0 12px 34px rgba(0, 0, 0, .35), inset 0 0 30px color-mix(in srgb, var(--c) 6%, transparent);
  animation: as-rise .8s cubic-bezier(.2, .8, .2, 1) both; transition: transform .3s, box-shadow .3s; }
.as-kpi:hover { transform: translateY(-3px); box-shadow: 0 0 30px color-mix(in srgb, var(--c) 30%, transparent); }
.as-kpi::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 2px; background: linear-gradient(90deg, transparent, var(--c), transparent); box-shadow: 0 0 12px var(--c); }
.as-kpi::after { content: ""; position: absolute; top: 0; left: -70%; width: 45%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255, 255, 255, .06), transparent); animation: as-sheen 7s ease-in-out infinite; }
.as-kpi-top { display: flex; align-items: center; justify-content: space-between; }
.as-kpi-label { font-family: 'Rajdhani', sans-serif; font-weight: 700; letter-spacing: .14em; font-size: .78rem; color: var(--as-muted); text-transform: uppercase; }
.as-kpi-icon { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; font-size: 1.05rem;
  background: color-mix(in srgb, var(--c) 14%, transparent); border: 1px solid color-mix(in srgb, var(--c) 40%, transparent); box-shadow: 0 0 14px color-mix(in srgb, var(--c) 30%, transparent); }
.as-kpi-value { font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 2rem; color: #fff; margin-top: .35rem; line-height: 1.1;
  text-shadow: 0 0 18px color-mix(in srgb, var(--c) 60%, transparent); }
.as-kpi-value small { font-size: .9rem; color: var(--as-muted); margin-left: .25rem; }
.as-kpi-sub { font-family: 'Exo 2', sans-serif; font-size: .78rem; color: var(--as-muted); margin-top: .25rem; }
/* Hex escape for the integer syntax: a literal less-than sign followed by a letter makes Streamlit's
   HTML sanitizer drop this whole stylesheet. */
@property --as-n { syntax: '\\3c integer>'; initial-value: 0; inherits: false; }
@property --as-p { syntax: '\\3c number>'; initial-value: 0; inherits: false; }
.as-count { counter-reset: n var(--as-n); }
.as-count::before { content: counter(n); }

.as-card { position: relative; padding: 18px 20px; border-radius: 18px; background: var(--as-glass); border: 1px solid var(--as-edge);
  box-shadow: 0 12px 34px rgba(0, 0, 0, .35); overflow: hidden; animation: as-rise .8s cubic-bezier(.2, .8, .2, 1) both; }
.as-card h4 { font-size: .8rem !important; letter-spacing: .2em; color: var(--as-cyan) !important; margin: 0 0 .6rem; text-transform: uppercase; }
.as-card p, .as-card li { font-family: 'Exo 2', sans-serif; color: var(--as-ink); }

.as-pill { --c: var(--as-ok); display: inline-flex; align-items: center; gap: .45rem; padding: .22rem .7rem; border-radius: 999px;
  font-family: 'Rajdhani', sans-serif; font-weight: 700; letter-spacing: .08em; font-size: .85rem; color: var(--c);
  background: color-mix(in srgb, var(--c) 12%, transparent); border: 1px solid color-mix(in srgb, var(--c) 55%, transparent); }
.as-pill i { width: 7px; height: 7px; border-radius: 50%; background: var(--c); box-shadow: 0 0 8px var(--c); }
.as-pill.pulse i { animation: as-blink 1s ease-in-out infinite; }

.as-gauges { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.as-gauge { position: relative; padding: 14px 10px 12px; border-radius: 18px; background: var(--as-glass); border: 1px solid var(--as-edge); text-align: center;
  animation: as-rise .8s cubic-bezier(.2, .8, .2, 1) both; }
.as-ring-wrap { position: relative; width: 120px; height: 120px; margin: 0 auto; }
.as-ring-wrap::after { content: ""; position: absolute; inset: -7px; border-radius: 50%; border: 1px dashed rgba(0, 229, 255, .28);
  animation: as-spin 22s linear infinite; }
.as-ring { position: absolute; inset: 0; border-radius: 50%; filter: drop-shadow(0 0 6px var(--c));
  background: conic-gradient(var(--c) calc(var(--as-p) * 1%), rgba(127, 149, 189, .16) 0);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 10px), #000 calc(100% - 9px));
  mask: radial-gradient(farthest-side, transparent calc(100% - 10px), #000 calc(100% - 9px)); }
.as-gauge .val { position: absolute; left: 0; right: 0; top: 56px; font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 1.45rem; color: #fff; }
.as-gauge .lab { font-family: 'Rajdhani', sans-serif; font-weight: 700; letter-spacing: .14em; font-size: .78rem; color: var(--as-muted); text-transform: uppercase; margin-top: .3rem; }
.as-gauge .note { font-family: 'Exo 2', sans-serif; font-size: .72rem; color: var(--as-muted); }

.as-list { list-style: none; padding: 0; margin: 0; }
.as-list li { display: flex; align-items: center; justify-content: space-between; gap: .6rem; padding: .45rem 0; border-bottom: 1px dashed rgba(0, 229, 255, .12); }
.as-list li:last-child { border-bottom: 0; }
.as-mono { font-family: 'JetBrains Mono', monospace; }
.as-bar { height: 6px; border-radius: 4px; background: rgba(127, 149, 189, .16); overflow: hidden; flex: 1; }
.as-bar b { display: block; height: 100%; border-radius: 4px; animation: as-grow 1.2s cubic-bezier(.2, .8, .2, 1) both; transform-origin: left; }

/* ---------- keyframes ---------- */
@keyframes as-stars { to { transform: translate3d(-460px, 300px, 0); } }
@keyframes as-grid { 0%, 100% { opacity: .65; } 50% { opacity: 1; } }
@keyframes as-rise { from { opacity: 0; transform: translateY(18px); filter: blur(4px); } to { opacity: 1; transform: none; filter: none; } }
@keyframes as-sheen { 0%, 60% { left: -70%; } 100% { left: 130%; } }
@keyframes as-flow { 0%, 100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
@keyframes as-scan { to { top: 140%; } }
@keyframes as-blink { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }
@keyframes as-draw { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes as-spin { to { transform: rotate(360deg); } }
@keyframes as-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
</style>
"""


def inject():
    # A style-only st.html goes to Streamlit's event container, which does not render it, so add an
    # anchor element; the CSS then hides the anchor's own (empty) container.
    st.html(GLOBAL_CSS + '<div class="as-css-anchor"></div>')


# ---------- Plotly ----------

def _register_plotly_template():
    axis = dict(gridcolor="rgba(0,229,255,0.07)", zerolinecolor="rgba(0,229,255,0.12)", linecolor="rgba(0,229,255,0.2)",
                tickfont=dict(color=MUTED, family="JetBrains Mono, monospace", size=11),
                title=dict(font=dict(color=MUTED, family="Rajdhani, sans-serif", size=13)))
    template = go.layout.Template(layout=dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(4,12,30,0.35)",
        font=dict(family="Exo 2, sans-serif", color=INK, size=13),
        colorway=[CYAN, VIOLET, "#19f5a0", "#ffd23f", PINK, BLUE, "#ff8a1f"],
        xaxis=axis, yaxis=axis,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED)),
        hoverlabel=dict(bgcolor="rgba(4,10,24,0.95)", bordercolor=CYAN, font=dict(family="JetBrains Mono, monospace", color=INK)),
        margin=dict(t=30, b=10, l=10, r=10),
        polar=dict(bgcolor="rgba(0,0,0,0)", angularaxis=dict(gridcolor="rgba(0,229,255,0.1)"), radialaxis=dict(gridcolor="rgba(0,229,255,0.1)")),
        scene=dict(xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(0,229,255,0.12)", color=MUTED),
                   yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(0,229,255,0.12)", color=MUTED),
                   zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(0,229,255,0.12)", color=MUTED)),
    ))
    pio.templates["aerosentinel"] = template
    pio.templates.default = "aerosentinel"


_register_plotly_template()


def chart(fig, key=None, height=None):
    """Plotly chart in the AeroSentinel template (Streamlit's own theme would override it)."""
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False})


# ---------- HTML building blocks ----------

def esc(text):
    return html.escape(str(text))


def page_header(kicker, title, subtitle=""):
    st.html(f'<div class="as-head"><div class="as-kicker"><i></i>{esc(kicker)}</div>'
            f'<div class="as-title">{esc(title)}</div><div class="as-sub">{subtitle}</div></div>')


def section(title, accent=""):
    st.html(f'<div class="as-section">{esc(title)}{f" <b>{esc(accent)}</b>" if accent else ""}</div>')


def _count(value, decimals=0, duration=1.8):
    """Number that counts up from 0 (CSS-only: animates an integer custom property)."""
    n = next(_ids)
    whole = int(abs(value))
    frac = f"{abs(value):.{decimals}f}".split(".")[1] if decimals else ""
    sign = "-" if value < 0 else ""
    return (f'<style>@keyframes as-c{n}{{from{{--as-n:0}}to{{--as-n:{whole}}}}}</style>'
            f'{sign}<span class="as-count" style="animation:as-c{n} {duration}s cubic-bezier(.2,.8,.2,1) both"></span>'
            f'{"." + frac if decimals else ""}')


def kpi(label, value, icon="", sub="", color=CYAN, decimals=0, suffix="", text=None, compact=False):
    """One KPI card. Pass `text` to show a fixed string instead of a counting number."""
    shown = esc(text) if text is not None else _count(value, decimals)
    size = ' style="font-size:1.2rem"' if compact else ""
    return (f'<div class="as-kpi" style="--c:{color}"><div class="as-kpi-top"><div class="as-kpi-label">{esc(label)}</div>'
            f'<div class="as-kpi-icon">{icon}</div></div><div class="as-kpi-value"{size}>{shown}<small>{esc(suffix)}</small></div>'
            f'<div class="as-kpi-sub">{sub}</div></div>')


def kpi_row(cards):
    st.html(f'<div class="as-kpis">{"".join(cards)}</div>')


def gauge(label, fraction, shown, color=CYAN, note=""):
    """Animated ring gauge (CSS conic gradient; st.html strips inline SVG). fraction in 0..1 fills the ring."""
    n = next(_ids)
    pct = 100 * max(0.0, min(1.0, fraction))
    return (f'<style>@keyframes as-g{n}{{from{{--as-p:0}}to{{--as-p:{pct:.1f}}}}}</style>'
            f'<div class="as-gauge"><div class="as-ring-wrap"><div class="as-ring" style="--c:{color};--as-p:{pct:.1f};'
            f'animation:as-g{n} 1.8s cubic-bezier(.2,.8,.2,1) both"></div></div>'
            f'<div class="val" style="text-shadow:0 0 14px {color}">{esc(shown)}</div>'
            f'<div class="lab">{esc(label)}</div><div class="note">{note}</div></div>')


def gauge_row(gauges):
    st.html(f'<div class="as-gauges">{"".join(gauges)}</div>')


def band_pill(band, extra=""):
    color = BAND_COLORS.get(band, CYAN)
    pulse = " pulse" if band in ("HIGH_RISK", "FAILURE_LIKELY") else ""
    return f'<span class="as-pill{pulse}" style="--c:{color}"><i></i>{esc(BAND_TEXT.get(band, band))}{esc(extra)}</span>'


def card(title, body_html):
    st.html(f'<div class="as-card"><h4>{esc(title)}</h4>{body_html}</div>')
