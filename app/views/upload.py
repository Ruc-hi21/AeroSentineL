"""Ingest data. States: empty, file loaded (preview), processing, success, partial, invalid, unrecognised, failure.

Flow shown on the page: the file is profiled (EDA), the component-recognition model decides which
component it comes from, and that component's pipeline cleans, corrects and scores it.
"""

import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import insights, theme
from app.components import (
    PROFILE_LABELS, SAMPLES, envelope_chart, fleet, require_model, run_analysis, sample_choice, subset_summary,
)
from app.engine3d import engine_twin, twin_payload
from app.theme import MONO, STATES, TOKENS, esc
from src import eda
from src.components import COMPONENTS, get, spec_of_profile
from src.data.loader import read_sensor_file
from src.errors import InvalidDataError
from src.models.artifacts import available_subsets
from src.router import load_router

T = TOKENS
COMPONENT_COLORS = {"turbofan": T["accent"], "battery": "#3ddbd9", "bearing": "#be95ff", "hydraulic": "#5fd4f8",
                    "power": "#f1c21b", "unknown": T["text_3"]}

theme.page_head("Ingest data", "Upload sensor data from a turbofan engine, a Li-ion battery cell, an engine gearbox, a "
                "hydraulic system or a power-electronics switch. Each row is one cycle (or minute) of one unit.")
require_model()

left, right = st.columns([1.6, 1], gap="large")
with left:
    uploaded = st.file_uploader("Sensor data file (.txt or .csv)", type=["txt", "csv"])
with right:
    st.html("""<dl class="as-kv" style="margin-top:4px">
<dt>Turbofan</dt><dd>NASA C-MAPSS .txt (26 columns, no header) or .csv: <code>unit</code>, <code>cycle</code>,
<code>setting_1..3</code>, <code>sensor_1..21</code></dd>
<dt>Battery</dt><dd>.csv: <code>cell</code>, <code>cycle</code>, <code>ambient_c</code>, <code>load_a</code>, capacity, timing,
voltage, resistance and temperature per discharge, from the cell's first cycles</dd>
<dt>Gearbox</dt><dd>.csv: <code>bearing</code>, <code>minute</code>, <code>speed_rpm</code>, <code>load_kn</code>, casing
vibration features per axis (<code>h_rms</code>, <code>v_kurt</code>, ...)</dd>
<dt>Hydraulics</dt><dd>.csv: <code>session</code>, <code>cycle</code>, the 17 rig sensors' cycle means (<code>ps1</code> ..
<code>se</code>) and PS2 / FS1 in six 10 s windows (<code>ps2_w0</code> .. <code>fs1_w5</code>)</dd>
<dt>Power electronics</dt><dd>.csv: <code>device</code>, <code>minute</code>, <code>vce_on</code>, <code>r_on</code>,
<code>vce_ripple</code>, <code>vce_off</code>, <code>ice_on</code>, <code>vge_on</code>, <code>pkg_temp</code></dd></dl>""")
    sample = sample_choice("ingest_sample")
    use_sample = st.button(f"Use the {PROFILE_LABELS[sample]} sample file", key="use_sample")
    summary = subset_summary(sample)
    st.caption(summary[0].upper() + summary[1:] + ".")
if use_sample:
    st.session_state["pending"] = (SAMPLES[sample].name, SAMPLES[sample].read_bytes())
elif uploaded is not None:
    st.session_state["pending"] = (uploaded.name, uploaded.getvalue())

pending = st.session_state.get("pending")
if pending is None:
    current = st.session_state.get("result")
    if current is not None and current.units is not None:
        theme.note(f"Currently loaded: {esc(st.session_state.get('source_name', ''))}, {len(current.units)} "
                   f"{current.spec.unit_plural}, scored by the {esc(current.subset or '')} model (job {esc(current.job_id)}). "
                   "Uploading a new file replaces it.")
        st.page_link("views/overview.py", label="Back to fleet overview", icon=":material/grid_view:")
    st.stop()  # empty state: the uploader and format notes above are the guidance

name, content = pending
try:
    df = read_sensor_file(io.BytesIO(content))
except InvalidDataError as exc:  # invalid-file state, before running anything
    st.error(f"Invalid file ({exc.code}). {exc.message}")
    st.stop()

# ---------------------------------------------------------------- 1. EDA
profile = eda.profile(df)
theme.section("1. Data profile", f"{name}: what the file contains, before any model sees it")
theme.stats([
    theme.stat("Rows", f"{profile['rows']:,}"),
    theme.stat("Columns", profile["columns"], foot=f"{profile['numeric_columns']} numeric"),
    theme.stat("Missing cells", f"{profile['missing_cells']:,}", foot="filled per unit during cleaning"),
    theme.stat("Duplicate rows", f"{profile['duplicate_rows']:,}", foot="removed during cleaning"),
    theme.stat("Constant columns", len(profile["constant_columns"]), foot="carry no wear signal"),
    theme.stat("Outlier cells", f"{profile['outlier_cells']:,}", foot="beyond 4 sigma"),
    theme.stat("Size", f"{len(content) / 1024:,.0f}", "KB"),
])
stats_df = pd.DataFrame([{
    "Column": c["name"], "Missing": c["missing"], "Unique": c["unique"], "Min": c.get("min"), "Median": c.get("median"),
    "Max": c.get("max"), "Std": c.get("std"), "Outliers": c.get("outliers", 0),
    "Distribution": c.get("hist", []),
} for c in profile["column_stats"]])
eda_left, eda_right = st.columns([1.6, 1], gap="large")
with eda_left:
    st.dataframe(stats_df, hide_index=True, width="stretch", height=min(36 * (len(stats_df) + 1) + 4, 420), column_config={
        "Min": st.column_config.NumberColumn(format="%.4g"), "Median": st.column_config.NumberColumn(format="%.4g"),
        "Max": st.column_config.NumberColumn(format="%.4g"), "Std": st.column_config.NumberColumn(format="%.3g"),
        "Distribution": st.column_config.BarChartColumn("Distribution", width="medium"),
    })
with eda_right:
    corr = profile.get("correlation")
    if corr:
        cdf = pd.DataFrame(corr)
        fig = go.Figure(go.Heatmap(z=cdf.to_numpy(), x=list(cdf.columns), y=list(cdf.index), zmin=-1, zmax=1,
                                   colorscale=[[0, "#a8343c"], [0.5, T["surface"]], [1, "#3a6cc2"]], showscale=False,
                                   hovertemplate="%{y} vs %{x}<br>r = %{z:.2f}<extra></extra>", xgap=1, ygap=1))
        fig.update_layout(height=320, margin=dict(t=8, b=8, l=8, r=8))
        fig.update_xaxes(showticklabels=False, showgrid=False)
        fig.update_yaxes(showticklabels=False, showgrid=False, autorange="reversed")
        theme.chart(fig, key="eda_corr")
        pairs = profile.get("top_correlations") or []
        if pairs:
            theme.note("Most related columns: " + "; ".join(f"{esc(p['a'])} and {esc(p['b'])} (r = {p['r']:+.2f})" for p in pairs[:3]) + ".")
with st.expander("Preview first 20 rows"):
    st.dataframe(df.head(20), width="stretch")

# ---------------------------------------------------------------- 2. recognition
router = load_router()
routing = router.route(df) if router is not None else None
theme.section("2. Component recognition", "a model decides from the data alone which component's models may score it")
if routing is None:
    st.info("The recognition model is not trained yet; the component is matched by column names.")
else:
    r_left, r_right = st.columns([1, 1.3], gap="large")
    with r_left:
        label = routing["label"]
        accepted = routing["component"] is not None
        verdict = get(label).name if accepted else ("Not recognised" if label == "unknown" else f"Uncertain ({label})")
        theme.stats([
            theme.stat("Decision", verdict, color=None if accepted else STATES["CRITICAL"]["color"]),
            theme.stat("Confidence", f"{routing['confidence']:.1%}", foot=f"routes at {router.threshold:.0%} or more"),
        ])
        probs = routing["probabilities"]
        fig = go.Figure(go.Bar(
            x=list(probs.values()), y=[get(k).name if k in COMPONENTS else "Not a known component" for k in probs],
            orientation="h", width=0.55, marker_color=[COMPONENT_COLORS.get(k, T["text_3"]) for k in probs],
            text=[f"{v:.1%}" for v in probs.values()], textposition="outside", cliponaxis=False,
            textfont=dict(family=MONO, size=11, color=T["text_2"]), hovertemplate="%{y}<br>%{x:.3f}<extra></extra>"))
        fig.add_vline(x=router.threshold, line=dict(color=T["line_strong"], width=1, dash="dot"))
        fig.update_layout(height=190, margin=dict(t=8, b=32, l=8, r=48), xaxis=dict(range=[0, 1.12], title="probability"),
                          yaxis=dict(ticks="", autorange="reversed"))
        theme.chart(fig, key="route_probs")
    with r_right:
        signals = routing.get("signals") or []
        if signals:
            theme.kv([(s["description"].capitalize(), f"{s['value']:.3g}") for s in signals])
            theme.note("The data signals that pushed this decision most (SHAP on the recognition model). It reads "
                       "values, not column names: magnitudes, how values evolve with age, smoothness and impulsiveness.")
        if not accepted:
            st.warning(f"This file will not be scored automatically: {routing['reason']}. Choose a model below only if "
                       "you know which component the data comes from.")

# ---------------------------------------------------------------- model choice and run
trained = available_subsets()
options = ["auto"] + trained
auto_label = (f"Automatic: {get(routing['component']).name}" if routing and routing["component"] else
              "Automatic (recognition model)")
labels = {"auto": auto_label, **{s: f"{spec_of_profile(s).unit_title}, {s}: {subset_summary(s)}" for s in trained}}
pick, run, _ = st.columns([2.4, 0.8, 1.4], vertical_alignment="bottom")
with pick:
    choice = st.selectbox("Model", options, format_func=labels.get, key="ingest_model",
                          help="Automatic sends the file to the component the recognition model chose; for turbofans "
                               "the subset comes from the file name or the number of operating conditions. Choosing a "
                               "model overrides both.")
with run:
    start = st.button("Run analysis", type="primary", width="stretch")
if start:
    subset = None if choice == "auto" else choice
    with st.spinner("Recognising the component, cleaning, correcting and scoring"):
        run_analysis(name, content, subset=subset)
    st.rerun()  # redraw the sidebar with the model that scored this file

result = st.session_state.get("last_run")
if result is None:
    st.stop()

if result.status == "FAILED":
    error = result.error
    title = {"INVALID_DATASET": "Invalid data", "UNKNOWN_COMPONENT": "Component not recognised"}.get(error["code"], "Analysis failed")
    st.error(f"{title} ({error['code']}). {error['message']}  \nRequest ID: `{error['requestId']}`")
    st.stop()

artifacts = require_model(result.subset)
spec = result.spec
if result.status == "PARTIAL":
    failed = [k for k, v in result.stages.items() if v != "ok"]
    st.warning(f"Partial result. These stages failed: {', '.join(failed)}. The other results are still shown.")
else:
    st.success(f"Analysis complete: {insights.count(len(result.units), spec)} in {result.duration_ms:.0f} ms. "
               f"{spec.name} model {result.subset} ({result.profile['reason']}). Job {result.job_id}, model {result.model_version}.")

# ---------------------------------------------------------------- 3. processing report
v, c, units, prof, t = result.validation, result.cleaning, result.units, result.profile, result.timings
rt = result.routing or {}
corrected = prof["corrected"]
route_value = spec.unit_title if not rt.get("by_user") else f"{spec.unit_title} (chosen)"
route_detail = (f"{rt['confidence']:.0%} confident" if rt.get("confidence") is not None else "by column names")
steps = [
    ("Profile", f"{v['rows']:,} rows", f"{result.eda['columns'] if result.eda else '?'} columns profiled", "ok",
     t.get("read", 0) + t.get("eda", 0)),
    ("Recognise", route_value, route_detail, "ok", t.get("route")),
    ("Validate", insights.count(v['units'], spec), f"{len(v['warnings'])} warnings", "ok", t.get("validate")),
    ("Clean", f"{c['rows_out']:,} kept", f"{c['dropped_duplicates']} duplicates, {c['filled_values']} filled", "ok", t.get("clean")),
    ("Conditions", f"{prof['conditions_seen']} found", "corrected to the reference" if corrected else "single condition, no correction",
     "ok", t.get("conditions")),
    ("Health", f"{int((units['health_condition'] == 'abnormal').sum())} abnormal", "drift from healthy baseline", "ok", t.get("health")),
    ("Features", f"{len(artifacts.metadata['features'])} per {spec.time_title.lower()}", "rolling stats, trends, drift",
     result.stages.get("preprocessing", "ok"), t.get("features")),
    ("RUL model", "XGBoost", "with 80% range", result.stages.get("rul", "n/a"), t.get("rul")),
    ("Risk model", "XGBoost", "four risk bands", result.stages.get("risk", "n/a"), t.get("risk")),
    ("Explain", "SHAP", "top sensors per unit", result.stages.get("explain", "n/a"), t.get("explain")),
]
theme.section("3. Processing report", f"{spec.name} model {result.subset}, {result.duration_ms:,.0f} ms end to end")
st.html(f'<div class="as-steps" style="--n:{len(steps)}">' + "".join(
    f'<div class="st" style="--c:{"#42be65" if s == "ok" else "#fa4d56"}"><div class="n"><i></i>{esc(n)}</div>'
    f'<div class="v">{esc(val)}</div><div class="d">{esc(d if s == "ok" else s)}</div>'
    f'{f"<div class=ms>{ms:,.0f} ms</div>" if ms is not None else ""}</div>'
    for n, val, d, s, ms in steps) + "</div>")
for warning in v["warnings"]:
    st.caption(f"Data warning: {warning}")

if spec.settings and set(spec.settings) <= set(result.history.columns):
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        theme.section("Operating envelope", "conditions in this file; rings are the conditions the model was trained on")
        theme.chart(envelope_chart(result.history, prof["condition_table"], spec), key="ingest_envelope")
    with right:
        theme.section("What the correction does")
        if corrected:
            what = {"turbofan": "altitude, speed and throttle", "battery": "ambient temperature and discharge current",
                    "bearing": "shaft speed and radial load"}[spec.key]
            theme.note(f"Readings change with {what} as well as with wear. Before modelling, every reading is mapped to "
                       f"the value it would show at the reference condition, using statistics from the {result.subset} "
                       "training units. The charts and the 3D model show these corrected readings.")
        else:
            theme.note("All data was recorded at a single operating condition, so readings are used as recorded.")
        if spec.settings_as_features:
            theme.note("The operating settings are also model inputs here, because they set how fast this component wears.")
        unknown = int((~result.history["condition_known"]).sum())
        if unknown:
            st.warning(f"{unknown:,} {spec.time_title.lower()}s come from conditions the {result.subset} model never saw.")

ranked = fleet(result)
theme.distribution(insights.state_counts(ranked))

top = ranked.iloc[0]
unit = int(top["unit"])
theme.section(f"Most urgent {spec.actions.get('noun', 'unit')}", f"{spec.label(unit)}, {STATES[top['state']]['label'].lower()}")
engine_twin(twin_payload(result, unit, artifacts.health, st.session_state.get("source_name", name)), height=760, key="upload_twin")
links = st.columns([1, 1, 3])
links[0].page_link("views/overview.py", label="Open fleet overview", icon=":material/grid_view:")
links[1].page_link("views/engine.py", label=f"Open {spec.unit_title.lower()} status", icon=":material/speed:")
