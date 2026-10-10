"""Reusable UI pieces: session state, pickers, tables and charts. Display only: numbers come from src/."""

import io
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app import insights
from app.theme import BAND_COLORS, BAND_TEXT, MONO, STATES, TOKENS, esc
from src.components import COMPONENTS, PROFILES, get, spec_of_profile
from src.config import DATASET, MODEL_VERSION, RAW_DATA_DIR, REPORTS_DIR, RISK_BANDS, SUBSETS
from src.data.loader import read_sensor_file
from src.explainability.sensor_names import SENSOR_INFO, describe
from src.models.artifacts import available_subsets, load_artifacts, model_status
from src.pipeline import analyze

# Sample fleets: NASA C-MAPSS test fleets, the battery cells the model never saw, the held-out bearings.
SAMPLES = {**{s: RAW_DATA_DIR / f"test_{s}.txt" for s in SUBSETS},
           "PCOE": RAW_DATA_DIR / "sample_PCOE.csv", "FEMTO": RAW_DATA_DIR / "test_FEMTO.csv"}
SAMPLE = SAMPLES[DATASET]
PROFILE_LABELS = {**{s: s for s in SUBSETS}, "PCOE": "Battery cells", "FEMTO": "Bearings"}
FAULT_TEXT = {"HPC": "HPC degradation", "Fan": "fan degradation", "capacity fade": "capacity fade",
              "rolling contact wear": "rolling contact wear"}
# Operating-envelope axes per component: (x setting, y setting, label setting or None).
ENVELOPE = {"turbofan": ("setting_2", "setting_1", "setting_3"), "battery": ("load_a", "ambient_c", None),
            "bearing": ("speed_rpm", "load_kn", None)}
T = TOKENS
STATE_COLOR = {s: v["color"] for s, v in STATES.items()}
STATE_LABEL = {s: v["label"] for s, v in STATES.items()}
CONDITION_LABELS = {"normal": "Normal", "abnormal": "Abnormal"}


def zones(spec):
    """Band thresholds as (band, lower, upper RUL limit), most severe first, in the component's life units."""
    lim = spec.risk_limits
    return [("FAILURE_LIKELY", 0, lim["FAILURE_LIKELY"]), ("HIGH_RISK", lim["FAILURE_LIKELY"], lim["HIGH_RISK"]),
            ("AT_RISK", lim["HIGH_RISK"], lim["AT_RISK"])]


ZONES = zones(get("turbofan"))


# ---------------------------------------------------------------- state
def get_result():
    return st.session_state.get("result")


def run_analysis(name, content, subset=None, component=None):
    """Analyze uploaded bytes and store the result for every page. None = the recognition model decides."""
    result = analyze(read_sensor_file(io.BytesIO(content)), subset=subset, name=name, component=component)
    st.session_state["last_run"] = result
    if result.status != "FAILED":
        st.session_state["result"] = result
        st.session_state["source_name"] = name
        st.session_state.pop("selected_unit", None)
    return result


def subset_summary(subset):
    """'6 operating conditions, HPC and fan degradation' style description of a profile."""
    spec = spec_of_profile(subset)
    if spec.key != "turbofan":
        return spec.profiles[subset].description
    info = SUBSETS[subset]
    conditions = "1 operating condition" if info["conditions"] == 1 else f"{info['conditions']} operating conditions"
    return f"{conditions}, {' and '.join(FAULT_TEXT[f] for f in info['fault_modes'])}"


def sample_choice(key, label="Sample fleet"):
    """Pick a bundled fleet: the four NASA C-MAPSS test fleets, battery cells or bearings."""
    options = [s for s in available_subsets() if SAMPLES.get(s) and SAMPLES[s].exists()] or [DATASET]
    choice = st.segmented_control(label, options, default=options[0], key=key, format_func=PROFILE_LABELS.get,
                                  help="Turbofan: FD001 and FD003 run at one operating condition, FD002 and FD004 at six; "
                                       "FD003 and FD004 add fan degradation. Battery cells: NASA PCoE cells the model never "
                                       "saw. Bearings: held-out FEMTO run-to-failure bearings.")
    return choice or options[0]


def sample_button(key, primary=True, subset=None):
    """Load a bundled sample fleet in one click."""
    subset = subset or DATASET
    path = SAMPLES[subset]
    spec = spec_of_profile(subset)
    label = "Load NASA sample fleet" if subset == DATASET else f"Load {PROFILE_LABELS[subset].lower()} fleet"
    if path.exists() and st.button(label, type="primary" if primary else "secondary", key=key):
        with st.spinner(f"Analyzing the {PROFILE_LABELS[subset]} sample fleet ({spec.unit_plural})"):
            run_analysis(path.name, path.read_bytes(), subset=subset)
        st.rerun()


def require_result():
    """Stop the page with an empty state if nothing has been analyzed yet."""
    result = get_result()
    if result is None or result.units is None:
        from app.theme import empty
        empty("No data loaded",
              "Upload turbofan, battery or bearing data, or load one of the sample fleets to populate this view.")
        left, right, _ = st.columns([1, 1, 3])
        with left:
            sample_button(key="empty_sample")
        with right:
            st.page_link("views/upload.py", label="Upload a file", icon=":material/upload:")
        st.stop()
    return result


def load_benchmark():
    """reports/benchmark.json written by training (every model on every subset), or None."""
    path = REPORTS_DIR / "benchmark.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def profile_spec(result):
    """Spec-strip facts for the loaded file: component, model, conditions, fault modes, size."""
    prof = result.profile or {}
    subset = result.subset or DATASET
    spec = spec_of_profile(subset)
    seen = prof.get("conditions_seen", 1)
    faults = prof.get("fault_modes") or list(spec.profiles[subset].fault_modes)
    return [("Component", spec.name), ("Model", f"{result.model_version} {subset}"),
            ("Operating conditions", f"{seen}" + (", corrected" if prof.get("corrected") else "")),
            ("Degradation", " and ".join(FAULT_TEXT.get(f, f) for f in faults)),
            (spec.unit_plural.capitalize(), f"{len(result.units)}"),
            (f"{spec.time_title}s", f"{len(result.history):,}"), ("Processing", f"{result.duration_ms:,.0f} ms")]


def active_subset():
    """The profile whose model scored the loaded data (the default subset before any analysis)."""
    result = get_result()
    return getattr(result, "subset", None) or DATASET


def active_spec():
    """The component spec of the loaded data (the turbofan before any analysis)."""
    return spec_of_profile(active_subset())


def require_model(subset=None):
    subset = subset or active_subset()
    status = model_status(MODEL_VERSION, subset)
    if not status["ready"]:
        st.error(f"Model unavailable. {status['message']}")
        st.stop()
    return load_artifacts(MODEL_VERSION, subset)


def fleet(result):
    """Units with condition state, in urgency order (cached per analysis job)."""
    cache = st.session_state.setdefault("_fleet_cache", {})
    if result.job_id not in cache:
        cache.clear()
        cache[result.job_id] = insights.add_states(result.units)
    return cache[result.job_id]


def sidebar_status():
    with st.sidebar:
        subset = active_subset()
        status = model_status(MODEL_VERSION, subset)
        rows = []
        if status["ready"]:
            meta = load_artifacts(MODEL_VERSION, subset).metadata
            m = meta["metrics"]
            conditions = len(meta.get("conditions") or [1])
            rows += [("Component", esc(spec_of_profile(subset).unit_title)),
                     ("Model", f"{esc(status['version'])} {esc(subset)}"),
                     ("Conditions", "1" if conditions == 1 else f"{conditions}, corrected"),
                     ("Trained", esc(str(status["trained_at"])[:10])),
                     (f"Accuracy, unseen {spec_of_profile(subset).unit_plural}", f"{m['validation']['risk']['xgboost']['accuracy']:.1%}"),
                     ("Accuracy, test set", f"{m['test']['risk']['accuracy']:.1%}"),
                     ("RUL RMSE, test, capped", f"{m['test']['rul'].get('rmse_capped', m['test']['rul']['rmse']):.1f}")]
        else:
            rows.append(("Model", '<span style="color:#fa4d56">unavailable</span>'))
        result = get_result()
        if result is not None and result.units is not None:
            rows += [("Dataset", esc(st.session_state.get("source_name", ""))),
                     (result.spec.unit_plural.capitalize(), str(len(result.units)))]
        body = "".join(f'<div class="r"><span>{k}</span><b>{v}</b></div>' for k, v in rows)
        st.html(f"""<style>.as-sb .r {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; font-size:12px;
  padding:3px 0; }}
.as-sb .r span {{ color:#7f8790; }} .as-sb .r b {{ color:#e6e8eb; font-weight:400; font-family:'IBM Plex Mono',monospace; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; max-width:60%; }}
.as-sb p {{ font-size:12px; color:#7f8790; line-height:1.5; margin:14px 0 0; }}</style>
<div class="as-sb">{body}
<p>Decision support only. Predictions do not certify {'airworthiness' if subset in ('FD001', 'FD002', 'FD003', 'FD004') else 'fitness for service'} and require review by a qualified engineer.</p></div>""")


# ---------------------------------------------------------------- pickers & tables
def band_label(band):
    return BAND_TEXT.get(band, band)


def unit_label(row):
    spec = insights.spec_of(row)
    state = STATE_LABEL[insights.engine_state(row)]
    rul = f"   RUL {row['predicted_rul']:.0f}" if "predicted_rul" in row else ""
    return f"{spec.label(row['unit'])}   {state}{rul}"


def unit_picker(units, key="unit", label=None):
    """Select an engine, most urgent first. The choice is shared across pages."""
    label = label or insights.spec_of(units).unit_title
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
    "Engine": st.column_config.TextColumn("Engine", width="small"),
    "RUL": st.column_config.NumberColumn("RUL (cycles)", format="%.0f"),
    "Range": st.column_config.TextColumn("80% range"),
    "Confidence": st.column_config.NumberColumn("Band confidence", format="%.0f%%"),
    "Health": st.column_config.NumberColumn("Health score", format="%.2f"),
    "Cycles": st.column_config.NumberColumn("Cycles", format="%d"),
}


def units_table(units, columns=None):
    """Readable unit table with human labels, in the order the caller passes."""
    u = units if "state" in units else units.assign(state=units.apply(insights.engine_state, axis=1))
    spec = insights.spec_of(u)
    table = {"_unit": u["unit"], "Engine": u["unit"].map(spec.unit_id), "State": u["state"].map(STATE_LABEL),
             "Cycles": u["cycle"]}
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
    keep = [c for c in (columns or df.columns) if c in df and c != "_unit"]
    return df[["_unit", *keep]]


def _style_states(df):
    color = {v: STATE_COLOR[k] for k, v in STATE_LABEL.items()}
    styler = df.style
    if "State" in df:
        styler = styler.map(lambda v: f"color: {color.get(v, T['text_1'])}; font-weight: 500", subset=["State"])
    return styler


def table_config(spec):
    """Column labels in the component's words: 'Cell', 'RUL (minutes)', 'Minutes'."""
    return {**TABLE_CONFIG,
            "Engine": st.column_config.TextColumn(spec.unit_title, width="small"),
            "RUL": st.column_config.NumberColumn(f"RUL ({spec.life_unit})", format="%.0f"),
            "Cycles": st.column_config.NumberColumn(f"{spec.time_title}s", format="%d")}


def show_table(units, columns=None, key=None, on_select=None, height="auto"):
    """Unit table. With on_select, a row click returns the selection state; df['_unit'] is the unit id."""
    df = units_table(units, columns)
    kwargs = dict(hide_index=True, width="stretch", column_config=table_config(insights.spec_of(units)), height=height,
                  column_order=[c for c in df.columns if c != "_unit"])
    if on_select:
        kwargs.update(on_select=on_select, selection_mode="single-row", key=key)
    event = st.dataframe(_style_states(df), **kwargs)
    return df, event


def review_box(row):
    reasons = [r for r in row["review_reasons"] if r != "high risk"]
    if reasons:
        st.warning("Needs human review: " + "; ".join(reasons))


# ---------------------------------------------------------------- chart helpers
def _band_zones(fig, row=None, col=None, axis="y", spec=None):
    """Faint RUL band zones with direct labels; colour is backed by the label text."""
    # Plotly drops row/col shapes on subplots without traces yet unless told otherwise.
    pos = {"row": row, "col": col, "exclude_empty_subplots": False} if row else {}
    for band, lo, hi in zones(spec or get("turbofan")):
        kw = dict(fillcolor=BAND_COLORS[band], opacity=0.09, line_width=0, layer="below")
        if axis == "y":
            fig.add_hrect(y0=lo, y1=hi, **pos, **kw)
            fig.add_hline(y=hi, line=dict(color=BAND_COLORS[band], width=1, dash="dot"), opacity=0.75, **pos,
                          annotation_text=f"{BAND_TEXT[band]} (RUL {hi} or less)", annotation_position="top left",
                          annotation_font=dict(color=BAND_COLORS[band], size=10))
        else:
            fig.add_vrect(x0=lo, x1=hi, **kw)


def rul_chart(unit_history, row=None, height=360, spec=None):
    """Predicted RUL per cycle with band zones; the latest cycle carries the 80% range."""
    spec = spec or (insights.spec_of(row) if row is not None else get("turbofan"))
    has_band = "risk_band" in unit_history
    fig = make_subplots(rows=2 if has_band else 1, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.9, 0.1] if has_band else [1])
    _band_zones(fig, row=1, col=1, spec=spec)
    fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history["predicted_rul"], mode="lines", name="Predicted RUL",
                             line=dict(color=T["accent"], width=2),
                             hovertemplate="cycle %{x}<br>RUL %{y:.0f}<extra></extra>"), row=1, col=1)
    if row is not None and "rul_low" in row:
        fig.add_trace(go.Scatter(
            x=[row["cycle"]], y=[row["predicted_rul"]], mode="markers", name=f"80% range, latest {spec.time_title.lower()}",
            marker=dict(color=T["accent"], size=8, line=dict(color=T["bg"], width=2)),
            error_y=dict(type="data", symmetric=False, array=[row["rul_high"] - row["predicted_rul"]],
                         arrayminus=[row["predicted_rul"] - row["rul_low"]], color=T["accent"], thickness=1.5, width=8),
            hovertemplate=f"latest {spec.time_title.lower()} " + "%{x}<br>RUL %{y:.0f}<extra></extra>"), row=1, col=1)
    if has_band:
        fig.add_trace(go.Scatter(
            x=unit_history["cycle"], y=[0] * len(unit_history), mode="markers", name="Risk band per cycle",
            marker=dict(symbol="square", size=6, color=[BAND_COLORS[b] for b in unit_history["risk_band"]]),
            customdata=[BAND_TEXT[b] for b in unit_history["risk_band"]], showlegend=False,
            hovertemplate="cycle %{x}<br>%{customdata}<extra></extra>"), row=2, col=1)
        fig.update_yaxes(visible=False, row=2, col=1)
        fig.update_xaxes(title_text=spec.time_title.lower(), row=2, col=1)
    else:
        fig.update_xaxes(title_text=spec.time_title.lower())
    fig.update_yaxes(title_text=f"predicted RUL ({spec.life_unit})", range=[0, spec.rul_cap + 5], row=1, col=1)
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
                             hovertemplate="health %{y:.2f}<extra></extra>"))
    fig.update_layout(height=height, showlegend=False, xaxis_title="cycle", yaxis_title="health score (0 = new engine)",
                      yaxis_range=[min(-0.5, float(unit_history["health_score"].min()) - 0.2), top])
    return crosshair(fig)


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


def confusion_chart(matrix, units="engines"):
    labels = [BAND_TEXT[b] for b in RISK_BANDS]
    z = np.asarray(matrix, dtype=float)
    norm = z / np.maximum(z.sum(axis=1, keepdims=True), 1)
    fig = go.Figure(go.Heatmap(
        z=norm, x=labels, y=labels, text=np.asarray(matrix), texttemplate="%{text}", showscale=False,
        textfont=dict(family=MONO, size=13, color=T["text_1"]), xgap=2, ygap=2,
        # capped at a mid blue so white counts keep at least 4.5:1 contrast
        colorscale=[[0, T["surface"]], [0.5, "#24406b"], [1, "#3a6cc2"]], zmin=0, zmax=1,
        hovertemplate="true %{y}<br>predicted %{x}<br>%{text} " + units + "<extra></extra>"))
    fig.update_layout(height=360, xaxis_title="predicted band", yaxis_title="true band", yaxis_autorange="reversed",
                      margin=dict(t=8, b=48, l=96, r=8))
    fig.update_xaxes(showgrid=False, ticks="")
    fig.update_yaxes(showgrid=False, ticks="")
    return fig


def ladder_chart(units, limit=None):
    """Fleet RUL forecast: one row per unit, 80% range as a bar, point estimate as a marker."""
    spec = insights.spec_of(units)
    u = units.head(limit) if limit else units
    labels = [spec.unit_id(x) for x in u["unit"]]
    fig = go.Figure()
    _band_zones(fig, axis="x", spec=spec)
    for band, lo, hi in zones(spec):
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
        hovertemplate=f"{spec.unit_title} " + "%{y}<br>RUL %{x:.0f} (80%: %{customdata[1]:.0f} to %{customdata[2]:.0f})"
                      "<br>%{customdata[3]}<extra></extra>"))
    fig.update_layout(height=max(260, 24 * len(u) + 70), barmode="overlay", showlegend=False, bargap=0.4,
                      margin=dict(t=24, b=40, l=44, r=12), hovermode="closest", clickmode="event+select")
    fig.update_xaxes(title_text=f"remaining useful life ({spec.life_unit})", range=[0, spec.rul_cap + 2], side="bottom")
    fig.update_yaxes(autorange="reversed", type="category", tickfont=dict(family=MONO, size=11), showgrid=False, ticks="")
    return fig


def health_heatmap(units, history, threshold, critical, rows=20, window=60):
    """Health score over the last `window` cycles for the most urgent units (rows)."""
    spec = insights.spec_of(units)
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
        z=grid.to_numpy(), x=grid.columns, y=[spec.unit_id(u) for u in grid.index], zmin=lo, zmax=hi, colorscale=scale,
        xgap=1, ygap=1, colorbar=dict(title=dict(text="health", side="right", font=dict(size=11)), thickness=8,
                                      outlinewidth=0, tickfont=dict(family=MONO, size=10)),
        hovertemplate=f"{spec.unit_title} " + "%{y}<br>%{x} " + spec.time_title.lower() + "s from latest<br>health %{z:.2f}<extra></extra>"))
    fig.update_layout(height=max(240, 18 * len(top) + 70), margin=dict(t=8, b=40, l=44, r=8))
    fig.update_xaxes(title_text=f"{spec.time_title.lower()}s before latest reading", showgrid=False)
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
    spec = insights.spec_of(row)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.58, 0.42])
    _band_zones(fig, row=1, col=1, spec=spec)
    if "predicted_rul" in unit_history:
        fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history["predicted_rul"], mode="lines", name="Predicted RUL",
                                 line=dict(color=T["accent"], width=2), hovertemplate="RUL %{y:.0f} " + spec.life_unit + "<extra></extra>"),
                      row=1, col=1)
    if "rul_low" in row:
        fig.add_trace(go.Scatter(
            x=[row["cycle"]], y=[row["predicted_rul"]], mode="markers", name=f"80% range, latest {spec.time_title.lower()}",
            marker=dict(color=T["accent"], size=8, line=dict(color=T["bg"], width=2)),
            error_y=dict(type="data", symmetric=False, array=[row["rul_high"] - row["predicted_rul"]],
                         arrayminus=[row["predicted_rul"] - row["rul_low"]], color=T["accent"], thickness=1.5, width=8),
            hovertemplate="latest reading, 80%% range %s<extra></extra>" % (
                f"{row['rul_low']:.0f} to {row['rul_high']:.0f}")), row=1, col=1)
    fig.add_hline(y=threshold, line=dict(color=STATE_COLOR["DEGRADING"], width=1, dash="dash"), row=2, col=1, exclude_empty_subplots=False,
                  annotation_text="abnormal", annotation_position="top left", annotation_font=dict(color=STATE_COLOR["DEGRADING"]))
    fig.add_hline(y=critical, line=dict(color=STATE_COLOR["CRITICAL"], width=1, dash="dash"), row=2, col=1, exclude_empty_subplots=False,
                  annotation_text="critical", annotation_position="top left", annotation_font=dict(color=STATE_COLOR["CRITICAL"]))
    fig.add_trace(go.Scatter(x=unit_history["cycle"], y=unit_history["health_score"], mode="lines", name="Health score",
                             line=dict(color=T["accent_2"], width=1.6), hovertemplate="health %{y:.2f}<extra></extra>"),
                  row=2, col=1)
    fig.update_yaxes(title_text=f"RUL ({spec.life_unit})", range=[0, spec.rul_cap + 5], row=1, col=1)
    fig.update_yaxes(title_text="health score", row=2, col=1,
                     range=[min(-0.5, float(unit_history["health_score"].min()) - 0.2), max(critical * 1.3, float(unit_history["health_score"].max()) * 1.1)])
    fig.update_xaxes(title_text=spec.time_title.lower(), row=2, col=1)
    fig.update_layout(height=height, margin=dict(t=30, b=40, l=56, r=12))
    return crosshair(fig)


DRIFT_COLORS = {"Critical": STATE_COLOR["CRITICAL"], "Warning": STATE_COLOR["WARNING"], "Elevated": STATE_COLOR["DEGRADING"],
                "Nominal": T["text_3"]}


def drift_table(drift, rows=None, height="auto", compact=False, unit="cycles"):
    """Sensor drift ranking with a 60-step drift sparkline per sensor (unit: the life unit). compact drops module and trend."""
    recent = f"Last 60 {unit}"
    d = drift.head(rows) if rows else drift
    df = pd.DataFrame({"Sensor": d["code"], "Measures": d["name"], "Module": d["module"], "Drift": d["drift"],
                       "Trend": d["trend"], "Status": d["status"], recent: d["history"]})
    if compact:
        df = df.drop(columns=["Module", "Trend"])
    styler = df.style.map(lambda v: f"color: {DRIFT_COLORS.get(v, T['text_1'])}", subset=["Status"])
    st.dataframe(styler, hide_index=True, width="stretch", height=height, column_config={
        "Drift": st.column_config.NumberColumn("Drift (sigma)", format="%+.1f",
                                               help="Directed z-score against the healthy baseline; positive means degrading"),
        "Trend": st.column_config.NumberColumn("Trend", format="%+.2f", help=f"Change in drift per 10 {unit}, last 20 {unit}"),
        recent: st.column_config.LineChartColumn(recent, y_min=-2, y_max=6, width="medium"),
    })


# ---------------------------------------------------------------- engineering views
def crosshair(fig):
    """Oscilloscope-style readout: a dotted cursor across the plot and one hover box per cycle."""
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikedash="dot",
                     spikecolor=T["text_3"])
    fig.update_layout(hovermode="x unified", spikedistance=-1)
    return fig


def envelope_chart(history, trained, spec=None, height=300):
    """Operating envelope: the conditions in the file against the conditions the model was trained on."""
    spec = spec or get("turbofan")
    xk, yk, tk = ENVELOPE[spec.key]
    labels = dict(zip(spec.settings, spec.setting_labels))
    cols = [c for c in (xk, yk, tk) if c]
    pts = history[cols + ["condition_known"]].copy()
    for c in cols:
        pts[c] = pts[c].round(2 if pts[c].abs().max() < 10 else 0)
    seen = pts.groupby(cols).agg(cycles=(xk, "size"), known=("condition_known", "all")).reset_index()
    fig = go.Figure()
    size = 10 + 26 * np.sqrt(seen["cycles"] / seen["cycles"].max())
    colors = [T["accent"] if k else STATE_COLOR["CRITICAL"] for k in seen["known"]]
    fig.add_trace(go.Scatter(
        x=seen[xk], y=seen[yk], mode="markers+text" if tk else "markers", name="in this file",
        marker=dict(size=size, color=colors, opacity=0.85, line=dict(color=T["bg"], width=1)),
        text=[f"TRA {t:.0f}" for t in seen[tk]] if tk else None, textposition="middle right",
        textfont=dict(family=MONO, size=10, color=T["text_2"]), cliponaxis=False,
        customdata=np.stack([seen["cycles"], np.where(seen["known"], "trained", "not trained")], axis=1),
        hovertemplate=f"{labels[yk]} " + "%{y}<br>" + f"{labels[xk]} " + "%{x}<br>%{customdata[0]:,} "
                      + f"{spec.time_title.lower()}s" + "<br>condition %{customdata[1]}<extra></extra>"))
    # Training conditions as rings drawn over the data, so a filled dot inside a ring reads as "covered".
    ring_x = [c.get("settings", {}).get(xk, c.get("mach")) for c in trained]
    ring_y = [c.get("settings", {}).get(yk, c.get("altitude_kft")) for c in trained]
    fig.add_trace(go.Scatter(
        x=ring_x, y=ring_y, mode="markers", name="trained conditions",
        marker=dict(size=46, color="rgba(0,0,0,0)", line=dict(color=T["text_3"], width=1)), hoverinfo="skip"))
    fig.update_layout(height=height, showlegend=False, margin=dict(t=8, b=44, l=56, r=60))
    span = lambda v: (min(v), max(v))  # noqa: E731
    xs, ys = span(list(seen[xk]) + [v for v in ring_x if v is not None]), span(list(seen[yk]) + [v for v in ring_y if v is not None])
    pad = lambda lo, hi: max((hi - lo) * 0.15, abs(hi) * 0.08, 0.1)  # noqa: E731
    fig.update_xaxes(title_text=labels[xk], range=[xs[0] - pad(*xs), xs[1] + pad(*xs) * 1.6], zeroline=False)
    fig.update_yaxes(title_text=labels[yk], range=[ys[0] - pad(*ys), ys[1] + pad(*ys)], zeroline=False)
    return fig


def cross_chart(cross, metric="accuracy"):
    """Generalisation matrix: each subset's model (rows) scored on every subset's test fleet (columns)."""
    models = list(cross)
    data = sorted({d for row in cross.values() for d in row})
    z, text, hover = [], [], []
    for m in models:
        zr, tr, hr = [], [], []
        for d in data:
            cell = cross[m].get(d, {})
            v = cell.get(metric)
            known = cell.get("known_conditions", 1.0)
            zr.append(None if v is None or known < 0.5 else v)
            label = "n/a" if v is None else (f"{v:.0%}" if metric == "accuracy" else f"{v:.1f}")
            tr.append(label if known >= 0.5 else f"{label}<br><span style='font-size:9px'>untrained conditions</span>")
            hr.append(f"{m} model on {d} test fleet<br>{label}" + ("" if known >= 0.5 else "<br>conditions it was not trained on"))
        z.append(zr), text.append(tr), hover.append(hr)
    better_high = metric == "accuracy"
    scale = [[0, T["surface"]], [1, "#3a6cc2"]] if better_high else [[0, "#3a6cc2"], [1, T["surface"]]]
    fig = go.Figure(go.Heatmap(
        z=z, x=[f"{d} test" for d in data], y=[f"{m} model" for m in models], text=text, texttemplate="%{text}",
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showscale=False, xgap=2, ygap=2,
        textfont=dict(family=MONO, size=12, color=T["text_1"]), colorscale=scale))
    fig.update_layout(height=70 + 52 * len(models), margin=dict(t=8, b=32, l=96, r=8), plot_bgcolor=T["bg"])
    fig.update_xaxes(showgrid=False, ticks="", side="top")
    fig.update_yaxes(showgrid=False, ticks="", autorange="reversed")
    return fig
