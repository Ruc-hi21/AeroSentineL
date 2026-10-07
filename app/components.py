"""Reusable UI pieces. Display only: every number shown comes from src/."""

import io

import plotly.graph_objects as go
import streamlit as st

from app.theme import BAND_COLORS, BAND_TEXT, CYAN, MUTED, PINK, VIOLET, band_pill, esc
from src.config import DATASET, RAW_DATA_DIR, RISK_BANDS, RISK_LIMITS
from src.data.loader import read_sensor_file
from src.explainability.sensor_names import describe
from src.models.artifacts import load_artifacts, model_status
from src.pipeline import analyze

SAMPLE = RAW_DATA_DIR / f"test_{DATASET}.txt"

# Colour is always paired with an icon and a text label (never colour alone).
BAND_LABELS = {
    "NORMAL": "🟢 Normal",
    "AT_RISK": "🟡 At risk",
    "HIGH_RISK": "🟠 High risk",
    "FAILURE_LIKELY": "🔴 Failure likely",
}
CONDITION_LABELS = {"normal": "🟢 Normal", "abnormal": "🔴 Abnormal"}


# ---------- state ----------

def get_result():
    return st.session_state.get("result")


def run_analysis(name, content):
    """Analyze uploaded bytes and store the result for every page. Returns the AnalysisResult."""
    result = analyze(read_sensor_file(io.BytesIO(content)))
    st.session_state["last_run"] = result
    if result.status != "FAILED":
        st.session_state["result"] = result
        st.session_state["source_name"] = name
        st.session_state["fresh_run"] = True
        st.session_state.pop("selected_unit", None)
    return result


def launch_sample_button(key):
    """One click from an empty page to a fully analysed fleet."""
    if SAMPLE.exists() and st.button("🚀  Launch with NASA FD001 sample (100 engines)", type="primary", key=key):
        with st.spinner("Spinning up the fleet…"):
            run_analysis(SAMPLE.name, SAMPLE.read_bytes())
        st.rerun()


def require_result():
    """Stop the page with an empty state (upload or launch sample) if nothing was analyzed yet."""
    result = get_result()
    if result is None or result.units is None:
        st.html('<div class="as-card"><h4>No telemetry linked</h4><p>Upload a C-MAPSS sensor file, or launch the NASA '
                'sample fleet to bring this view online.</p></div>')
        left, right = st.columns([1, 1])
        with left:
            launch_sample_button(key="empty_launch")
        with right:
            st.page_link("views/upload.py", label="Upload your own dataset", icon=":material/upload_file:")
        st.stop()
    return result


def require_model():
    status = model_status()
    if not status["ready"]:
        st.error(f"**Model unavailable.** {status['message']}")
        st.stop()
    return load_artifacts()


def sidebar_status():
    with st.sidebar:
        status = model_status()
        if status["ready"]:
            meta = load_artifacts().metadata
            m = meta["metrics"]
            val_acc, test_acc = m["validation"]["risk"]["xgboost"]["accuracy"], m["test"]["risk"]["accuracy"]
            model_html = (f'<div class="as-pill" style="--c:#19f5a0"><i></i>MODEL {esc(status["version"]).upper()} ONLINE</div>'
                          f'<div class="as-sb-row"><span>Accuracy · unseen engines</span><b>{val_acc:.1%}</b></div>'
                          f'<div class="as-sb-row"><span>Accuracy · NASA test</span><b>{test_acc:.1%}</b></div>'
                          f'<div class="as-sb-row"><span>RUL RMSE · test</span><b>{m["test"]["rul"]["rmse"]:.1f} cyc</b></div>')
        else:
            model_html = '<div class="as-pill" style="--c:#ff2e4d"><i></i>MODEL OFFLINE</div>'
        result = get_result()
        if result is not None and result.units is not None:
            severe = int(result.units["risk_band"].isin(["HIGH_RISK", "FAILURE_LIKELY"]).sum()) if "risk_band" in result.units else 0
            data_html = (f'<div class="as-sb-row"><span>Dataset</span><b>{esc(st.session_state.get("source_name", ""))}</b></div>'
                         f'<div class="as-sb-row"><span>Engines</span><b>{len(result.units)}</b></div>'
                         f'<div class="as-sb-row"><span>Severe</span><b style="color:#ff8a1f">{severe}</b></div>')
        else:
            data_html = '<div class="as-sb-row"><span>Telemetry</span><b style="color:#7f95bd">not linked</b></div>'
        st.html(f"""<style>
.as-sb {{ padding: 12px 14px; border-radius: 14px; background: linear-gradient(145deg, rgba(14,30,64,.7), rgba(6,14,32,.6));
  border: 1px solid rgba(0,229,255,.16); margin: 4px 0 10px; }}
.as-sb-row {{ display: flex; justify-content: space-between; gap: 8px; font-family: 'Rajdhani', sans-serif; font-size: .9rem; margin-top: 6px; }}
.as-sb-row span {{ color: #7f95bd; letter-spacing: .06em; }} .as-sb-row b {{ color: #fff; font-family: 'JetBrains Mono', monospace; font-size: .8rem;
  max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.as-sb-foot {{ font-family: 'Exo 2', sans-serif; font-size: .72rem; color: #7f95bd; line-height: 1.45; margin-top: 8px; }}
</style><div class="as-sb">{model_html}{data_html}</div>
<div class="as-sb-foot">Decision support only. Predictions do not certify airworthiness and must be reviewed by a
maintenance professional before any action.</div>""")


# ---------- small widgets ----------

def band_label(band):
    return BAND_LABELS.get(band, band)


def unit_picker(units, key="unit", label="Engine unit (most at risk first)"):
    """Select a unit, most at-risk first. The choice is shared across pages."""
    order = units
    if "risk_band" in units:
        rul = units["predicted_rul"] if "predicted_rul" in units else 0
        order = units.assign(_sev=units["risk_band"].map(RISK_BANDS.index), _rul=rul)
        order = order.sort_values(["_sev", "_rul"], ascending=[False, True])
    options = order["unit"].tolist()
    current = st.session_state.get("selected_unit")
    index = options.index(current) if current in options else 0

    def fmt(u):
        row = units.loc[units["unit"] == u].iloc[0]
        rul = f" · RUL {row['predicted_rul']:.0f}" if "predicted_rul" in row else ""
        return f"Unit {u:03d} — {band_label(row['risk_band'])}{rul}" if "risk_band" in row else f"Unit {u:03d}"

    unit = st.selectbox(label, options, index=index, format_func=fmt, key=f"{key}_picker")
    st.session_state["selected_unit"] = unit
    return units.loc[units["unit"] == unit].iloc[0]


TABLE_CONFIG = {
    "unit": st.column_config.NumberColumn("unit", format="%03d"),
    "predicted_rul": st.column_config.ProgressColumn("predicted RUL", min_value=0, max_value=125, format="%.0f cyc"),
    "rul_low": st.column_config.NumberColumn("RUL low", format="%.0f"),
    "rul_high": st.column_config.NumberColumn("RUL high", format="%.0f"),
    "risk_probability": st.column_config.ProgressColumn("confidence", min_value=0, max_value=1, format="percent"),
    "health_score": st.column_config.NumberColumn("health score", format="%.2f"),
}


def units_table(units, columns):
    """Readable unit table: label columns added, only the requested columns that exist."""
    table = units.copy()
    if "risk_band" in table:
        table["risk"] = table["risk_band"].map(band_label)
    table["health"] = table["health_condition"].map(CONDITION_LABELS)
    table["review"] = table["review_reasons"].apply(lambda r: "; ".join(r) or "—")
    return table[[c for c in columns if c in table]]


def show_table(units, columns, **kwargs):
    st.dataframe(units_table(units, columns), hide_index=True, width="stretch", column_config=TABLE_CONFIG, **kwargs)


def review_box(row):
    reasons = row["review_reasons"]
    if reasons:
        st.warning("**Needs human review:** " + "; ".join(reasons), icon="👀")
    else:
        st.success("No review flags for this unit.", icon="✔️")


def unit_banner(row):
    """Headline strip for one unit: band pill, RUL and health in big type."""
    band = row.get("risk_band")
    pill = band_pill(band, f" · {row['risk_probability']:.0%}") if isinstance(band, str) else ""
    rul = f"{row['predicted_rul']:.0f}" if "predicted_rul" in row else "—"
    rng = f"{row['rul_low']:.0f}–{row['rul_high']:.0f}" if "rul_low" in row else "—"
    color = BAND_COLORS.get(band, CYAN)
    st.html(f"""<div class="as-card" style="display:flex;flex-wrap:wrap;align-items:center;gap:28px;border-color:{color}55;
box-shadow:0 0 30px {color}22">
<div><div class="as-kpi-label">Engine unit</div><div style="font-family:Orbitron;font-size:2.1rem;font-weight:900;color:#fff">{int(row['unit']):03d}</div></div>
<div><div class="as-kpi-label">Predicted RUL</div><div style="font-family:Orbitron;font-size:2.1rem;font-weight:900;color:{color};
text-shadow:0 0 18px {color}">{rul}<small style="font-size:.9rem;color:#7f95bd"> cycles</small></div></div>
<div><div class="as-kpi-label">80% range</div><div class="as-mono" style="font-size:1.1rem;color:#fff">{rng}</div></div>
<div><div class="as-kpi-label">Health score</div><div class="as-mono" style="font-size:1.1rem;color:#fff">{row['health_score']:.2f}</div></div>
<div><div class="as-kpi-label">Cycles observed</div><div class="as-mono" style="font-size:1.1rem;color:#fff">{int(row['cycle'])}</div></div>
<div style="margin-left:auto">{pill}</div></div>""")


# ---------- charts ----------

def _glow_line(fig, x, y, color, name, width=2.5, fill=False):
    """Line with a soft neon halo (a wide transparent copy underneath)."""
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=width * 4), opacity=0.12,
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name, line=dict(color=color, width=width),
                             fill="tozeroy" if fill else None, fillcolor="rgba(0,229,255,0.07)" if fill else None))


def band_count_chart(units):
    counts = units["risk_band"].value_counts().reindex(RISK_BANDS, fill_value=0)
    fig = go.Figure(go.Pie(
        labels=[BAND_TEXT[b] for b in RISK_BANDS], values=counts.values, hole=0.68, sort=False,
        marker=dict(colors=[BAND_COLORS[b] for b in RISK_BANDS], line=dict(color="#040a18", width=3)),
        textinfo="value", textfont=dict(family="Orbitron", size=13, color="#fff"),
        hovertemplate="%{label}: %{value} units<extra></extra>",
    ))
    fig.add_annotation(text=f"<b>{len(units)}</b><br><span style='font-size:11px;color:{MUTED}'>ENGINES</span>",
                       showarrow=False, font=dict(family="Orbitron", size=26, color="#fff"))
    fig.update_layout(height=320, showlegend=True, legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"),
                      margin=dict(t=10, b=10, l=10, r=10))
    return fig


def health_chart(unit_history, threshold, critical):
    fig = go.Figure()
    top = max(unit_history["health_score"].max(), critical) * 1.15
    fig.add_hrect(y0=threshold, y1=critical, fillcolor="#ff8a1f", opacity=0.06, line_width=0)
    fig.add_hrect(y0=critical, y1=top, fillcolor="#ff2e4d", opacity=0.08, line_width=0)
    _glow_line(fig, unit_history["cycle"], unit_history["health_score"], PINK, "health score")
    fig.add_hline(y=threshold, line_dash="dash", line_color="#ff8a1f", annotation_text="abnormal",
                  annotation_font_color="#ff8a1f")
    fig.add_hline(y=critical, line_dash="dot", line_color="#ff2e4d", annotation_text="critical",
                  annotation_font_color="#ff2e4d")
    fig.update_layout(height=340, showlegend=False, xaxis_title="cycle", yaxis_title="health score (0 = like new)",
                      yaxis_range=[min(0, unit_history["health_score"].min() - 0.2), top])
    return fig


def rul_chart(unit_history):
    fig = go.Figure()
    for band, limit in RISK_LIMITS.items():
        fig.add_hline(y=limit, line_dash="dot", line_color=BAND_COLORS[band], annotation_text=BAND_TEXT[band],
                      annotation_position="top left", annotation_font_color=BAND_COLORS[band])
    _glow_line(fig, unit_history["cycle"], unit_history["predicted_rul"], CYAN, "predicted RUL", fill=True)
    if "risk_band" in unit_history:
        fig.add_trace(go.Scatter(
            x=unit_history["cycle"], y=[-4] * len(unit_history), mode="markers", hoverinfo="skip", showlegend=False,
            marker=dict(symbol="square", size=7, color=[BAND_COLORS[b] for b in unit_history["risk_band"]]),
        ))
    fig.update_layout(height=360, showlegend=False, xaxis_title="cycle", yaxis_title="predicted RUL (cycles)",
                      yaxis_range=[-8, 132])
    return fig


def sensor_chart(unit_history, sensors):
    from plotly.subplots import make_subplots

    rows = (len(sensors) + 2) // 3
    fig = make_subplots(rows=rows, cols=3, subplot_titles=[describe(s) for s in sensors],
                        vertical_spacing=0.12 / max(1, rows - 1) if rows > 1 else 0.1, horizontal_spacing=0.06)
    colors = [CYAN, VIOLET, PINK, "#19f5a0", "#ffd23f", "#3d8bff"]
    for i, s in enumerate(sensors):
        r, c = i // 3 + 1, i % 3 + 1
        color = colors[i % len(colors)]
        fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history[s], mode="lines", line=dict(color=color, width=1),
                                 opacity=0.35, showlegend=False, hoverinfo="skip"), row=r, col=c)
        fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history[s].rolling(10, min_periods=1).mean(),
                                 mode="lines", line=dict(color=color, width=2.5), name=s, showlegend=False), row=r, col=c)
    fig.update_annotations(font=dict(family="Rajdhani", size=13, color=MUTED))
    fig.update_layout(height=250 * rows, margin=dict(t=40, b=10, l=10, r=10))
    return fig


def factor_chart(factors, x_title, negative_color, positive_color):
    """Signed SHAP impact per sensor, largest at the top."""
    names = [describe(f["sensor"]) for f in factors][::-1]
    values = [f["impact"] for f in factors][::-1]
    colors = [negative_color if v < 0 else positive_color for v in values]
    fig = go.Figure(go.Bar(x=values, y=names, orientation="h", marker=dict(color=colors, line=dict(color=colors, width=1)),
                           text=[f"{v:+.2f}" for v in values], textposition="outside",
                           textfont=dict(family="JetBrains Mono", size=11)))
    fig.update_layout(height=70 + 48 * len(factors), margin=dict(t=10, b=10, l=10, r=40), xaxis_title=x_title)
    return fig


def confusion_chart(matrix):
    labels = [BAND_TEXT[b] for b in RISK_BANDS]
    fig = go.Figure(go.Heatmap(
        z=matrix, x=labels, y=labels, text=matrix, texttemplate="%{text}", showscale=False,
        textfont=dict(family="Orbitron", size=14, color="#fff"),
        colorscale=[[0, "rgba(4,12,30,0.6)"], [0.15, "#0b3a6e"], [0.5, "#0077b6"], [1, CYAN]],
        hovertemplate="true %{y} → predicted %{x}: %{z}<extra></extra>",
    ))
    fig.update_layout(height=420, xaxis_title="predicted", yaxis_title="true", yaxis_autorange="reversed")
    return fig
