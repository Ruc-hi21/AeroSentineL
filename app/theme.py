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
  --text-1: #e6e8eb; --text-2: #a6adb6; --text-3: #7f8790; --accent: #3fa2ff;
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
.as-head h1 { font-size: 20px; font-weight: 600; margin: 0; padding: 0; line-height: 1.3; color: var(--text-1); }
.as-head .ctx { font-size: 13px; color: var(--text-2); margin-top: 4px; max-width: 80ch; }
.as-head .meta { font-family: var(--mono); font-size: 12px; color: var(--text-3); text-align: right; line-height: 1.6; }
.as-head .meta b { color: var(--text-2); font-weight: 500; }

/* ---------- section titles ---------- */
.as-sec { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin: 22px 0 8px; }
.as-sec h2 { font-size: 14px; font-weight: 600; margin: 0; padding: 0; color: var(--text-1); display: flex; align-items: center; gap: 8px; }
.as-sec h2::before { content: ""; width: 3px; height: 12px; border-radius: 1px; background: linear-gradient(180deg, #5fd4f8, #1683f2); flex: none; }
.as-sec span { font-size: 12px; color: var(--text-3); }

/* ---------- stat row: hairline-separated readouts, no cards ---------- */
.as-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line); margin: 6px 0 4px; }
.as-stat { padding: 12px 16px 12px 0; position: relative; transition: background var(--t-std) var(--ease); }
.as-stat::after { content: ""; position: absolute; left: 0; right: 0; bottom: -1px; height: 1px; background: var(--accent);
  transform: scaleX(0); transform-origin: left; transition: transform var(--t-std) var(--ease-out); }
.as-stat:hover { background: linear-gradient(180deg, rgba(63, 162, 255, .06), transparent); }
.as-stat:hover::after { transform: scaleX(1); }
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
.as-actions { list-style: none; margin: 4px 0; padding: 0; counter-reset: act; }
.as-actions li { position: relative; display: grid; grid-template-columns: 22px 1fr; column-gap: 10px; padding: 10px 0;
  border-top: 1px solid var(--line); }
.as-actions li:first-child { border-top: 0; padding-top: 2px; }
.as-actions li::before { counter-increment: act; content: counter(act); font-family: var(--mono); font-size: 12px; color: var(--text-3);
  padding-top: 2px; }
.as-actions .a { font-size: 14px; color: var(--text-1); font-weight: 500; }
.as-actions .w { font-size: 13px; color: var(--text-2); margin-top: 2px; }
.as-note { font-size: 12px; color: var(--text-3); margin-top: 6px; max-width: 90ch; }
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

/* landing hero */
.as-hero .eyebrow { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.as-hero .eyebrow img { width: 46px; height: 46px; animation: as-spin-in .9s var(--ease-out) both, as-float 6s var(--ease) 1s infinite; }
.as-hero .eyebrow b { display: block; font-size: 13px; font-weight: 600; letter-spacing: .14em; color: var(--text-1); }
.as-hero .eyebrow i { display: block; font-style: normal; font-size: 12px; color: var(--brand-cyan); letter-spacing: .04em; margin-top: 2px; }
.as-hero h1 { font-size: 32px; font-weight: 600; margin: 0 0 12px; padding: 0; line-height: 1.16; letter-spacing: -.01em; }
.as-hero h1 span { background: linear-gradient(90deg, #3fa2ff, #5fd4f8); -webkit-background-clip: text; background-clip: text; color: transparent; }
.as-hero p { font-size: 15px; color: var(--text-2); margin: 0; line-height: 1.55; max-width: 60ch; }

@media (max-width: 900px) {
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
  const REVEAL = '.as-head, .as-hero, .as-sec, .as-stats, .as-dist, .as-spec, .as-steps, .as-kv, .as-actions, .as-empty, .as-note, '
    + '[data-testid="stPlotlyChart"], [data-testid="stDataFrame"], [data-testid="stCustomComponentV1"], [data-testid="stImage"]';
  const COUNT = '.as-stat .v, .as-dist .k .n, .as-steps .v';
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
    const lab = el.parentElement && el.parentElement.querySelector('.l, .t');
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


def spec(items):
    """Spec strip from [(label, value), ...]: compact engineering facts in one bordered row."""
    st.html('<div class="as-spec">' + "".join(f"<div><i>{esc(k)}</i><b>{esc(v)}</b></div>" for k, v in items) + "</div>")


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
