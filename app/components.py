"""Reusable UI pieces: session state, pickers, tables and charts. Display only: numbers come from src/."""

import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app import insights
from app.theme import BAND_COLORS, BAND_TEXT, MONO, STATES, TOKENS, esc
from src.config import DATASET, RAW_DATA_DIR, RISK_BANDS, RISK_LIMITS, RUL_CAP
from src.data.loader import read_sensor_file
from src.explainability.sensor_names import SENSOR_INFO, describe
from src.models.artifacts import load_artifacts, model_status
from src.pipeline import analyze

SAMPLE = RAW_DATA_DIR / f"test_{DATASET}.txt"
T = TOKENS
STATE_COLOR = {s: v["color"] for s, v in STATES.items()}
STATE_LABEL = {s: v["label"] for s, v in STATES.items()}
CONDITION_LABELS = {"normal": "Normal", "abnormal": "Abnormal"}
# Band thresholds as (band, upper RUL limit), most severe first.
ZONES = [("FAILURE_LIKELY", 0, RISK_LIMITS["FAILURE_LIKELY"]), ("HIGH_RISK", RISK_LIMITS["FAILURE_LIKELY"], RISK_LIMITS["HIGH_RISK"]),
         ("AT_RISK", RISK_LIMITS["HIGH_RISK"], RISK_LIMITS["AT_RISK"])]


# ---------------------------------------------------------------- state
def get_result():
    return st.session_state.get("result")


def run_analysis(name, content):
    """Analyze uploaded bytes and store the result for every page. Returns the AnalysisResult."""
    result = analyze(read_sensor_file(io.BytesIO(content)))
    st.session_state["last_run"] = result
    if result.status != "FAILED":
        st.session_state["result"] = result
        st.session_state["source_name"] = name
        st.session_state.pop("selected_unit", None)
    return result


def sample_button(key, primary=True):
    """Load the bundled NASA test fleet in one click."""
    if SAMPLE.exists() and st.button("Load NASA sample fleet", type="primary" if primary else "secondary", key=key):
        with st.spinner("Analyzing 100 engines"):
            run_analysis(SAMPLE.name, SAMPLE.read_bytes())
        st.rerun()


def require_result():
    """Stop the page with an empty state if nothing has been analyzed yet."""
    result = get_result()
    if result is None or result.units is None:
        from app.theme import empty
        empty("No engine data loaded",
              "Upload a C-MAPSS sensor file, or load the NASA FD001 test fleet (100 engines) to populate this view.")
        left, right, _ = st.columns([1, 1, 3])
        with left:
            sample_button(key="empty_sample")
        with right:
            st.page_link("views/upload.py", label="Upload a file", icon=":material/upload:")
        st.stop()
    return result


def require_model():
    status = model_status()
    if not status["ready"]:
        st.error(f"Model unavailable. {status['message']}")
        st.stop()
    return load_artifacts()


def fleet(result):
    """Units with condition state, in urgency order (cached per analysis job)."""
    cache = st.session_state.setdefault("_fleet_cache", {})
    if result.job_id not in cache:
        cache.clear()
        cache[result.job_id] = insights.add_states(result.units)
    return cache[result.job_id]


def sidebar_status():
    with st.sidebar:
        status = model_status()
        rows = []
        if status["ready"]:
            m = load_artifacts().metadata["metrics"]
            rows += [("Model", esc(status["version"])), ("Trained", esc(str(status["trained_at"])[:10])),
                     ("Accuracy, unseen engines", f"{m['validation']['risk']['xgboost']['accuracy']:.1%}"),
                     ("Accuracy, NASA test", f"{m['test']['risk']['accuracy']:.1%}"),
                     ("RUL RMSE, NASA test", f"{m['test']['rul']['rmse']:.1f}")]
        else:
            rows.append(("Model", '<span style="color:#fa4d56">unavailable</span>'))
        result = get_result()
        if result is not None and result.units is not None:
            rows += [("Dataset", esc(st.session_state.get("source_name", ""))), ("Engines", str(len(result.units)))]
        body = "".join(f'<div class="r"><span>{k}</span><b>{v}</b></div>' for k, v in rows)
        st.html(f"""<style>.as-sb .r {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; font-size:12px;
  padding:3px 0; }}
.as-sb .r span {{ color:#7f8790; }} .as-sb .r b {{ color:#e6e8eb; font-weight:400; font-family:'IBM Plex Mono',monospace; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; max-width:60%; }}
.as-sb p {{ font-size:12px; color:#7f8790; line-height:1.5; margin:14px 0 0; }}</style>
<div class="as-sb">{body}
<p>Decision support only. Predictions do not certify airworthiness and require review by a qualified engineer.</p></div>""")


# ---------------------------------------------------------------- pickers & tables
def band_label(band):
    return BAND_TEXT.get(band, band)


def unit_label(row):
    state = STATE_LABEL[insights.engine_state(row)]
    rul = f"   RUL {row['predicted_rul']:.0f}" if "predicted_rul" in row else ""
    return f"Engine {int(row['unit']):03d}   {state}{rul}"


def unit_picker(units, key="unit", label="Engine"):
    """Select an engine, most urgent first. The choice is shared across pages."""
    ordered = insights.add_states(units)
    options = ordered["unit"].tolist()
    current = st.session_state.get("selected_unit")
    index = options.index(current) if current in options else 0
    lookup = units.set_index("unit")

    def fmt(u):
        row = lookup.loc[u].copy()
        row["unit"] = u
        return unit_label(row)

    wkey = f"{key}_picker"
    kwargs = {} if st.session_state.get(wkey) in options else {"index": index}
    unit = st.selectbox(label, options, format_func=fmt, key=wkey, **kwargs)
    st.session_state["selected_unit"] = unit
    row = units.loc[units["unit"] == unit].iloc[0]
    return row


TABLE_CONFIG = {
    "Engine": st.column_config.NumberColumn("Engine", format="%03d", width="small"),
    "RUL": st.column_config.NumberColumn("RUL (cycles)", format="%.0f"),
    "Range": st.column_config.TextColumn("80% range"),
    "Confidence": st.column_config.NumberColumn("Band confidence", format="%.0f%%"),
    "Health": st.column_config.NumberColumn("Health score", format="%.2f"),
    "Cycles": st.column_config.NumberColumn("Cycles", format="%d"),
}


def units_table(units, columns=None):
    """Readable unit table with human labels, in the order the caller passes."""
    u = units if "state" in units else units.assign(state=units.apply(insights.engine_state, axis=1))
    table = {"Engine": u["unit"], "State": u["state"].map(STATE_LABEL), "Cycles": u["cycle"]}
    if "predicted_rul" in u:
        table["RUL"] = u["predicted_rul"]
        table["Range"] = [f"{lo:.0f} to {hi:.0f}" for lo, hi in zip(u["rul_low"], u["rul_high"])]
    if "risk_band" in u:
        table["Band"] = u["risk_band"].map(BAND_TEXT)
        table["Confidence"] = u["risk_probability"] * 100
    table["Health"] = u["health_score"]
    table["Condition"] = u["health_condition"].map(CONDITION_LABELS)
    if "rul_factors" in u:
        table["Top driver"] = u["rul_factors"].apply(lambda f: describe(f[0]["sensor"]) if isinstance(f, list) and f else "")
    table["Flags"] = u["review_reasons"].apply(lambda r: ", ".join(x for x in r if x != "high risk"))
    df = pd.DataFrame(table).reset_index(drop=True)
    return df[[c for c in (columns or df.columns) if c in df]]


def _style_states(df):
    color = {v: STATE_COLOR[k] for k, v in STATE_LABEL.items()}
    styler = df.style
    if "State" in df:
        styler = styler.map(lambda v: f"color: {color.get(v, T['text_1'])}; font-weight: 500", subset=["State"])
    return styler


def show_table(units, columns=None, key=None, on_select=None, height="auto"):
    """Unit table. With on_select, a row click returns the selection state."""
    df = units_table(units, columns)
    kwargs = dict(hide_index=True, width="stretch", column_config=TABLE_CONFIG, height=height)
    if on_select:
        kwargs.update(on_select=on_select, selection_mode="single-row", key=key)
    event = st.dataframe(_style_states(df), **kwargs)
    return df, event


def review_box(row):
    reasons = [r for r in row["review_reasons"] if r != "high risk"]
    if reasons:
        st.warning("Needs human review: " + "; ".join(reasons))


# ---------------------------------------------------------------- chart helpers
def _band_zones(fig, row=None, col=None, axis="y"):
    """Faint RUL band zones with direct labels; colour is backed by the label text."""
    # Plotly drops row/col shapes on subplots without traces yet unless told otherwise.
    pos = {"row": row, "col": col, "exclude_empty_subplots": False} if row else {}
    for band, lo, hi in ZONES:
        kw = dict(fillcolor=BAND_COLORS[band], opacity=0.09, line_width=0, layer="below")
        if axis == "y":
            fig.add_hrect(y0=lo, y1=hi, **pos, **kw)
            fig.add_hline(y=hi, line=dict(color=BAND_COLORS[band], width=1, dash="dot"), opacity=0.75, **pos,
                          annotation_text=f"{BAND_TEXT[band]} (RUL {hi} or less)", annotation_position="top left",
                          annotation_font=dict(color=BAND_COLORS[band], size=10))
        else:
            fig.add_vrect(x0=lo, x1=hi, **kw)


def rul_chart(unit_history, row=None, height=360):
    """Predicted RUL per cycle with band zones; the latest cycle carries the 80% range."""
    has_band = "risk_band" in unit_history
    fig = make_subplots(rows=2 if has_band else 1, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.9, 0.1] if has_band else [1])
    _band_zones(fig, row=1, col=1)
    fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history["predicted_rul"], mode="lines", name="Predicted RUL",
                             line=dict(color=T["accent"], width=2),
                             hovertemplate="cycle %{x}<br>RUL %{y:.0f}<extra></extra>"), row=1, col=1)
    if row is not None and "rul_low" in row:
        fig.add_trace(go.Scatter(
            x=[row["cycle"]], y=[row["predicted_rul"]], mode="markers", name="80% range, latest cycle",
            marker=dict(color=T["accent"], size=8, line=dict(color=T["bg"], width=2)),
            error_y=dict(type="data", symmetric=False, array=[row["rul_high"] - row["predicted_rul"]],
                         arrayminus=[row["predicted_rul"] - row["rul_low"]], color=T["accent"], thickness=1.5, width=8),
            hovertemplate="latest cycle %{x}<br>RUL %{y:.0f}<extra></extra>"), row=1, col=1)
    if has_band:
        fig.add_trace(go.Scatter(
            x=unit_history["cycle"], y=[0] * len(unit_history), mode="markers", name="Risk band per cycle",
            marker=dict(symbol="square", size=6, color=[BAND_COLORS[b] for b in unit_history["risk_band"]]),
            customdata=[BAND_TEXT[b] for b in unit_history["risk_band"]], showlegend=False,
            hovertemplate="cycle %{x}<br>%{customdata}<extra></extra>"), row=2, col=1)
        fig.update_yaxes(visible=False, row=2, col=1)
        fig.update_xaxes(title_text="cycle", row=2, col=1)
    else:
        fig.update_xaxes(title_text="cycle")
    fig.update_yaxes(title_text="predicted RUL (cycles)", range=[0, RUL_CAP + 5], row=1, col=1)
    fig.update_layout(height=height, showlegend=True)
    return fig


def health_chart(unit_history, threshold, critical, height=300):
    fig = go.Figure()
    top = max(float(unit_history["health_score"].max()), critical) * 1.15
    fig.add_hline(y=threshold, line=dict(color=STATE_COLOR["DEGRADING"], width=1, dash="dash"),
                  annotation_text=f"abnormal above {threshold:.2f}", annotation_position="top left",
                  annotation_font=dict(color=STATE_COLOR["DEGRADING"]))
    fig.add_hline(y=critical, line=dict(color=STATE_COLOR["CRITICAL"], width=1, dash="dash"),
                  annotation_text=f"critical above {critical:.2f}", annotation_position="top left",
                  annotation_font=dict(color=STATE_COLOR["CRITICAL"]))
    fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history["health_score"], mode="lines", name="Health score",
                             line=dict(color=T["accent_2"], width=2),
                             hovertemplate="cycle %{x}<br>health %{y:.2f}<extra></extra>"))
    fig.update_layout(height=height, showlegend=False, xaxis_title="cycle", yaxis_title="health score (0 = new engine)",
                      yaxis_range=[min(-0.5, float(unit_history["health_score"].min()) - 0.2), top])
    return fig


def sensor_chart(unit_history, sensors):
    """Small multiples, one per sensor: raw reading plus 10-cycle mean."""
    rows = (len(sensors) + 2) // 3
    fig = make_subplots(rows=rows, cols=3, subplot_titles=[describe(s) for s in sensors],
                        vertical_spacing=0.16 / rows, horizontal_spacing=0.06)
    for i, s in enumerate(sensors):
        r, c = i // 3 + 1, i % 3 + 1
        fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history[s], mode="lines", line=dict(color=T["text_3"], width=1),
                                 opacity=0.6, showlegend=False, hoverinfo="skip"), row=r, col=c)
        fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history[s].rolling(10, min_periods=1).mean(), mode="lines",
                                 line=dict(color=T["accent"], width=1.8), showlegend=False,
                                 hovertemplate="cycle %{x}<br>%{y:.2f}<extra>" + s + "</extra>"), row=r, col=c)
    fig.update_annotations(font=dict(size=12, color=T["text_2"]), xanchor="left", x=None)
    for i, a in enumerate(fig.layout.annotations):
        a.x = (i % 3) / 3 + 0.005
    fig.update_layout(height=230 * rows, margin=dict(t=36, b=24, l=48, r=8))
    return fig


def sensor_label(sensor):
    """Short axis label: symbol plus plain-language name, e.g. 'Ps30  HPC static press.'"""
    if sensor == "cycle":
        return "Engine age (cycles)"
    code, name = SENSOR_INFO[sensor][:2]
    return f"{code}  {name}"


def factor_chart(factors, x_title, negative_color, positive_color, height=None):
    """Signed SHAP impact per sensor, largest at the top."""
    names = [sensor_label(f["sensor"]) for f in factors][::-1]
    values = [f["impact"] for f in factors][::-1]
    colors = [negative_color if v < 0 else positive_color for v in values]
    lo, hi = min(0.0, *values), max(0.0, *values)
    pad = (hi - lo) * 0.18 or 1.0  # room for the value labels beyond the bar ends
    fig = go.Figure(go.Bar(x=values, y=names, orientation="h", marker=dict(color=colors), width=0.55,
                           text=[f"{v:+.1f}" for v in values], textposition="outside", cliponaxis=False,
                           textfont=dict(family=MONO, size=11, color=T["text_2"]),
                           hovertemplate="%{y}<br>%{x:+.3f}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=T["line_strong"], width=1))
    fig.update_layout(height=height or 60 + 34 * len(factors), margin=dict(t=8, b=36, l=8, r=16), xaxis_title=x_title,
                      xaxis_range=[lo - (pad if lo < 0 else 0), hi + (pad if hi > 0 else 0)],
                      yaxis=dict(ticks="", tickfont=dict(family="IBM Plex Sans", size=12, color=T["text_2"])))
    return fig


def confusion_chart(matrix):
    labels = [BAND_TEXT[b] for b in RISK_BANDS]
    z = np.asarray(matrix, dtype=float)
    norm = z / np.maximum(z.sum(axis=1, keepdims=True), 1)
    fig = go.Figure(go.Heatmap(
        z=norm, x=labels, y=labels, text=np.asarray(matrix), texttemplate="%{text}", showscale=False,
        textfont=dict(family=MONO, size=13, color=T["text_1"]), xgap=2, ygap=2,
        # capped at a mid blue so white counts keep at least 4.5:1 contrast
        colorscale=[[0, T["surface"]], [0.5, "#24406b"], [1, "#3a6cc2"]], zmin=0, zmax=1,
        hovertemplate="true %{y}<br>predicted %{x}<br>%{text} engines<extra></extra>"))
    fig.update_layout(height=360, xaxis_title="predicted band", yaxis_title="true band", yaxis_autorange="reversed",
                      margin=dict(t=8, b=48, l=96, r=8))
    fig.update_xaxes(showgrid=False, ticks="")
    fig.update_yaxes(showgrid=False, ticks="")
    return fig


def ladder_chart(units, limit=None):
    """Fleet RUL forecast: one row per engine, 80% range as a bar, point estimate as a marker."""
    u = units.head(limit) if limit else units
    labels = [f"{int(x):03d}" for x in u["unit"]]
    fig = go.Figure()
    _band_zones(fig, axis="x")
    for band, lo, hi in ZONES:
        fig.add_annotation(x=(lo + hi) / 2, y=1.0, yref="paper", yanchor="bottom", showarrow=False,
                           text=BAND_TEXT[band], font=dict(color=BAND_COLORS[band], size=10))
    colors = [STATE_COLOR[s] for s in u["state"]]
    fig.add_trace(go.Bar(
        x=u["rul_high"] - u["rul_low"], base=u["rul_low"], y=labels, orientation="h", name="80% range",
        marker=dict(color=colors, opacity=0.28), width=0.6, hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=u["predicted_rul"], y=labels, mode="markers", name="Predicted RUL",
        marker=dict(color=colors, size=8, symbol="diamond", line=dict(color=T["bg"], width=1)),
        customdata=np.stack([u["unit"], u["rul_low"], u["rul_high"], u["state"].map(STATE_LABEL)], axis=1),
        hovertemplate="Engine %{y}<br>RUL %{x:.0f} (80%: %{customdata[1]:.0f} to %{customdata[2]:.0f})"
                      "<br>%{customdata[3]}<extra></extra>"))
    fig.update_layout(height=max(260, 24 * len(u) + 70), barmode="overlay", showlegend=False, bargap=0.4,
                      margin=dict(t=24, b=40, l=44, r=12), hovermode="closest", clickmode="event+select")
    fig.update_xaxes(title_text="remaining useful life (cycles)", range=[0, RUL_CAP + 2], side="bottom")
    fig.update_yaxes(autorange="reversed", type="category", tickfont=dict(family=MONO, size=11), showgrid=False, ticks="")
    return fig


def health_heatmap(units, history, threshold, critical, rows=20, window=60):
    """Health score over the last `window` cycles for the most urgent engines (rows)."""
    top = units.head(rows)["unit"].tolist()
    h = history[history["unit"].isin(top)].copy()
    h["rel"] = h["cycle"] - h.groupby("unit")["cycle"].transform("max")
    h = h[h["rel"] > -window]
    grid = h.pivot_table(index="unit", columns="rel", values="health_score").reindex(top)
    lo, hi = -0.5, max(critical * 1.5, 3.0)
    pos = lambda v: (v - lo) / (hi - lo)  # noqa: E731
    # Large filled areas use muted tones of the status ramp; full-strength colour is for marks and text.
    scale = [[0, T["surface"]], [pos(threshold) - 0.01, "#30353c"], [pos(threshold), "#7d6a1f"],
             [pos(critical), "#9a5426"], [1, "#a8343c"]]
    fig = go.Figure(go.Heatmap(
        z=grid.to_numpy(), x=grid.columns, y=[f"{u:03d}" for u in grid.index], zmin=lo, zmax=hi, colorscale=scale,
        xgap=1, ygap=1, colorbar=dict(title=dict(text="health", side="right", font=dict(size=11)), thickness=8,
                                      outlinewidth=0, tickfont=dict(family=MONO, size=10)),
        hovertemplate="Engine %{y}<br>%{x} cycles from latest<br>health %{z:.2f}<extra></extra>"))
    fig.update_layout(height=max(240, 18 * len(top) + 70), margin=dict(t=8, b=40, l=44, r=8))
    fig.update_xaxes(title_text="cycles before latest reading", showgrid=False)
    fig.update_yaxes(autorange="reversed", type="category", tickfont=dict(family=MONO, size=11), showgrid=False, ticks="")
    return fig


def step_unit(units, key, delta):
    """Callback for previous/next buttons: move the picker along the urgency order."""
    options = insights.add_states(units)["unit"].tolist()
    wkey = f"{key}_picker"
    current = st.session_state.get(wkey, st.session_state.get("selected_unit", options[0]))
    i = options.index(current) if current in options else 0
    st.session_state[wkey] = st.session_state["selected_unit"] = options[(i + delta) % len(options)]


def trend_chart(unit_history, row, threshold, critical, height=430):
    """What is changing: predicted RUL (with band zones) above the health score, on one cycle axis."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.58, 0.42])
    _band_zones(fig, row=1, col=1)
    if "predicted_rul" in unit_history:
        fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history["predicted_rul"], mode="lines", name="Predicted RUL",
                                 line=dict(color=T["accent"], width=2), hovertemplate="cycle %{x}<br>RUL %{y:.0f}<extra></extra>"),
                      row=1, col=1)
    if "rul_low" in row:
        fig.add_trace(go.Scatter(
            x=[row["cycle"]], y=[row["predicted_rul"]], mode="markers", name="80% range, latest cycle",
            marker=dict(color=T["accent"], size=8, line=dict(color=T["bg"], width=2)),
            error_y=dict(type="data", symmetric=False, array=[row["rul_high"] - row["predicted_rul"]],
                         arrayminus=[row["predicted_rul"] - row["rul_low"]], color=T["accent"], thickness=1.5, width=8),
            hovertemplate="latest %{x}<br>RUL %{y:.0f}<extra></extra>"), row=1, col=1)
    fig.add_hline(y=threshold, line=dict(color=STATE_COLOR["DEGRADING"], width=1, dash="dash"), row=2, col=1, exclude_empty_subplots=False,
                  annotation_text="abnormal", annotation_position="top left", annotation_font=dict(color=STATE_COLOR["DEGRADING"]))
    fig.add_hline(y=critical, line=dict(color=STATE_COLOR["CRITICAL"], width=1, dash="dash"), row=2, col=1, exclude_empty_subplots=False,
                  annotation_text="critical", annotation_position="top left", annotation_font=dict(color=STATE_COLOR["CRITICAL"]))
    fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history["health_score"], mode="lines", name="Health score",
                             line=dict(color=T["accent_2"], width=1.6), hovertemplate="cycle %{x}<br>health %{y:.2f}<extra></extra>"),
                  row=2, col=1)
    fig.update_yaxes(title_text="RUL (cycles)", range=[0, RUL_CAP + 5], row=1, col=1)
    fig.update_yaxes(title_text="health score", row=2, col=1,
                     range=[min(-0.5, float(unit_history["health_score"].min()) - 0.2), max(critical * 1.3, float(unit_history["health_score"].max()) * 1.1)])
    fig.update_xaxes(title_text="cycle", row=2, col=1)
    fig.update_layout(height=height, margin=dict(t=30, b=40, l=56, r=12))
    return fig


DRIFT_COLORS = {"Critical": STATE_COLOR["CRITICAL"], "Warning": STATE_COLOR["WARNING"], "Elevated": STATE_COLOR["DEGRADING"],
                "Nominal": T["text_3"]}


def drift_table(drift, rows=None, height="auto", compact=False):
    """Sensor drift ranking with a 60-cycle drift sparkline per sensor. compact drops module and trend."""
    d = drift.head(rows) if rows else drift
    df = pd.DataFrame({"Sensor": d["code"], "Measures": d["name"], "Module": d["module"], "Drift": d["drift"],
                       "Trend": d["trend"], "Status": d["status"], "Last 60 cycles": d["history"]})
    if compact:
        df = df.drop(columns=["Module", "Trend"])
    styler = df.style.map(lambda v: f"color: {DRIFT_COLORS.get(v, T['text_1'])}", subset=["Status"])
    st.dataframe(styler, hide_index=True, width="stretch", height=height, column_config={
        "Drift": st.column_config.NumberColumn("Drift (sigma)", format="%+.1f",
                                               help="Directed z-score against the healthy baseline; positive means degrading"),
        "Trend": st.column_config.NumberColumn("Trend", format="%+.2f", help="Change in drift per 10 cycles, last 20 cycles"),
        "Last 60 cycles": st.column_config.LineChartColumn("Last 60 cycles", y_min=-2, y_max=6, width="medium"),
    })
