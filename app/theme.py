"""AeroSentinel design system: tokens, global CSS, Plotly template and HTML primitives.

Visual language: an engineering console. Carbon-inspired Gray-100 dark theme (borrowed
conventions, not the official Carbon package), IBM Plex type, 2px radii, 1px hairlines,
no shadows, glows or gradients. Colour is semantic: one accent for interaction and the
primary data series, status colours only for engine condition.

Presentation only. Every number shown comes from src/ via the pages.
"""

import html
import itertools

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
    "accent": "#78a9ff",      # interaction + primary data series (Carbon blue 40)
    "accent_2": "#3ddbd9",    # secondary data series (Carbon teal 30)
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
  --text-1: #e6e8eb; --text-2: #a6adb6; --text-3: #7f8790; --accent: #78a9ff;
  --s-crit: #fa4d56; --s-warn: #ff832b; --s-degr: #f1c21b; --s-ok: #42be65; --s-none: #8d8d8d;
  --mono: 'IBM Plex Mono', ui-monospace, Consolas, monospace;
  --ease: cubic-bezier(.2, 0, .38, .9);
  --t-fast: 110ms; --t-std: 240ms;
}

/* ---------- frame ---------- */
[data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--bg); }
[data-testid="stHeader"] { background: var(--bg); border-bottom: 1px solid var(--line); }
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
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
[data-testid="stSidebarNavLink"] { border-radius: 2px; margin: 0 4px; padding-top: 4px; padding-bottom: 4px;
  transition: background var(--t-fast) var(--ease); }
[data-testid="stSidebarNavLink"]:hover { background: var(--surface-2); }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: var(--surface-2); box-shadow: inset 2px 0 0 var(--accent); }
[data-testid="stSidebarNavLink"][aria-current="page"] span:not([data-testid="stIconMaterial"]) { color: var(--text-1); font-weight: 500; }
[data-testid="stNavSectionHeader"] { font-size: 11px !important; letter-spacing: .06em; text-transform: uppercase; color: var(--text-3) !important; }
/* Material icons are font ligatures: any font override on them prints the icon name as text. */
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }

/* ---------- controls ---------- */
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button, [data-testid="stPageLink-NavLink"] {
  border-radius: 2px; border: 1px solid var(--line-strong); background: transparent; min-height: 34px;
  transition: background var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease); }
[data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover, [data-testid="stPageLink-NavLink"]:hover {
  background: var(--surface-2); border-color: var(--text-3); }
[data-testid="stButton"] button:active, [data-testid="stDownloadButton"] button:active { transform: translateY(1px); }
[data-testid="stButton"] button[kind="primary"] { background: var(--accent); border-color: var(--accent); }
[data-testid="stButton"] button[kind="primary"] p { color: #0b0d10; font-weight: 600; }
[data-testid="stButton"] button[kind="primary"]:hover { background: #8fb8ff; border-color: #8fb8ff; }
button:focus-visible, a:focus-visible, [role="tab"]:focus-visible { outline: 2px solid var(--accent) !important; outline-offset: 1px; }
[data-testid="stPageLink-NavLink"] { padding: 4px 12px; }
[data-testid="stFileUploaderDropzone"] { background: var(--surface); border: 1px dashed var(--line-strong); border-radius: 2px; }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent); }
[data-testid="stExpander"] details { border: 1px solid var(--line); border-radius: 2px; background: transparent; }
[data-testid="stExpander"] summary:hover { background: var(--surface); }
[data-testid="stTabs"] [data-baseweb="tab-list"] { border-bottom: 1px solid var(--line); gap: 20px; }
[data-testid="stTabs"] [data-baseweb="tab"] { padding: 0 0 10px; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--accent); height: 2px; }
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
  padding-bottom: 14px; margin-bottom: 8px; border-bottom: 1px solid var(--line); }
.as-head h1 { font-size: 20px; font-weight: 600; margin: 0; padding: 0; line-height: 1.3; color: var(--text-1); }
.as-head .ctx { font-size: 13px; color: var(--text-2); margin-top: 4px; max-width: 80ch; }
.as-head .meta { font-family: var(--mono); font-size: 12px; color: var(--text-3); text-align: right; line-height: 1.6; }
.as-head .meta b { color: var(--text-2); font-weight: 500; }

/* ---------- section titles ---------- */
.as-sec { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin: 22px 0 8px; }
.as-sec h2 { font-size: 14px; font-weight: 600; margin: 0; padding: 0; color: var(--text-1); }
.as-sec span { font-size: 12px; color: var(--text-3); }

/* ---------- stat row: hairline-separated readouts, no cards ---------- */
.as-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line); margin: 6px 0 4px; }
.as-stat { padding: 12px 16px 12px 0; }
.as-stat + .as-stat { padding-left: 16px; border-left: 1px solid var(--line); }
.as-stat .l { font-size: 12px; color: var(--text-2); }
.as-stat .v { font-family: var(--mono); font-size: 24px; font-weight: 500; color: var(--text-1); line-height: 1.25; margin-top: 2px;
  font-variant-numeric: tabular-nums; white-space: nowrap; }
.as-stat .v small { font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; color: var(--text-3); font-weight: 400; margin-left: 4px; }
.as-stat .v.t { font-family: 'IBM Plex Sans', sans-serif; font-size: 20px; font-weight: 600; line-height: 1.5; }
.as-stat .f { font-size: 12px; color: var(--text-3); margin-top: 2px; }

/* ---------- status ---------- */
.as-state { --c: var(--s-none); display: inline-flex; align-items: center; gap: 8px; font-weight: 500; color: var(--c); white-space: nowrap; }
.as-state i { width: 8px; height: 8px; background: var(--c); border-radius: 1px; flex: none; }
.as-flag { display: inline-block; font-size: 12px; color: var(--text-2); border: 1px solid var(--line-strong); border-radius: 2px;
  padding: 1px 6px; margin: 2px 6px 2px 0; white-space: nowrap; }

/* condition distribution: one 100% bar instead of five cards */
.as-dist { margin: 8px 0 2px; }
.as-dist .bar { display: flex; height: 10px; gap: 2px; }
.as-dist .bar span { display: block; height: 100%; }
.as-dist .keys { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 16px; margin-top: 10px; }
.as-dist .k { border-top: 2px solid var(--c); padding-top: 6px; }
.as-dist .k .n { font-family: var(--mono); font-size: 22px; color: var(--text-1); line-height: 1.2; }
.as-dist .k .t { font-size: 12px; color: var(--text-2); }

/* ---------- lists ---------- */
.as-kv { display: grid; grid-template-columns: max-content 1fr; column-gap: 24px; row-gap: 6px; font-size: 13px; margin: 4px 0; }
.as-kv dt { color: var(--text-3); }
.as-kv dd { margin: 0; color: var(--text-1); font-variant-numeric: tabular-nums; }
.as-actions { list-style: none; margin: 4px 0; padding: 0; counter-reset: act; }
.as-actions li { position: relative; display: grid; grid-template-columns: 22px 1fr; column-gap: 10px; padding: 10px 0;
  border-top: 1px solid var(--line); }
.as-actions li:first-child { border-top: 0; padding-top: 2px; }
.as-actions li::before { counter-increment: act; content: counter(act); font-family: var(--mono); font-size: 12px; color: var(--text-3);
  padding-top: 2px; }
.as-actions .a { font-size: 14px; color: var(--text-1); font-weight: 500; }
.as-actions .w { font-size: 13px; color: var(--text-2); margin-top: 2px; }
.as-note { font-size: 12px; color: var(--text-3); margin-top: 6px; max-width: 90ch; }
.as-empty { border: 1px dashed var(--line-strong); padding: 20px 22px; margin: 12px 0; max-width: 760px; }
.as-empty h3 { font-size: 15px !important; font-weight: 600; margin: 0 0 6px; padding: 0; }
.as-empty p { font-size: 13px; color: var(--text-2); margin: 0; }

/* processing report */
.as-steps { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.as-steps .st { padding: 12px 12px 12px 0; }
.as-steps .st + .st { padding-left: 12px; border-left: 1px solid var(--line); }
.as-steps .n { font-size: 12px; color: var(--text-2); display: flex; align-items: center; gap: 6px; }
.as-steps .n i { width: 7px; height: 7px; border-radius: 1px; background: var(--c, var(--s-ok)); }
.as-steps .v { font-family: var(--mono); font-size: 14px; color: var(--text-1); margin-top: 4px; }
.as-steps .d { font-size: 12px; color: var(--text-3); }

/* figure frame for the static training-report images (rendered light by matplotlib) */
[data-testid="stImage"] img { border: 1px solid var(--line); border-radius: 2px; }

@media (max-width: 900px) {
  .as-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .as-dist .keys { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  [data-testid="stMainBlockContainer"] { padding: 2rem 1rem 3rem; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition: none !important; animation: none !important; } }
</style>
"""


def inject():
    # A style-only st.html goes to Streamlit's event container, which does not render it, so add an
    # anchor element; the CSS then hides the anchor's own (empty) container.
    st.html(GLOBAL_CSS + '<div class="as-css-anchor"></div>')


# ---------------------------------------------------------------- Plotly
def _register_plotly_template():
    t = TOKENS
    axis = dict(gridcolor=t["line"], gridwidth=1, zeroline=False, linecolor=t["line_strong"], ticks="outside",
                tickcolor=t["line_strong"], ticklen=4, tickfont=dict(family=MONO, size=11, color=t["text_3"]),
                title=dict(font=dict(family=SANS, size=12, color=t["text_2"]), standoff=8), showspikes=False, automargin=True)
    pio.templates["aerosentinel"] = go.layout.Template(layout=dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=SANS, color=t["text_2"], size=12),
        colorway=[t["accent"], t["accent_2"], t["text_2"], "#f1c21b", "#ff832b"],
        xaxis=axis, yaxis=axis,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12, color=t["text_2"]), orientation="h", y=1.02, x=0,
                    yanchor="bottom"),
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["line_strong"], font=dict(family=MONO, size=12, color=t["text_1"])),
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


def page_head(title, context="", meta=""):
    """Title row: page name, one line of context, optional right-aligned metadata (pre-escaped HTML)."""
    st.html(f'<div class="as-head"><div><h1>{esc(title)}</h1>'
            f'{f"<div class=ctx>{context}</div>" if context else ""}</div>'
            f'{f"<div class=meta>{meta}</div>" if meta else ""}</div>')


def section(title, note=""):
    st.html(f'<div class="as-sec"><h2>{esc(title)}</h2>{f"<span>{esc(note)}</span>" if note else ""}</div>')


def stat(label, value, unit="", foot="", color=None):
    """One readout for stats(). Numbers are set in mono, words in sans; color tints the value (status only)."""
    style = f' style="color:{color}"' if color else ""
    is_text = isinstance(value, str) and not any(ch.isdigit() for ch in value)
    return (f'<div class="as-stat"><div class="l">{esc(label)}</div><div class="v{" t" if is_text else ""}"{style}>{esc(value)}'
            f'{f"<small>{esc(unit)}</small>" if unit else ""}</div>{f"<div class=f>{foot}</div>" if foot else ""}</div>')


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


def kv(rows):
    """Definition list from [(label, value_html), ...]."""
    st.html('<dl class="as-kv">' + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>")


def actions(items):
    """Ordered action list from [{'action', 'why'}]."""
    st.html('<ol class="as-actions">' + "".join(
        f'<li><div><div class="a">{esc(a["action"])}</div><div class="w">{esc(a["why"])}</div></div></li>' for a in items)
        + "</ol>")


def note(text):
    st.html(f'<div class="as-note">{text}</div>')


def empty(title, body):
    st.html(f'<div class="as-empty"><h3>{esc(title)}</h3><p>{body}</p></div>')
