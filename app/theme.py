"""AeroSentinel design system: tokens, global CSS, Plotly template and HTML primitives.

Visual language: an engineering console on a near-black base. Carbon-inspired Gray-100 dark theme
(borrowed conventions, not the official Carbon package), IBM Plex type, 2px radii, 1px hairlines.
Brand colour comes from the AeroSentinel logo (cobalt to azure to cyan) and is used sparingly:
the top hairline, the active navigation item, primary buttons, section markers and the primary
data series. Status colours are reserved for condition and always ship with a text label.

Motion has a job: content rises in once when a page opens, numbers count to their value (and
from the previous value when the unit changes), the top hairline sweeps while the app computes.
Everything respects prefers-reduced-motion.

Presentation only. Every number shown comes from src/ via the pages.
"""

import html
import itertools
import re

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------- tokens (mirror .streamlit/config.toml)
TOKENS = {
    "bg": "#0e1013",          # app background
    "surface": "#16191d",     # panels, inputs, table headers
    "surface_2": "#1d2126",   # hover / selected rows
    "line": "#262b31",        # hairline separators
    "line_strong": "#353b43", # control borders, axes
    "text_1": "#e6e8eb",      # primary text        15.4:1 on bg
    "text_2": "#a6adb6",      # secondary text       8.3:1
    "text_3": "#7f8790",      # labels, captions     5.2:1
    "accent": "#3fa2ff",      # interaction + primary data series (logo azure, 7.0:1 on bg)
    "accent_2": "#3ddbd9",    # secondary data series (Carbon teal 30)
    "brand": "#1683f2",       # logo blue
    "brand_deep": "#0a4fb8",  # logo cobalt
    "brand_cyan": "#5fd4f8",  # logo highlight
}
MONO = "'IBM Plex Mono', ui-monospace, Consolas, monospace"
SANS = "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif"

# Engine condition states. Order = severity. Colour always ships with the text label.
STATES = {
    "CRITICAL": {"label": "Critical", "color": "#fa4d56"},
    "WARNING": {"label": "Warning", "color": "#ff832b"},
    "DEGRADING": {"label": "Degrading", "color": "#f1c21b"},
    "HEALTHY": {"label": "Healthy", "color": "#42be65"},
    "INSUFFICIENT": {"label": "Insufficient data", "color": "#8d8d8d"},
}
# Model risk bands (backend vocabulary) share the same ramp.
BAND_COLORS = {"NORMAL": "#42be65", "AT_RISK": "#f1c21b", "HIGH_RISK": "#ff832b", "FAILURE_LIKELY": "#fa4d56"}
BAND_TEXT = {"NORMAL": "Normal", "AT_RISK": "At risk", "HIGH_RISK": "High risk", "FAILURE_LIKELY": "Failure likely"}

_ids = itertools.count()

GLOBAL_CSS = """
<style>
:root {
  --bg: #0e1013; --surface: #16191d; --surface-2: #1d2126; --line: #262b31; --line-strong: #353b43;
  --text-0: #f4f6f8; --text-1: #e6e8eb; --text-2: #a6adb6; --text-3: #7f8790; --accent: #3fa2ff;
  --brand: #1683f2; --brand-deep: #0a4fb8; --brand-cyan: #5fd4f8;
  --brand-grad: linear-gradient(90deg, #0a4fb8 0%, #1683f2 45%, #5fd4f8 100%);
  --s-crit: #fa4d56; --s-warn: #ff832b; --s-degr: #f1c21b; --s-ok: #42be65; --s-none: #8d8d8d;
  --mono: 'IBM Plex Mono', ui-monospace, Consolas, monospace;
  --ease: cubic-bezier(.2, 0, .38, .9); --ease-out: cubic-bezier(.16, 1, .3, 1);
  --t-fast: 110ms; --t-std: 240ms;
}
::selection { background: rgba(63, 162, 255, .35); }

/* ---------- motion ---------- */
@keyframes as-rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes as-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes as-sweep { from { left: -30%; } to { left: 100%; } }
@keyframes as-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
@keyframes as-spin-in { from { opacity: 0; transform: rotate(-40deg) scale(.7); } to { opacity: 1; transform: none; } }
.as-reveal { animation: as-rise .55s var(--ease-out) both; animation-delay: var(--as-d, 0ms); }

/* ---------- frame ---------- */
[data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--bg); }
[data-testid="stHeader"] { background: var(--bg); border-bottom: 1px solid var(--line); }
/* brand hairline across the top; a highlight sweeps along it while the app is computing */
[data-testid="stHeader"]::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px; background: var(--brand-grad); z-index: 1000; }
[data-testid="stHeader"]:has([data-testid="stStatusWidget"])::after { content: ""; position: absolute; top: 0; height: 2px; width: 30%;
  background: linear-gradient(90deg, transparent, #d4f1ff, transparent); animation: as-sweep 1.1s var(--ease) infinite; z-index: 1001; }
[data-testid="stAppDeployButton"] { display: none; }
[data-testid="stMainBlockContainer"] { max-width: 1480px; padding: 4.2rem 2.2rem 4rem; }
[data-testid="stElementContainer"]:has(.as-css-anchor) { display: none; }
p, li, td, th { font-variant-numeric: tabular-nums; }
code { font-family: var(--mono) !important; color: var(--text-1) !important; background: var(--surface) !important;
  border: 1px solid var(--line); border-radius: 2px; padding: 0 .3em; }
[data-testid="stCaptionContainer"] { color: var(--text-3); }
hr { border-color: var(--line) !important; margin: 1.2rem 0 !important; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--line-strong); border: 2px solid var(--bg); border-radius: 2px; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { border-right: 1px solid var(--line);
  background: radial-gradient(130% 34% at 0% 0%, rgba(22, 131, 242, .11), transparent 70%), #121418; }
[data-testid="stSidebarNavLink"] { border-radius: 2px; margin: 0 4px; padding-top: 4px; padding-bottom: 4px;
  transition: background var(--t-fast) var(--ease); }
[data-testid="stSidebarNavLink"]:hover { background: var(--surface-2); }
[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] { transition: transform var(--t-std) var(--ease-out), color var(--t-std) var(--ease); }
[data-testid="stSidebarNavLink"]:hover [data-testid="stIconMaterial"] { transform: translateX(2px); color: var(--text-1); }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: linear-gradient(90deg, rgba(22, 131, 242, .2), rgba(22, 131, 242, .02));
  box-shadow: inset 2px 0 0 var(--accent); }
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"] { color: var(--accent) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] span:not([data-testid="stIconMaterial"]) { color: var(--text-1); font-weight: 500; }
[data-testid="stNavSectionHeader"] { font-size: 11px !important; letter-spacing: .06em; text-transform: uppercase; color: var(--text-3) !important; }
/* Material icons are font ligatures: any font override on them prints the icon name as text. */
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }

/* ---------- controls ---------- */
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button, [data-testid="stPageLink-NavLink"] {
  border-radius: 2px; border: 1px solid var(--line-strong); background: transparent; min-height: 34px;
  transition: background var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease); }
[data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover, [data-testid="stPageLink-NavLink"]:hover {
  background: var(--surface-2); border-color: rgba(63, 162, 255, .55); }
[data-testid="stButton"] button:active, [data-testid="stDownloadButton"] button:active { transform: translateY(1px) scale(.99); }
[data-testid="stButton"] button[kind="primary"] { background: linear-gradient(90deg, #3fa2ff, #5fb8ff); border-color: #3fa2ff;
  box-shadow: 0 8px 20px -12px rgba(63, 162, 255, .9); transition: transform var(--t-fast) var(--ease), box-shadow var(--t-std) var(--ease); }
[data-testid="stButton"] button[kind="primary"] p { color: #06121f; font-weight: 600; }
[data-testid="stButton"] button[kind="primary"]:hover { background: linear-gradient(90deg, #5fb3ff, #7cc6ff); border-color: #5fb3ff;
  transform: translateY(-1px); box-shadow: 0 12px 24px -12px rgba(63, 162, 255, 1); }
button:focus-visible, a:focus-visible, [role="tab"]:focus-visible { outline: 2px solid var(--accent) !important; outline-offset: 1px; }
[data-testid="stPageLink-NavLink"] { padding: 4px 12px; }
[data-testid="stFileUploaderDropzone"] { background: var(--surface); border: 1px dashed var(--line-strong); border-radius: 2px; }
[data-testid="stFileUploaderDropzone"] { transition: border-color var(--t-std) var(--ease), background var(--t-std) var(--ease); }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent); background: rgba(63, 162, 255, .05); }
[data-testid="stExpander"] details { border: 1px solid var(--line); border-radius: 2px; background: transparent; }
[data-testid="stExpander"] summary:hover { background: var(--surface); }
[data-testid="stTabs"] [data-baseweb="tab-list"] { border-bottom: 1px solid var(--line); gap: 20px; }
[data-testid="stTabs"] [data-baseweb="tab"] { padding: 0 0 10px; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--brand-grad); height: 2px; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { display: none; }
[data-testid="stAlertContainer"] { border-radius: 2px; }
/* multiselect chips: neutral, the accent is reserved for focus and the primary data series */
[data-testid="stMultiSelectTagsContainer"] > span > span { background: var(--surface-2) !important; color: var(--text-1) !important;
  border: 1px solid var(--line-strong); border-radius: 2px !important; }
[data-testid="stMultiSelectTagsContainer"] > span > span svg { fill: var(--text-2) !important; color: var(--text-2) !important; }
[data-testid="stMetric"] { padding: 0; }
[data-testid="stMetricValue"] { font-family: var(--mono); }
[data-testid="stDataFrame"] { border-radius: 2px; }
[data-testid="stCustomComponentV1"] { display: block; }

/* ---------- page head ---------- */
.as-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; flex-wrap: wrap;
  padding-bottom: 14px; margin-bottom: 8px; border-bottom: 1px solid var(--line); position: relative; }
.as-head::after { content: ""; position: absolute; left: 0; bottom: -1px; height: 2px; width: 96px; background: var(--brand-grad);
  transform-origin: left; animation: as-grow .8s var(--ease-out) .15s both; }
.as-head .k { font-family: var(--mono); font-size: 11px; letter-spacing: .16em; text-transform: uppercase; color: var(--brand-cyan);
  margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }
.as-head .k::before { content: ""; width: 18px; height: 1px; background: var(--brand-cyan); }
.as-head h1 { font-size: 28px; font-weight: 600; margin: 0; padding: 0; line-height: 1.18; letter-spacing: -.015em; color: var(--text-0); }
.as-head .ctx { font-size: 14px; color: var(--text-2); margin-top: 6px; max-width: 78ch; line-height: 1.5; }
.as-head .meta { font-family: var(--mono); font-size: 12px; color: var(--text-3); text-align: right; line-height: 1.6; }
.as-head .meta b { color: var(--text-2); font-weight: 500; }

/* ---------- section titles: mono kicker, bright title, a rule that fades to the note ---------- */
.as-sec { display: flex; align-items: flex-end; gap: 16px; margin: 34px 0 12px; }
.as-sec .h { flex: none; min-width: 0; }
.as-sec .k { display: block; font-family: var(--mono); font-size: 11px; font-weight: 500; letter-spacing: .16em; text-transform: uppercase;
  color: var(--brand-cyan); margin-bottom: 4px; }
.as-sec h2 { font-size: 19px; font-weight: 600; margin: 0; padding: 0; line-height: 1.25; letter-spacing: -.01em; color: var(--text-0);
  display: flex; align-items: center; gap: 10px; }
.as-sec.nk h2::before { content: ""; width: 3px; height: 16px; border-radius: 1px; background: linear-gradient(180deg, #5fd4f8, #1683f2); flex: none; }
.as-sec .r { flex: 1; height: 1px; margin-bottom: 8px; background: linear-gradient(90deg, var(--line-strong), rgba(53, 59, 67, 0));
  transform-origin: left; animation: as-grow .9s var(--ease-out) .1s both; }
.as-sec .n { flex: none; max-width: 52ch; font-size: 12px; color: var(--text-3); text-align: right; margin-bottom: 2px; line-height: 1.4; }

/* ---------- readouts: framed tiles, status line on top, uppercase label, optional meter ---------- */
.as-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(176px, 1fr)); gap: 12px; margin: 6px 0 6px; }
.as-stat { --c: var(--line-strong); position: relative; overflow: hidden; padding: 14px 16px 13px; border: 1px solid var(--line); border-radius: 4px;
  background: linear-gradient(180deg, #181c21 0%, #131619 100%);
  transition: border-color var(--t-std) var(--ease), transform var(--t-std) var(--ease-out), box-shadow var(--t-std) var(--ease); }
.as-stat::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px; background: var(--c); opacity: .9; }
.as-stat::after { content: ""; position: absolute; inset: 0; pointer-events: none; opacity: 0;
  background: radial-gradient(120% 80% at 0% 0%, rgba(63, 162, 255, .10), transparent 60%); transition: opacity var(--t-std) var(--ease); }
.as-stat:hover { border-color: rgba(63, 162, 255, .45); transform: translateY(-2px); box-shadow: 0 14px 28px -20px rgba(22, 131, 242, .8); }
.as-stat:hover::after { opacity: 1; }
.as-stat .l { font-family: var(--mono); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--text-3); }
.as-stat .v { font-family: var(--mono); font-size: 26px; font-weight: 500; color: var(--text-0); line-height: 1.2; margin-top: 8px;
  font-variant-numeric: tabular-nums; white-space: nowrap; }
.as-stat .v small { font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; color: var(--text-3); font-weight: 400; margin-left: 5px; }
.as-stat .v.t { font-family: 'IBM Plex Sans', sans-serif; font-size: 21px; font-weight: 600; line-height: 1.3; letter-spacing: -.01em; white-space: normal; }
.as-stat .v.c { color: var(--c); display: flex; align-items: center; gap: 9px; }
.as-stat .v.c::before { content: ""; width: 8px; height: 8px; border-radius: 1px; background: var(--c); flex: none; box-shadow: 0 0 10px -1px var(--c); }
.as-stat .f { font-size: 12px; color: var(--text-2); margin-top: 6px; line-height: 1.4; }
.as-stat .m { height: 3px; margin-top: 10px; background: var(--line); border-radius: 2px; overflow: hidden; }
.as-stat .m i { display: block; height: 100%; border-radius: 2px; background: var(--mc, var(--accent)); transform-origin: left;
  animation: as-grow 1s var(--ease-out) .25s both; }

.as-stat.has-tip { cursor: help; }
.as-stat.has-tip .l::after { content: "i"; display: inline-block; width: 13px; height: 13px; margin-left: 7px; border: 1px solid var(--line-strong);
  border-radius: 50%; font-size: 9px; line-height: 12px; text-align: center; letter-spacing: 0; text-transform: none; color: var(--text-3);
  transition: color var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease); }
.as-stat.has-tip:hover .l::after, .as-stat.has-tip:focus .l::after { color: var(--accent); border-color: var(--accent); }
.as-stat .tip { position: absolute; left: 0; right: 0; bottom: 0; padding: 10px 16px 12px; font-size: 12px; line-height: 1.45; color: var(--text-1);
  background: rgba(13, 16, 20, .97); border-top: 1px solid var(--accent); transform: translateY(101%); z-index: 2;
  transition: transform .32s var(--ease-out); }
.as-stat .tip b { display: block; font-family: var(--mono); font-size: 10px; font-weight: 500; letter-spacing: .12em; text-transform: uppercase;
  color: var(--brand-cyan); margin-bottom: 3px; }
.as-stat.has-tip:hover .tip, .as-stat.has-tip:focus .tip { transform: none; }
.as-stat:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }

/* ---------- friendlier controls: pills, segmented switches, sliders, popovers ---------- */
[data-testid="stPills"] button, [data-testid="stSegmentedControl"] button, [data-testid="stBaseButton-pills"], [data-testid="stBaseButton-segmented_control"] {
  border-radius: 2px !important; border: 1px solid var(--line-strong) !important; background: transparent !important; min-height: 30px;
  transition: background var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease), transform var(--t-fast) var(--ease); }
[data-testid="stBaseButton-pills"]:hover, [data-testid="stBaseButton-segmented_control"]:hover { border-color: rgba(63, 162, 255, .6) !important;
  background: rgba(63, 162, 255, .08) !important; transform: translateY(-1px); }
[data-testid="stBaseButton-pillsActive"], [data-testid="stBaseButton-segmented_controlActive"] { border-radius: 2px !important;
  border: 1px solid var(--accent) !important; background: rgba(63, 162, 255, .16) !important; box-shadow: inset 0 -2px 0 var(--accent); }
[data-testid="stBaseButton-pillsActive"] p, [data-testid="stBaseButton-segmented_controlActive"] p { color: var(--text-0) !important; font-weight: 500; }
[data-testid="stSlider"] [role="slider"] { box-shadow: 0 0 0 4px rgba(63, 162, 255, .18); transition: box-shadow var(--t-std) var(--ease); }
[data-testid="stSlider"] [role="slider"]:hover { box-shadow: 0 0 0 7px rgba(63, 162, 255, .26); }
[data-testid="stPopover"] button { border-radius: 2px; border: 1px solid var(--line-strong); background: transparent; }
[data-testid="stPopover"] button:hover { border-color: rgba(63, 162, 255, .6); background: rgba(63, 162, 255, .08); }
.as-guide { display: grid; grid-template-columns: max-content 1fr; gap: 8px 14px; font-size: 13px; line-height: 1.45; max-width: 460px; }
.as-guide dt { font-family: var(--mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--brand-cyan); padding-top: 2px; }
.as-guide dd { margin: 0; color: var(--text-1); }

/* ---------- verdict panel: the state, the number that matters, and where it sits on the risk bands ---------- */
@keyframes as-pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--c) 60%, transparent); } 100% { box-shadow: 0 0 0 12px transparent; } }
@keyframes as-slide { from { left: 100%; opacity: 0; } }
.as-verdict { --c: var(--s-none); display: grid; grid-template-columns: minmax(240px, 1.15fr) minmax(170px, .6fr) minmax(320px, 1.7fr);
  gap: 0; margin: 14px 0 12px; border: 1px solid var(--line); border-left: 3px solid var(--c); border-radius: 4px; overflow: hidden;
  background: linear-gradient(115deg, color-mix(in srgb, var(--c) 11%, #14171b) 0%, #14171b 46%, #121418 100%); }
.as-verdict > div { padding: 20px 24px; }
.as-verdict > div + div { border-left: 1px solid var(--line); }
.as-verdict .k { font-family: var(--mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--text-3); }
.as-verdict .s { display: flex; align-items: center; gap: 12px; margin-top: 10px; font-size: 30px; font-weight: 600; letter-spacing: -.015em;
  line-height: 1.1; color: var(--c); }
.as-verdict .s i { width: 12px; height: 12px; border-radius: 50%; background: var(--c); flex: none; }
.as-verdict.live .s i { animation: as-pulse 1.8s var(--ease) infinite; }
.as-verdict p { margin: 12px 0 0; font-size: 13px; line-height: 1.5; color: var(--text-2); max-width: 44ch; }
.as-verdict .num { font-family: var(--mono); font-size: 46px; font-weight: 500; line-height: 1; margin-top: 10px; color: var(--text-0);
  font-variant-numeric: tabular-nums; white-space: nowrap; }
.as-verdict .u { font-size: 13px; color: var(--text-2); margin-top: 6px; }
.as-verdict .rg { font-size: 12px; color: var(--text-3); margin-top: 8px; line-height: 1.45; }
.as-verdict .rg b { font-family: var(--mono); font-weight: 500; color: var(--text-1); }
.as-gauge { position: relative; height: 12px; margin: 44px 4px 30px; }
.as-gauge .z { position: absolute; top: 0; height: 100%; background: var(--zc); opacity: .26; border-radius: 1px; }
.as-gauge .z.on { opacity: .95; box-shadow: 0 0 16px -3px var(--zc); }
.as-gauge .rng { position: absolute; top: -6px; height: 24px; border: 1px solid rgba(244, 246, 248, .8); border-radius: 2px;
  background: rgba(244, 246, 248, .08); transform-origin: left; animation: as-grow .8s var(--ease-out) .45s both; }
.as-gauge .mk { position: absolute; top: -11px; width: 2px; height: 34px; margin-left: -1px; background: #fff; box-shadow: 0 0 10px rgba(255, 255, 255, .7);
  animation: as-slide 1.1s var(--ease-out) both; }
.as-gauge .mk b { position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); padding-bottom: 5px; font-family: var(--mono);
  font-size: 12px; font-weight: 500; color: var(--text-0); white-space: nowrap; }
.as-gauge .mk.a b { left: 0; transform: none; } .as-gauge .mk.b b { left: auto; right: 0; transform: none; }
.as-gauge .tk { position: absolute; top: 20px; transform: translateX(-50%); font-family: var(--mono); font-size: 11px; color: var(--text-3); }
.as-gauge .tk::before { content: ""; position: absolute; left: 50%; top: -8px; width: 1px; height: 5px; background: var(--line-strong); }
.as-zones { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 0 4px; }
.as-zones span { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-3); white-space: nowrap; }
.as-zones span i { width: 8px; height: 8px; border-radius: 1px; background: var(--zc); opacity: .5; }
.as-zones span.on { color: var(--text-1); font-weight: 500; } .as-zones span.on i { opacity: 1; }

/* ---------- leading indicators: one row per sensor with its drift trace ---------- */
.as-ind { border: 1px solid var(--line); border-radius: 4px; overflow: hidden; background: linear-gradient(180deg, #171a1f, #131619); }
.as-ind .row { --c: var(--text-3); display: grid; grid-template-columns: 62px minmax(120px, 1fr) 132px 78px 96px; align-items: center; gap: 14px;
  padding: 11px 16px; border-top: 1px solid var(--line); transition: background var(--t-fast) var(--ease); }
.as-ind .row:first-child { border-top: 0; }
.as-ind .row:hover { background: rgba(63, 162, 255, .06); }
.as-ind .code { font-family: var(--mono); font-size: 14px; font-weight: 500; color: var(--text-0); }
.as-ind .nm { font-size: 13px; color: var(--text-1); line-height: 1.3; }
.as-ind .nm small { display: block; font-size: 11px; color: var(--text-3); letter-spacing: .04em; text-transform: uppercase; margin-top: 2px; }
.as-ind .sp { --c: inherit; position: relative; width: 132px; height: 30px; animation: as-wipe 1.1s var(--ease-out) .25s both; }
.as-ind .sp span { position: absolute; display: block; }
.as-ind .sp .ar { inset: 0; background: linear-gradient(180deg, color-mix(in srgb, var(--c) 34%, transparent), transparent); }
.as-ind .sp .ln { inset: 0; background: var(--c); }
.as-ind .sp .th { left: 0; right: 0; height: 0; border-top: 1px dashed var(--s-warn); opacity: .65; }
.as-ind .sp .dot { right: -3px; width: 7px; height: 7px; margin-top: -3.5px; border-radius: 50%; background: var(--c); box-shadow: 0 0 0 2px #14171b; }
@keyframes as-wipe { from { clip-path: inset(-6px 100% -6px 0); } to { clip-path: inset(-6px -8px -6px 0); } }
.as-ind .val { font-family: var(--mono); font-size: 15px; color: var(--text-0); text-align: right; font-variant-numeric: tabular-nums; }
.as-ind .val small { display: block; font-size: 11px; color: var(--text-3); }
.as-chip { --c: var(--text-3); display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 2px; font-size: 12px;
  font-weight: 500; color: var(--c); border: 1px solid color-mix(in srgb, var(--c) 45%, transparent);
  background: color-mix(in srgb, var(--c) 10%, transparent); white-space: nowrap; }
.as-chip::before { content: ""; width: 6px; height: 6px; border-radius: 1px; background: var(--c); }

/* ---------- chart panels: every plot sits in its own frame ---------- */
[data-testid="stPlotlyChart"] { border-radius: 4px; box-shadow: 0 0 0 1px var(--line); background: linear-gradient(180deg, #16191d 0%, #121418 100%);
  transition: box-shadow var(--t-std) var(--ease); }
[data-testid="stPlotlyChart"]:hover { box-shadow: 0 0 0 1px rgba(63, 162, 255, .38), 0 18px 34px -26px rgba(22, 131, 242, .9); }

/* ---------- status ---------- */
.as-state { --c: var(--s-none); display: inline-flex; align-items: center; gap: 8px; font-weight: 500; color: var(--c); white-space: nowrap; }
.as-state i { width: 8px; height: 8px; background: var(--c); border-radius: 1px; flex: none; }
.as-flag { display: inline-block; font-size: 12px; color: var(--text-2); border: 1px solid var(--line-strong); border-radius: 2px;
  padding: 1px 6px; margin: 2px 6px 2px 0; white-space: nowrap; }

/* condition distribution: one 100% bar instead of five cards */
.as-dist { margin: 8px 0 2px; }
.as-dist .bar { display: flex; height: 10px; gap: 2px; }
.as-dist .bar span { display: block; height: 100%; transform-origin: left; animation: as-grow .9s var(--ease-out) both; }
.as-dist .bar span:nth-child(2) { animation-delay: .06s; } .as-dist .bar span:nth-child(3) { animation-delay: .12s; }
.as-dist .bar span:nth-child(4) { animation-delay: .18s; } .as-dist .bar span:nth-child(5) { animation-delay: .24s; }
.as-dist .keys { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 16px; margin-top: 10px; }
.as-dist .k { border-top: 2px solid var(--c); padding-top: 6px; }
.as-dist .k .n { font-family: var(--mono); font-size: 22px; color: var(--text-1); line-height: 1.2; }
.as-dist .k .t { font-size: 12px; color: var(--text-2); }

/* ---------- lists ---------- */
.as-kv { display: grid; grid-template-columns: max-content 1fr; column-gap: 24px; row-gap: 6px; font-size: 13px; margin: 4px 0; }
.as-kv dt { color: var(--text-3); }
.as-kv dd { margin: 0; color: var(--text-1); font-variant-numeric: tabular-nums; }
.as-actions { list-style: none; margin: 4px 0; padding: 0; border: 1px solid var(--line); border-radius: 4px; overflow: hidden;
  background: linear-gradient(180deg, #171a1f, #131619); }
.as-actions li { position: relative; display: grid; grid-template-columns: 92px 1fr; column-gap: 14px; align-items: start; padding: 13px 16px;
  border-top: 1px solid var(--line); transition: background var(--t-fast) var(--ease); }
.as-actions li:first-child { border-top: 0; box-shadow: inset 2px 0 0 var(--accent); background: rgba(63, 162, 255, .05); }
.as-actions li:hover { background: rgba(63, 162, 255, .07); }
.as-actions .tag { font-family: var(--mono); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--text-3); padding-top: 3px; }
.as-actions li:first-child .tag { color: var(--brand-cyan); }
.as-actions .a { font-size: 15px; color: var(--text-0); font-weight: 600; line-height: 1.35; }
.as-actions .w { font-size: 13px; color: var(--text-2); margin-top: 3px; line-height: 1.45; }
.as-note { font-size: 12px; color: var(--text-3); margin: 8px 0 0; padding-left: 10px; border-left: 2px solid var(--line-strong);
  max-width: 96ch; line-height: 1.5; }
/* spec strip: one line of engineering facts, like the title block of a drawing */
.as-spec { display: flex; flex-wrap: wrap; border: 1px solid var(--line); border-radius: 2px; margin: 2px 0 14px; }
.as-spec > div { padding: 7px 14px; border-right: 1px solid var(--line); }
.as-spec > div:last-child { border-right: 0; }
.as-spec i { display: block; font-style: normal; font-size: 11px; color: var(--text-3); }
.as-spec b { font-family: var(--mono); font-size: 13px; font-weight: 400; color: var(--text-1); white-space: nowrap; }
.as-empty { border: 1px dashed var(--line-strong); padding: 20px 22px; margin: 12px 0; max-width: 760px; }
.as-empty h3 { font-size: 15px !important; font-weight: 600; margin: 0 0 6px; padding: 0; }
.as-empty p { font-size: 13px; color: var(--text-2); margin: 0; }

/* processing report */
.as-steps { display: grid; grid-template-columns: repeat(var(--n, 7), minmax(0, 1fr)); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.as-steps .st { padding: 12px 12px 12px 0; }
.as-steps .st + .st { padding-left: 12px; border-left: 1px solid var(--line); }
.as-steps .n { font-size: 12px; color: var(--text-2); display: flex; align-items: center; gap: 6px; }
.as-steps .n i { width: 7px; height: 7px; border-radius: 1px; background: var(--c, var(--s-ok)); }
.as-steps .v { font-family: var(--mono); font-size: 14px; color: var(--text-1); margin-top: 4px; }
.as-steps .d { font-size: 12px; color: var(--text-3); }
.as-steps .ms { font-family: var(--mono); font-size: 11px; color: var(--text-3); margin-top: 6px; white-space: nowrap; }

/* figure frame for the static training-report images (rendered light by matplotlib) */
[data-testid="stImage"] img { border: 1px solid var(--line); border-radius: 2px; }

/* ---------- ingest: centred drop zone ---------- */
.as-drop-title { text-align: center; margin: 26px 0 14px; }
.as-drop-title .k { font-family: var(--mono); font-size: 11px; letter-spacing: .2em; text-transform: uppercase; color: var(--brand-cyan); }
.as-drop-title h2 { font-size: 26px; font-weight: 600; letter-spacing: -.01em; color: var(--text-0); margin: 6px 0 4px; padding: 0; }
.as-drop-title p { font-size: 14px; color: var(--text-2); margin: 0; }
.st-key-ingest_drop [data-testid="stFileUploaderDropzone"] { min-height: 190px; padding: 28px; border: 1px dashed rgba(95, 212, 248, .45);
  border-radius: 8px; background: radial-gradient(80% 120% at 50% 0%, rgba(22, 131, 242, .14), transparent 70%), #12161b;
  display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 10px; text-align: center; position: relative; overflow: hidden; }
.st-key-ingest_drop [data-testid="stFileUploaderDropzone"]::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px;
  background: linear-gradient(90deg, transparent, #5fd4f8, transparent); animation: as-sweep 3s var(--ease) infinite; }
.st-key-ingest_drop [data-testid="stFileUploaderDropzone"]:hover { border-color: var(--brand-cyan); box-shadow: 0 0 0 4px rgba(95, 212, 248, .08); }
.as-or { display: flex; align-items: center; gap: 12px; margin: 18px 0 6px; font-family: var(--mono); font-size: 11px; letter-spacing: .16em;
  text-transform: uppercase; color: var(--text-3); }
.as-or::before, .as-or::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.as-done { display: flex; align-items: center; gap: 16px; padding: 18px 22px; margin: 18px 0 12px; border: 1px solid rgba(66, 190, 101, .45);
  border-radius: 6px; background: linear-gradient(100deg, rgba(66, 190, 101, .12), rgba(18, 22, 27, .2) 60%); }
.as-done .ok { width: 34px; height: 34px; border-radius: 50%; flex: none; display: grid; place-items: center; background: rgba(66, 190, 101, .18);
  border: 1px solid var(--s-ok); animation: as-spin-in .6s var(--ease-out) both; }
.as-done .ok::after { content: ""; width: 12px; height: 6px; border-left: 2px solid var(--s-ok); border-bottom: 2px solid var(--s-ok);
  transform: translateY(-2px) rotate(-45deg); }
.as-done b { display: block; font-size: 18px; font-weight: 600; color: var(--text-0); }
.as-done span { font-family: var(--mono); font-size: 12px; color: var(--text-2); }
.as-done.fail { border-color: rgba(250, 77, 86, .5); background: linear-gradient(100deg, rgba(250, 77, 86, .12), rgba(18, 22, 27, .2) 60%); }
.as-done.fail .ok { background: rgba(250, 77, 86, .18); border-color: var(--s-crit); }
.as-done.fail .ok::after { content: "!"; width: auto; height: auto; border: 0; transform: none; font-weight: 700; color: var(--s-crit); }

/* ---------- pre-flight processing: an aircraft crossing a radar sky while each step is checked off ---------- */
@keyframes as-fly { 0% { left: -14%; } 100% { left: 104%; } }
@keyframes as-bob { 0%, 100% { transform: translateY(-50%) rotate(-1deg); } 50% { transform: translateY(calc(-50% - 6px)) rotate(1deg); } }
@keyframes as-step { to { color: var(--text-0); } }
@keyframes as-step-dot { 0% { border-color: var(--line-strong); background: transparent; box-shadow: none; }
  30% { border-color: var(--brand-cyan); background: transparent; box-shadow: 0 0 0 4px rgba(95, 212, 248, .2); }
  100% { border-color: var(--s-ok); background: var(--s-ok); box-shadow: none; } }
@keyframes as-fill { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes as-blink { 0%, 60%, 100% { opacity: .25; } 30% { opacity: 1; } }
@keyframes as-radar { to { transform: rotate(360deg); } }
.as-proc { position: relative; margin: 18px 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden;
  background: linear-gradient(180deg, #0f1318, #0b0d10); }
.as-proc .sky { position: relative; height: 190px; overflow: hidden; border-bottom: 1px solid var(--line);
  background: radial-gradient(70% 140% at 50% 120%, rgba(22, 131, 242, .22), transparent 60%),
    linear-gradient(rgba(95, 212, 248, .06) 1px, transparent 1px), linear-gradient(90deg, rgba(95, 212, 248, .06) 1px, transparent 1px);
  background-size: auto, 38px 38px, 38px 38px; }
.as-proc .radar { position: absolute; right: 6%; top: 50%; width: 150px; height: 150px; margin-top: -75px; border-radius: 50%;
  border: 1px solid rgba(95, 212, 248, .25); background: repeating-radial-gradient(circle, transparent 0 24px, rgba(95, 212, 248, .12) 25px 26px); }
.as-proc .radar::after { content: ""; position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(from 0deg, rgba(95, 212, 248, .45), rgba(95, 212, 248, 0) 70deg, transparent 360deg); animation: as-radar 2.2s linear infinite; }
.as-proc .path { position: absolute; left: 0; right: 0; top: 56%; height: 0; border-top: 1px dashed rgba(95, 212, 248, .3); }
.as-proc .plane { position: absolute; top: 56%; width: 92px; height: 74px; animation: as-fly var(--dur, 3.6s) cubic-bezier(.45, .05, .35, 1) both,
  as-bob 1.6s var(--ease) infinite; }
.as-proc .plane .body { position: absolute; inset: 0; background: linear-gradient(180deg, #f4f6f8, #9fb4c8);
  clip-path: polygon(100% 50%, 94% 46.5%, 60% 45.5%, 36% 6%, 29% 6%, 44% 45%, 16% 45.5%, 9% 28%, 4% 28%, 8% 46%, 1% 47.5%, 1% 52.5%,
    8% 54%, 4% 72%, 9% 72%, 16% 54.5%, 44% 55%, 29% 94%, 36% 94%, 60% 54.5%, 94% 53.5%);
  filter: drop-shadow(0 0 10px rgba(95, 212, 248, .6)); }
.as-proc .plane .trail { position: absolute; right: 96%; top: 50%; width: 360px; height: 3px; margin-top: -1.5px; border-radius: 2px;
  background: linear-gradient(90deg, transparent, rgba(95, 212, 248, .15) 40%, rgba(212, 241, 255, .85)); }
.as-proc .plane .nav { position: absolute; width: 4px; height: 4px; border-radius: 50%; animation: as-blink 1s linear infinite; }
.as-proc .plane .nav.l { left: 31%; top: 5%; background: #fa4d56; box-shadow: 0 0 8px #fa4d56; }
.as-proc .plane .nav.r { left: 31%; bottom: 5%; background: #42be65; box-shadow: 0 0 8px #42be65; animation-delay: .5s; }
.as-proc .hud { position: absolute; left: 22px; top: 18px; }
.as-proc .hud .k { font-family: var(--mono); font-size: 11px; letter-spacing: .18em; text-transform: uppercase; color: var(--brand-cyan); }
.as-proc .hud b { display: block; margin-top: 6px; font-size: 20px; font-weight: 600; color: var(--text-0); }
.as-proc .hud span { font-family: var(--mono); font-size: 12px; color: var(--text-3); }
.as-proc .steps { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 28px; padding: 16px 22px 6px; }
.as-proc .st { display: flex; align-items: center; gap: 10px; padding: 7px 0; font-size: 13px; color: var(--text-3); border-top: 1px solid var(--line);
  animation: as-step .3s var(--ease) both; animation-delay: var(--d); }
.as-proc .st i { width: 11px; height: 11px; border-radius: 50%; border: 1.5px solid var(--line-strong); flex: none;
  animation: as-step-dot var(--step, .34s) var(--ease) both; animation-delay: var(--d); }
.as-proc .st small { margin-left: auto; font-family: var(--mono); font-size: 11px; color: var(--text-3); }
.as-proc .bar { height: 3px; margin: 10px 22px 18px; background: var(--line); border-radius: 2px; overflow: hidden; }
.as-proc .bar i { display: block; height: 100%; background: linear-gradient(90deg, #1683f2, #5fd4f8); transform-origin: left;
  animation: as-fill var(--dur, 3.6s) linear both; }
@media (max-width: 700px) { .as-proc .steps { grid-template-columns: 1fr; } .as-proc .radar { display: none; } }

/* ---------- sidebar: drifting aurora, a light running down the edge, kicker headers, a radar status module ---------- */
@keyframes as-aurora { 0%, 100% { background-position: 0% 0%, 100% 100%, 0 0; } 50% { background-position: 60% 30%, 40% 70%, 0 0; } }
@keyframes as-edge { from { transform: translateY(-120%); } to { transform: translateY(120vh); } }
@keyframes as-active { from { background-position: 200% 0; } to { background-position: -200% 0; } }
[data-testid="stSidebar"] { background: radial-gradient(60% 40% at 10% 0%, rgba(22, 131, 242, .22), transparent 70%),
    radial-gradient(60% 40% at 90% 100%, rgba(61, 219, 217, .10), transparent 70%), #0f1215 !important;
  background-size: 160% 160%, 160% 160%, auto !important; animation: as-aurora 18s var(--ease) infinite; border-right: 1px solid var(--line); }
[data-testid="stSidebar"]::after { content: ""; position: absolute; top: 0; right: -1px; width: 1px; height: 140px; z-index: 5; pointer-events: none;
  background: linear-gradient(180deg, transparent, #5fd4f8, transparent); animation: as-edge 6s linear infinite; }
/* sections stay open: no collapse arrow, the header is a label */
[data-testid="stNavSectionHeader"] { pointer-events: none; margin-top: 18px !important; padding-left: 12px !important; }
[data-testid="stNavSectionHeader"] [data-testid="stIconMaterial"], [data-testid="stNavSectionHeader"] > div:last-child { display: none !important; }
[data-testid="stNavSectionHeader"] p { font-family: var(--mono) !important; font-size: 10.5px !important; letter-spacing: .2em !important;
  text-transform: uppercase; color: var(--brand-cyan) !important; display: flex; align-items: center; gap: 8px; }
[data-testid="stNavSectionHeader"] p::after { content: ""; width: 60px; height: 1px; background: linear-gradient(90deg, rgba(95, 212, 248, .45), transparent); }
[data-testid="stSidebarNavLink"] { margin: 1px 8px !important; padding: 7px 10px !important; border-radius: 4px !important; position: relative;
  transition: background var(--t-fast) var(--ease), transform var(--t-std) var(--ease-out) !important; }
[data-testid="stSidebarNavLink"]:hover { background: rgba(63, 162, 255, .08) !important; transform: translateX(3px); }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: linear-gradient(100deg, rgba(22, 131, 242, .32), rgba(22, 131, 242, .06) 60%,
    rgba(95, 212, 248, .18) 70%, rgba(22, 131, 242, .06) 80%) !important; background-size: 300% 100% !important;
  animation: as-active 6s linear infinite; box-shadow: inset 2px 0 0 #5fd4f8, 0 0 22px -10px rgba(95, 212, 248, .9) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stIconMaterial"] { color: #5fd4f8 !important;
  filter: drop-shadow(0 0 6px rgba(95, 212, 248, .8)); }
.as-side { margin: 18px 4px 6px; padding: 14px; border: 1px solid rgba(95, 212, 248, .22); border-radius: 8px; position: relative; overflow: hidden;
  background: linear-gradient(180deg, rgba(22, 131, 242, .10), rgba(12, 14, 17, .6)); }
.as-side .top { display: flex; align-items: center; gap: 12px; }
.as-side .scope { position: relative; width: 52px; height: 52px; flex: none; border-radius: 50%; border: 1px solid rgba(95, 212, 248, .35);
  background: repeating-radial-gradient(circle, transparent 0 8px, rgba(95, 212, 248, .14) 9px 10px); }
.as-side .scope::before { content: ""; position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(from 0deg, rgba(95, 212, 248, .55), transparent 80deg); animation: as-radar 2.6s linear infinite; }
.as-side .scope::after { content: ""; position: absolute; width: 5px; height: 5px; border-radius: 50%; left: 62%; top: 30%; background: var(--c, #5fd4f8);
  box-shadow: 0 0 8px var(--c, #5fd4f8); animation: as-blink 2.6s linear infinite; }
.as-side .k { font-family: var(--mono); font-size: 10px; letter-spacing: .18em; text-transform: uppercase; color: var(--c, #5fd4f8); }
.as-side b { display: block; margin-top: 3px; font-size: 14px; font-weight: 600; color: var(--text-0); line-height: 1.25; word-break: break-all; }
.as-side dl { display: grid; grid-template-columns: max-content 1fr; gap: 4px 10px; margin: 12px 0 0; font-size: 12px; }
.as-side dt { font-family: var(--mono); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--text-3); padding-top: 1px; }
.as-side dd { margin: 0; color: var(--text-1); }

/* ---------- home: intro between the title band and the showcase ---------- */
.as-intro { display: grid; grid-template-columns: minmax(260px, .9fr) minmax(320px, 1.4fr); gap: 32px; align-items: start; margin: 8px 0 22px; }
.as-intro .k { font-family: var(--mono); font-size: 11px; letter-spacing: .2em; text-transform: uppercase; color: var(--brand-cyan); }
.as-intro h2 { margin: 8px 0 0; padding: 0; font-size: 28px; font-weight: 600; line-height: 1.2; letter-spacing: -.015em; color: var(--text-0); }
.as-intro p { margin: 0; font-size: 15px; line-height: 1.6; color: var(--text-2); max-width: 70ch; }
.as-intro .pillars { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.as-intro .pillars div { padding: 12px 14px; border: 1px solid var(--line); border-top: 2px solid var(--accent); border-radius: 4px;
  background: linear-gradient(180deg, #171a1f, #131619); transition: transform var(--t-std) var(--ease-out), border-color var(--t-std) var(--ease); }
.as-intro .pillars div:hover { transform: translateY(-2px); border-color: rgba(63, 162, 255, .45); }
.as-intro .pillars b { display: block; font-size: 14px; font-weight: 600; color: var(--text-0); }
.as-intro .pillars span { display: block; margin-top: 4px; font-size: 12px; line-height: 1.45; color: var(--text-2); }
@media (max-width: 1000px) { .as-intro { grid-template-columns: 1fr; gap: 14px; } .as-intro .pillars { grid-template-columns: 1fr; } }

/* status card, wide: one row on the ingest page */
.as-side.wide { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; margin: 16px 0 6px; padding: 16px 20px; }
.as-side.wide .top { flex: none; min-width: 230px; }
.as-side.wide dl { display: flex; flex-wrap: wrap; gap: 6px 26px; margin: 0; }
.as-side.wide dl > div { display: flex; flex-direction: column; gap: 3px; }
.as-side.wide dd { font-size: 13px; }

/* ---------- ingest v2: readiness strip, upload box, column reference ---------- */
@keyframes as-ready { 0%, 100% { box-shadow: 0 0 0 0 rgba(66, 190, 101, .55); } 50% { box-shadow: 0 0 0 5px rgba(66, 190, 101, 0); } }
@keyframes as-float-icon { 0%, 100% { transform: translate(-50%, 0); } 50% { transform: translate(-50%, -6px); } }
.as-ready { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin: 18px 0 8px; }
.as-ready .m { position: relative; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #12161b;
  transition: transform var(--t-std) var(--ease-out), border-color var(--t-std) var(--ease), opacity var(--t-std) var(--ease); }
.as-ready .m:hover { transform: translateY(-3px); border-color: rgba(95, 212, 248, .5); }
.as-ready .m img { display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; }
.as-ready .m .b { padding: 8px 10px 9px; display: flex; align-items: center; gap: 7px; }
.as-ready .m .b i { width: 7px; height: 7px; border-radius: 50%; background: var(--s-ok); flex: none; animation: as-ready 2.2s var(--ease) infinite; }
.as-ready .m .b span { font-size: 12px; font-weight: 500; color: var(--text-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.as-ready .m.dim { opacity: .38; }
.as-ready .m.on { border-color: var(--s-ok); box-shadow: 0 0 0 1px var(--s-ok), 0 10px 26px -14px rgba(66, 190, 101, .9); }
.as-ready-note { display: flex; justify-content: space-between; gap: 12px; font-family: var(--mono); font-size: 11px; letter-spacing: .08em;
  text-transform: uppercase; color: var(--text-3); margin: 0 2px 6px; }
.as-ready-note b { color: var(--s-ok); font-weight: 500; }
.st-key-ingest_drop [data-testid="stFileUploaderDropzone"] { min-height: 230px !important; padding-top: 92px !important; }
.st-key-ingest_drop [data-testid="stFileUploaderDropzone"]::after { content: ""; position: absolute; left: 50%; top: 26px; width: 52px; height: 52px;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%235fd4f8' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 16V4'/%3E%3Cpath d='M7 9l5-5 5 5'/%3E%3Cpath d='M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2'/%3E%3C/svg%3E") center / 52px no-repeat; animation: as-float-icon 2.8s var(--ease) infinite; pointer-events: none; }
.st-key-ingest_drop [data-testid="stFileUploaderDropzoneInstructions"] { text-align: center; }
.as-cols { margin: 6px 0 2px; }
.as-cols .fmt { font-size: 13px; color: var(--text-2); margin-bottom: 10px; }
.as-cols .fmt b { color: var(--text-0); font-weight: 600; }
.as-cols .g { margin: 10px 0 4px; font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--brand-cyan); }
.as-cols .g small { color: var(--text-3); letter-spacing: .04em; margin-left: 6px; }
.as-cols .chips { display: flex; flex-wrap: wrap; gap: 6px; }
.as-cols .c { display: inline-flex; align-items: baseline; gap: 6px; padding: 4px 8px; border: 1px solid var(--line-strong); border-radius: 3px;
  background: #13171c; font-size: 12px; color: var(--text-2); }
.as-cols .c code { font-family: var(--mono) !important; font-size: 12px; color: var(--text-0) !important; background: none !important; border: 0 !important;
  padding: 0 !important; }
.as-cols .c.id { border-color: rgba(63, 162, 255, .5); }
.as-cols .c.set { border-color: rgba(241, 194, 27, .45); }
@media (max-width: 900px) { .as-ready { grid-template-columns: repeat(3, minmax(0, 1fr)); } }

/* ---------- past records line (ingest) ---------- */
.as-rec { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin: -4px 0 10px; font-size: 12.5px; color: var(--text-2); }
.as-rec b { color: var(--text-0); font-weight: 600; font-family: var(--mono); }
.as-rec .db { font-family: var(--mono); font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--brand-cyan);
  border: 1px solid rgba(95, 212, 248, .4); border-radius: 3px; padding: 2px 7px; }
.as-rec .err { color: var(--s-warn); }

/* ---------- home: title band (radar grid, scan sweep, letter-by-letter wordmark, channel ticker) ---------- */
@keyframes as-letter { from { opacity: 0; transform: translateY(.45em) scale(.96); filter: blur(6px); } to { opacity: 1; transform: none; filter: none; } }
@keyframes as-scan { 0% { transform: translateX(-30%); opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { transform: translateX(130%); opacity: 0; } }
@keyframes as-grid-drift { from { background-position: 0 0, 0 0; } to { background-position: 0 44px, 44px 0; } }
@keyframes as-glow { 0%, 100% { opacity: .75; transform: scale(1); } 50% { opacity: 1; transform: scale(1.08); } }
@keyframes as-tick { from { transform: translateX(0); } to { transform: translateX(-50%); } }
@keyframes as-fade-up { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.as-home { position: relative; overflow: hidden; margin: -8px 0 18px; border: 1px solid var(--line); border-radius: 6px;
  background: radial-gradient(80% 140% at 12% 0%, rgba(22, 131, 242, .20), transparent 60%), linear-gradient(180deg, #11151a, #0c0e11); }
.as-home .grid { position: absolute; inset: 0; opacity: .5;
  background-image: linear-gradient(rgba(95, 212, 248, .07) 1px, transparent 1px), linear-gradient(90deg, rgba(95, 212, 248, .07) 1px, transparent 1px);
  background-size: 44px 44px; animation: as-grid-drift 6s linear infinite;
  -webkit-mask-image: radial-gradient(90% 120% at 30% 40%, #000 30%, transparent 85%); mask-image: radial-gradient(90% 120% at 30% 40%, #000 30%, transparent 85%); }
.as-home .glow { position: absolute; right: -8%; top: -60%; width: 60%; height: 220%; border-radius: 50%;
  background: radial-gradient(closest-side, rgba(95, 212, 248, .16), transparent 70%); animation: as-glow 7s var(--ease) infinite; }
.as-home .scan { position: absolute; top: 0; bottom: 0; left: 0; width: 34%; pointer-events: none;
  background: linear-gradient(90deg, transparent, rgba(95, 212, 248, .10) 70%, rgba(212, 241, 255, .55) 99%, transparent);
  animation: as-scan 5.5s var(--ease) 1.2s infinite; }
.as-home .body { position: relative; padding: 40px 40px 30px; }
.as-home .mark { display: flex; align-items: center; gap: 12px; animation: as-fade-up .7s var(--ease-out) both; }
.as-home .mark img { width: 40px; height: 40px; animation: as-spin-in .9s var(--ease-out) both, as-float 6s var(--ease) 1s infinite; }
.as-home .mark span { font-family: var(--mono); font-size: 12px; letter-spacing: .22em; text-transform: uppercase; color: var(--brand-cyan); }
.as-home h1 { margin: 18px 0 0; padding: 0; font-size: clamp(44px, 7.4vw, 104px); font-weight: 600; line-height: .95; letter-spacing: .06em;
  white-space: nowrap; color: var(--text-0); }
.as-home h1 i { display: inline-block; font-style: normal; color: var(--text-0);
  animation: as-letter .7s var(--ease-out) both, as-glint 6s var(--ease) infinite;
  animation-delay: calc(var(--i) * 55ms + 150ms), calc(var(--i) * 70ms + 2s); }
@keyframes as-glint { 0%, 8%, 100% { color: var(--text-0); text-shadow: none; }
  4% { color: #5fd4f8; text-shadow: 0 0 24px rgba(95, 212, 248, .75), 0 0 2px rgba(212, 241, 255, .9); } }
.as-home .line { margin-top: 18px; display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 17px; color: var(--text-2);
  animation: as-fade-up .8s var(--ease-out) .9s both; }
.as-home .line b { font-weight: 500; }
.as-home .line .hl { color: var(--text-0); font-weight: 600; }
.as-home .ticker { position: relative; overflow: hidden; border-top: 1px solid var(--line); background: rgba(10, 12, 15, .7);
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent); mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent); }
.as-home .track { display: flex; width: max-content; animation: as-tick 38s linear infinite; }
.as-home .track span { font-family: var(--mono); font-size: 12px; letter-spacing: .14em; color: var(--text-3); padding: 9px 22px; white-space: nowrap; }
.as-home .track span::before { content: ""; display: inline-block; width: 5px; height: 5px; margin-right: 10px; border-radius: 50%;
  background: var(--brand-cyan); vertical-align: middle; opacity: .7; }
.as-cards.as-home-cards { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.as-home-cards .as-card .body { padding: 12px 14px; }
.as-home-cards .as-card b { font-size: 15px; }
@media (max-width: 1100px) { .as-cards.as-home-cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) { .as-cards.as-home-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 900px) { .as-home .body { padding: 28px 20px 22px; } .as-home h1 { letter-spacing: .03em; } }

/* landing hero */
.as-hero .eyebrow { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.as-hero .eyebrow img { width: 46px; height: 46px; animation: as-spin-in .9s var(--ease-out) both, as-float 6s var(--ease) 1s infinite; }
.as-hero .eyebrow b { display: block; font-size: 13px; font-weight: 600; letter-spacing: .14em; color: var(--text-1); }
.as-hero .eyebrow i { display: block; font-style: normal; font-size: 12px; color: var(--brand-cyan); letter-spacing: .04em; margin-top: 2px; }
.as-hero h1 { font-size: 32px; font-weight: 600; margin: 0 0 12px; padding: 0; line-height: 1.16; letter-spacing: -.01em; }
.as-hero h1 span { background: linear-gradient(90deg, #3fa2ff, #5fd4f8); -webkit-background-clip: text; background-clip: text; color: transparent; }
.as-hero p { font-size: 15px; color: var(--text-2); margin: 0; line-height: 1.55; max-width: 60ch; }

/* landing: how it works */
.as-flow { position: relative; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 4px 0 6px;
  border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); overflow: hidden; }
.as-flow .st { padding: 16px 18px 16px 0; position: relative; }
.as-flow .st + .st { padding-left: 18px; border-left: 1px solid var(--line); }
.as-flow .n { font-family: var(--mono); font-size: 12px; color: var(--brand-cyan); letter-spacing: .08em; }
.as-flow b { display: block; font-size: 15px; font-weight: 600; color: var(--text-1); margin: 4px 0 6px; }
.as-flow p { font-size: 13px; color: var(--text-2); margin: 0 0 8px; line-height: 1.45; }
.as-flow i { font-style: normal; font-family: var(--mono); font-size: 11px; color: var(--text-3); }
.as-flow .pulse { position: absolute; left: 0; top: -1px; height: 2px; width: 18%;
  background: linear-gradient(90deg, transparent, #5fd4f8, transparent); animation: as-flow 3.6s var(--ease) infinite; }
@keyframes as-flow { from { transform: translateX(-100%); } to { transform: translateX(560%); } }

/* landing: component cards */
.as-card { border: 1px solid var(--line); border-radius: 6px; overflow: hidden; background: var(--surface); margin-bottom: 8px;
  transition: border-color var(--t-std) var(--ease), transform var(--t-std) var(--ease-out), box-shadow var(--t-std) var(--ease); }
.as-card:hover { border-color: rgba(63, 162, 255, .55); transform: translateY(-3px); box-shadow: 0 14px 30px -18px rgba(22, 131, 242, .7); }
.as-card .img { aspect-ratio: 16 / 10; overflow: hidden; background: #0b0d10; }
.as-card .img img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .6s var(--ease-out); }
.as-card:hover .img img { transform: scale(1.06); }
.as-card .body { padding: 12px 14px 14px; }
.as-card b { display: block; font-size: 14px; font-weight: 600; color: var(--text-1); }
.as-card p { font-size: 12px; color: var(--text-2); margin: 4px 0 8px; line-height: 1.45; min-height: 3.4em; }
.as-card .data { display: block; font-size: 11px; color: var(--text-3); }
.as-card .metric { display: block; font-family: var(--mono); font-size: 11px; color: var(--brand-cyan); margin-top: 6px; }
.as-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; margin-top: 6px; }
a.as-card { text-decoration: none !important; color: inherit; display: block; margin: 0; }
.as-card .go { display: inline-flex; align-items: center; gap: 6px; margin-top: 10px; font-size: 12px; font-weight: 600; color: var(--accent); }
.as-card .go::after { content: "→"; transition: transform var(--t-std) var(--ease-out); }
.as-card:hover .go::after { transform: translateX(4px); }
.as-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr)); gap: 0 18px; margin-top: 18px; }
.as-kpis .as-stat { padding: 10px 0 10px 14px !important; border: 0 !important; border-left: 2px solid var(--line-strong) !important;
  border-radius: 0; background: none; transform: none !important; box-shadow: none !important; }
.as-kpis .as-stat::before, .as-kpis .as-stat::after { display: none; }
.as-kpis .as-stat:first-child { border-left-color: var(--accent) !important; }
.as-kpis .v { font-family: var(--mono); font-size: 26px; font-weight: 500; color: var(--text-1); line-height: 1.2; }
.as-kpis .l { font-size: 13px; color: var(--text-2); margin-top: 2px; }
.as-kpis .f { font-size: 11px; color: var(--text-3); margin-top: 2px; }

@media (max-width: 1100px) {
  .as-verdict { grid-template-columns: 1fr 1fr; }
  .as-verdict > div:last-child { grid-column: 1 / -1; border-left: 0; border-top: 1px solid var(--line); }
}
@media (max-width: 900px) {
  .as-ind .row { grid-template-columns: 54px 1fr 78px; } .as-ind .row .sp, .as-ind .row .lv { display: none; }
  .as-sec .n { display: none; }
  .as-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .as-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .as-dist .keys { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  [data-testid="stMainBlockContainer"] { padding: 2rem 1rem 3rem; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition: none !important; animation: none !important; } }
/* the motion runtime's carrier iframe takes no space */
[data-testid="stElementContainer"]:has(iframe[srcdoc*="__asMotion"]) { display: none; }
</style>
"""


def inject():
    # A style-only st.html goes to Streamlit's event container, which does not render it, so add an
    # anchor element; the CSS then hides the anchor's own (empty) container.
    st.html(GLOBAL_CSS + '<div class="as-css-anchor"></div>')


# ---------------------------------------------------------------- motion runtime
# Runs once in the parent page (the component iframe is same-origin): staggers the reveal of new
# content and counts numbers to their value, from the previous value when the same readout updates.
MOTION_JS = r"""
<script>
(function () {
  const P = window.parent, doc = P.document;
  if (P.__asMotion) return; P.__asMotion = 1;
  if (P.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const REVEAL = '.as-head, .as-home-cards, .as-hero, .as-flow, .as-kpis, .as-cards, .as-sec, .as-stats, .as-verdict, .as-ind, .as-dist, .as-spec, .as-steps, .as-kv, .as-actions, .as-empty, .as-note, '
    + '[data-testid="stPlotlyChart"], [data-testid="stDataFrame"], [data-testid="stCustomComponentV1"], [data-testid="stImage"]';
  const COUNT = '.as-stat .v, .as-verdict .num, .as-ind .val, .as-dist .k .n, .as-steps .v';
  const seen = new WeakSet(), last = new Map();
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  const textNode = (el) => { for (const n of el.childNodes) if (n.nodeType === 3 && /\d/.test(n.nodeValue)) return n; return null; };
  function count(el) {
    const tn = textNode(el); if (!tn) return;
    const txt = tn.nodeValue, nums = txt.match(/\d[\d,]*(\.\d+)?/g);
    if (!nums || nums.length !== 1) return;
    const m = txt.match(/^(.*?)(\d[\d,]*)(\.\d+)?(.*)$/); if (!m) return;
    const pre = m[1], whole = m[2], dec = m[3] || '', post = m[4];
    const target = parseFloat(whole.replace(/,/g, '') + dec); if (!isFinite(target)) return;
    const decimals = dec ? dec.length - 1 : 0, comma = whole.includes(',');
    const lab = el.parentElement && el.parentElement.querySelector('.l, .t, .k, .code');
    const key = P.location.pathname + '|' + (lab ? lab.textContent : '') + '|' + pre;
    const from = last.has(key) ? last.get(key) : 0;
    last.set(key, target);
    if (from === target) return;
    const fmt = (v) => pre + (comma ? v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
      : v.toFixed(decimals)) + post;
    const t0 = P.performance.now(), dur = 800;
    const step = (now) => {
      if (!tn.isConnected) return;
      const k = Math.min(1, (now - t0) / dur);
      tn.nodeValue = k < 1 ? fmt(from + (target - from) * ease(k)) : txt;
      if (k < 1) P.requestAnimationFrame(step);
    };
    tn.nodeValue = fmt(from); P.requestAnimationFrame(step);
  }
  let pending = false;
  function scan() {
    pending = false;
    const main = doc.querySelector('[data-testid="stMain"]'); if (!main) return;
    let i = 0;
    main.querySelectorAll(REVEAL).forEach((el) => {
      if (seen.has(el)) return; seen.add(el);
      el.style.setProperty('--as-d', Math.min(i++, 12) * 45 + 'ms');
      el.classList.add('as-reveal');
      el.addEventListener('animationend', function done(e) {
        if (e.target !== el) return; el.classList.remove('as-reveal'); el.removeEventListener('animationend', done);
      });
    });
    main.querySelectorAll(COUNT).forEach((el) => { if (seen.has(el)) return; seen.add(el); count(el); });
  }
  new P.MutationObserver(() => { if (!pending) { pending = true; P.requestAnimationFrame(scan); } })
    .observe(doc.body, { childList: true, subtree: true });
  scan();
})();
</script>
"""


def motion():
    """Load the motion runtime once: a zero-height same-origin iframe in the sidebar (hidden by CSS)."""
    import streamlit.components.v1 as components
    with st.sidebar:
        components.html(MOTION_JS, height=0)

# ---------------------------------------------------------------- Plotly
def _register_plotly_template():
    t = TOKENS
    # Readable at a glance: 12 px mono ticks one step brighter, light grid, thousands separators, axis titles in sans.
    axis = dict(gridcolor="#20252b", gridwidth=1, zeroline=False, linecolor=t["line_strong"], ticks="outside",
                tickcolor=t["line_strong"], ticklen=4, tickfont=dict(family=MONO, size=12, color="#98a0aa"),
                title=dict(font=dict(family=SANS, size=13, color=t["text_2"]), standoff=10), showspikes=False,
                automargin=True, separatethousands=True, nticks=8)
    pio.templates["aerosentinel"] = go.layout.Template(layout=dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=SANS, color=t["text_2"], size=12),
        colorway=[t["accent"], t["accent_2"], t["text_2"], "#f1c21b", "#ff832b"],
        xaxis=axis, yaxis=axis,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=13, color=t["text_2"]), orientation="h", y=1.02, x=0,
                    yanchor="bottom", itemwidth=40),
        hoverlabel=dict(bgcolor="#11151a", bordercolor=t["accent"], align="left",
                        font=dict(family=MONO, size=13, color=t["text_1"])),
        margin=dict(t=28, b=36, l=48, r=16),
        annotationdefaults=dict(font=dict(family=SANS, size=11, color=t["text_3"])),
    ))
    pio.templates.default = "aerosentinel"


_register_plotly_template()


def chart(fig, key=None, height=None, on_select=None):
    """Plotly chart in the AeroSentinel template (Streamlit's own theme would override it)."""
    if height:
        fig.update_layout(height=height)
    kwargs = dict(theme=None, key=key, config={"displayModeBar": False})
    if on_select:
        kwargs.update(on_select=on_select, selection_mode="points")
    return st.plotly_chart(fig, **kwargs)


# ---------------------------------------------------------------- HTML primitives
def esc(text):
    return html.escape(str(text))


def page_head(title, context="", meta="", kicker=""):
    """Title row: a mono kicker, the page name and optional right-aligned metadata (pre-escaped HTML).

    `context` (the page's one-line description) is accepted but not shown: the pages carry only their title."""
    st.html(f'<div class="as-head"><div>{f"<div class=k>{esc(kicker)}</div>" if kicker else ""}<h1>{esc(title)}</h1></div>'
            f'{f"<div class=meta>{meta}</div>" if meta else ""}</div>')


def section(title, note="", kicker=""):
    """Section heading: an uppercase mono kicker over the title, a rule that fades out, and a right-aligned note."""
    title = re.sub(r"^\d+\.\s+", "", str(title))  # headings are named, never numbered
    head = f'<span class="k">{esc(kicker)}</span>' if kicker else ""
    st.html(f'<div class="as-sec{"" if kicker else " nk"}"><div class="h">{head}<h2>{esc(title)}</h2></div><div class="r"></div>'
            f'{f"<div class=n>{esc(note)}</div>" if note else ""}</div>')


def stat(label, value, unit="", foot="", color=None, meter=None, tip=""):
    """One readout tile for stats(). Numbers are set in mono, words in sans.

    color marks a status (top line, marker and value); meter (0 to 1) draws a bar under the value;
    tip is a plain-language explanation that slides up when the tile is hovered or focused.
    """
    is_text = isinstance(value, str) and not any(ch.isdigit() for ch in value)
    cls = "v" + (" t" if is_text else "") + (" c" if color else "")
    bar = ""
    if meter is not None:
        share = max(0.0, min(1.0, float(meter)))
        bar = f'<div class="m"><i style="width:{share:.1%};--mc:{color or TOKENS["accent"]}"></i></div>'
    hint = f'<div class="tip"><b>What this means</b>{esc(tip)}</div>' if tip else ""
    return (f'<div class="as-stat{" has-tip" if tip else ""}"{f" style=--c:{color}" if color else ""}{" tabindex=0" if tip else ""}>'
            f'<div class="l">{esc(label)}</div><div class="{cls}">{esc(value)}'
            f'{f"<small>{esc(unit)}</small>" if unit else ""}</div>{bar}{f"<div class=f>{foot}</div>" if foot else ""}{hint}</div>')


def chip(text, color=None):
    """Small status chip: a marker and a word, tinted by the status colour."""
    return f'<span class="as-chip"{f" style=--c:{color}" if color else ""}>{esc(text)}</span>'


def life_gauge(value, low, high, cap, limits, band, label):
    """Where the forecast sits on the four risk bands: zones from 0 to the model ceiling, the likely range as a
    frame and the estimate as a marker. limits: band -> upper limit; band: the predicted band (highlighted)."""
    order = ["FAILURE_LIKELY", "HIGH_RISK", "AT_RISK", "NORMAL"]
    edges = [0, limits["FAILURE_LIKELY"], limits["HIGH_RISK"], limits["AT_RISK"], cap]
    pct = lambda x: max(0.0, min(100.0, float(x) / cap * 100))  # noqa: E731
    zones = "".join(
        f'<span class="z{" on" if b == band else ""}" style="left:{pct(lo):.2f}%;width:calc({pct(hi) - pct(lo):.2f}% - 2px);--zc:{BAND_COLORS[b]}"'
        f' title="{esc(BAND_TEXT[b])}: {lo:g} to {hi:g}"></span>' for b, lo, hi in zip(order, edges, edges[1:]))
    ticks = "".join(f'<span class="tk" style="left:{pct(e):.2f}%">{e:g}</span>' for e in edges)
    frame = ""
    if low is not None and high is not None:
        frame = f'<span class="rng" style="left:{pct(low):.2f}%;width:{max(pct(high) - pct(low), 0.6):.2f}%" title="likely range"></span>'
    side = " a" if pct(value) < 14 else " b" if pct(value) > 86 else ""
    keys = "".join(f'<span class="{"on" if b == band else ""}" style="--zc:{BAND_COLORS[b]}"><i></i>{esc(BAND_TEXT[b])}</span>' for b in order)
    return (f'<div class="as-gauge">{zones}{frame}<span class="mk{side}" style="left:{pct(value):.2f}%"><b>{esc(label)}</b></span>{ticks}</div>'
            f'<div class="as-zones">{keys}</div>')


def verdict(state, kicker, reason, number="", number_label="", unit="", range_html="", gauge=""):
    """The unit's verdict in one panel: condition and why, the headline number, and its place on the risk bands."""
    s = STATES[state]
    live = " live" if state in ("CRITICAL", "WARNING") else ""
    mid = (f'<div><div class="k">{esc(number_label)}</div><div class="num">{esc(number)}</div><div class="u">{esc(unit)}</div>'
           f'{f"<div class=rg>{range_html}</div>" if range_html else ""}</div>') if number else ""
    right = f'<div><div class="k">Position on the risk bands</div>{gauge}</div>' if gauge else ""
    st.html(f'<div class="as-verdict{live}" style="--c:{s["color"]}"><div><div class="k">{esc(kicker)}</div>'
            f'<div class="s"><i></i>{esc(s["label"])}</div><p>{esc(reason)}</p></div>{mid}{right}</div>')


def _spark(values, limit=2.4):
    """A sensor's drift over its latest readings as a small area trace, with the warning level dashed.
    Drawn with CSS shapes: st.html strips inline SVG."""
    v = [float(x) for x in values] or [0.0]
    if len(v) == 1:
        v = v * 2
    lo, hi = min(-1.0, min(v)), max(4.0, max(v))
    x = lambda i: i / (len(v) - 1) * 100  # noqa: E731
    y = lambda val: 100 - (val - lo) / (hi - lo) * 100  # noqa: E731
    top = [f"{x(i):.1f}% {y(val):.1f}%" for i, val in enumerate(v)]
    under = [f"{x(i):.1f}% calc({y(val):.1f}% + 1.8px)" for i, val in reversed(list(enumerate(v)))]
    area, line = ", ".join([*top, "100% 100%", "0% 100%"]), ", ".join([*top, *under])
    return (f'<div class="sp" role="img" aria-label="drift over the latest readings"><span class="th" style="top:{y(limit):.1f}%"></span>'
            f'<span class="ar" style="clip-path:polygon({area})"></span><span class="ln" style="clip-path:polygon({line})"></span>'
            f'<span class="dot" style="top:{y(v[-1]):.1f}%"></span></div>')


def indicators(rows, per=""):
    """Leading indicators from [{'code', 'name', 'module', 'drift', 'trend', 'status', 'history', 'color'}]:
    one row per sensor with its drift trace, its drift now and its level."""
    out = []
    for r in rows:
        trend = f'{r["trend"]:+.1f} {esc(per)}' if per else ""
        out.append(
            f'<div class="row" style="--c:{r["color"]}" title="{esc(r["name"])}: {r["drift"]:+.1f} standard deviations from a healthy reading">'
            f'<div class="code">{esc(r["code"])}</div><div class="nm">{esc(r["name"])}<small>{esc(r["module"])}</small></div>'
            f'{_spark(r["history"])}<div class="val">{r["drift"]:+.1f}σ<small>{trend}</small></div>'
            f'<div class="lv">{chip(r["status"], r["color"])}</div></div>')
    st.html(f'<div class="as-ind">{"".join(out)}</div>')


def stats(items):
    st.html(f'<div class="as-stats">{"".join(items)}</div>')


def state_badge(state):
    s = STATES[state]
    return f'<span class="as-state" style="--c:{s["color"]}"><i></i>{esc(s["label"])}</span>'


def band_badge(band):
    color = BAND_COLORS.get(band, STATES["INSUFFICIENT"]["color"])
    return f'<span class="as-state" style="--c:{color}"><i></i>{esc(BAND_TEXT.get(band, band))}</span>'


def flags(items):
    return "".join(f'<span class="as-flag">{esc(x)}</span>' for x in items)


def distribution(counts):
    """Condition distribution: a 100% bar plus a labelled count per state, in severity order."""
    total = max(1, sum(counts.values()))
    bar = "".join(f'<span title="{esc(STATES[k]["label"])}: {n}" style="flex:{n};background:{STATES[k]["color"]}"></span>'
                  for k, n in counts.items() if n)
    keys = "".join(f'<div class="k" style="--c:{STATES[k]["color"]}"><div class="n">{n}</div>'
                   f'<div class="t">{esc(STATES[k]["label"])} ({n / total:.0%})</div></div>' for k, n in counts.items())
    st.html(f'<div class="as-dist"><div class="bar">{bar}</div><div class="keys">{keys}</div></div>')


def spec(items):
    """Spec strip from [(label, value), ...]: compact engineering facts in one bordered row."""
    st.html('<div class="as-spec">' + "".join(f"<div><i>{esc(k)}</i><b>{esc(v)}</b></div>" for k, v in items) + "</div>")


def kv(rows):
    """Definition list from [(label, value_html), ...]."""
    st.html('<dl class="as-kv">' + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>")


def actions(items):
    """Action list from [{'action', 'why'}], most important first: the first leads, the rest follow."""
    tags = ["Do first", "Then", "Also"]
    st.html('<ul class="as-actions">' + "".join(
        f'<li><div class="tag">{tags[min(i, 2)]}</div><div><div class="a">{esc(a["action"])}</div>'
        f'<div class="w">{esc(a["why"])}</div></div></li>' for i, a in enumerate(items)) + "</ul>")


def note(text):
    st.html(f'<div class="as-note">{text}</div>')


def empty(title, body):
    st.html(f'<div class="as-empty"><h3>{esc(title)}</h3><p>{body}</p></div>')


def guide(rows, label="How to read this page"):
    """A popover that explains the page in plain words: [(term, meaning), ...]."""
    with st.popover(label, icon=":material/help:"):
        st.html('<dl class="as-guide">' + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows) + "</dl>")


# The pipeline's real stages, in the order src/pipeline.py runs them.
PREFLIGHT = [
    ("Reading the file", "read"), ("Profiling the data", "eda"), ("Recognising the component", "route"),
    ("Validating the columns", "validate"), ("Cleaning the readings", "clean"), ("Correcting for operating conditions", "conditions"),
    ("Scoring health against a healthy baseline", "health"), ("Building causal features", "features"),
    ("Forecasting remaining life and risk", "rul"), ("Explaining the forecast", "explain"),
]


def preflight(name, duration=3.6):
    """The pre-flight animation shown while a file is processed: an aircraft crossing a radar sky while the
    pipeline's stages are checked off one after another. Pure CSS (st.html allows no script and no SVG)."""
    step = duration / len(PREFLIGHT)
    rows = "".join(f'<div class="st" style="--d:{i * step:.2f}s;--step:{step:.2f}s"><i></i>{esc(label)}<small>{esc(code)}</small></div>'
                   for i, (label, code) in enumerate(PREFLIGHT))
    return (f'<div class="as-proc" style="--dur:{duration}s"><div class="sky"><div class="radar"></div><div class="path"></div>'
            f'<div class="hud"><div class="k">Pre-flight checks</div><b>Processing {esc(name)}</b>'
            f'<span>reading, recognising and preparing the data before prediction</span></div>'
            f'<div class="plane"><span class="trail"></span><span class="body"></span><span class="nav l"></span><span class="nav r"></span></div>'
            f'</div><div class="steps">{rows}</div><div class="bar"><i></i></div></div>')


def status_card(title, rows, ready=True):
    """The system status card: a radar scope, a headline and a few facts [(label, value), ...], as one wide row."""
    color = STATES["HEALTHY"]["color"] if ready else "#5fd4f8"
    facts = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in rows)
    return (f'<div class="as-side wide" style="--c:{color}"><div class="top"><div class="scope"></div><div>'
            f'<div class="k">{"Data loaded" if ready else "Standing by"}</div><b>{esc(title)}</b></div></div>'
            f'{f"<dl>{facts}</dl>" if facts else ""}</div>')

def readiness(items, note_left, note_right=""):
    """The five component models as a strip of image tiles with a live 'ready' light.

    items: [(key, name, state)] with state 'ready', 'on' (the loaded file's component) or 'dim'."""
    tiles = "".join(f'<div class="m {state}"><img src="app/static/brand/thumb_{esc(key)}.jpg" alt=""><div class="b"><i></i>'
                    f'<span>{esc(name)}</span></div></div>' for key, name, state in items)
    return (f'<div class="as-ready-note"><span>{note_left}</span><span>{note_right}</span></div>'
            f'<div class="as-ready">{tiles}</div>')
