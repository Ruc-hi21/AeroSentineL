"""Ingest data. States: empty, file loaded (preview), processing, success, partial, invalid, failure."""

import io

import streamlit as st

from app import insights, theme
from app.components import (
    SAMPLES, envelope_chart, fleet, require_model, run_analysis, sample_choice, subset_summary,
)
from app.engine3d import engine_twin, twin_payload
from app.theme import STATES, esc
from src.config import SUBSETS
from src.data.loader import read_sensor_file
from src.data.profile import detect_subset
from src.errors import InvalidDataError
from src.models.artifacts import available_subsets
from src.preprocessing.conditions import count_conditions

theme.page_head("Ingest data", "Upload engine sensor data in NASA C-MAPSS format. Each row is one operating cycle of one engine.")
require_model()

left, right = st.columns([1.6, 1], gap="large")
with left:
    uploaded = st.file_uploader("Sensor data file (.txt or .csv)", type=["txt", "csv"])
with right:
    st.html("""<dl class="as-kv" style="margin-top:4px">
<dt>Raw .txt</dt><dd>26 space-separated columns, no header</dd>
<dt>.csv</dt><dd><code>unit</code>, <code>cycle</code>, <code>setting_1..3</code>, <code>sensor_1..21</code></dd>
<dt>Minimum</dt><dd>30 cycles per engine for a reliable prediction</dd></dl>""")
    sample = sample_choice("ingest_sample")
    use_sample = st.button(f"Use the {sample} test fleet ({SUBSETS[sample]['test_engines']} engines)", key="use_sample")
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
        theme.note(f"Currently loaded: {esc(st.session_state.get('source_name', ''))}, {len(current.units)} engines, "
                   f"scored by the {esc(current.subset or '')} model (job {esc(current.job_id)}). Uploading a new file replaces it.")
        st.page_link("views/overview.py", label="Back to fleet overview", icon=":material/grid_view:")
    st.stop()  # empty state: the uploader and format notes above are the guidance

name, content = pending
try:
    df = read_sensor_file(io.BytesIO(content))
except InvalidDataError as exc:  # invalid-file state, before running anything
    st.error(f"Invalid file ({exc.code}). {exc.message}")
    st.stop()

theme.section("File", name)
n_units = df["unit"].nunique() if "unit" in df else None
cycles = df.groupby("unit")["cycle"].max() if {"unit", "cycle"} <= set(df.columns) else None
conditions = count_conditions(df)
auto_subset, auto_reason = detect_subset(df, name)
theme.stats([
    theme.stat("Rows", f"{len(df):,}"),
    theme.stat("Engines", n_units if n_units is not None else "unknown"),
    theme.stat("Cycles per engine", f"{cycles.min()} to {cycles.max()}" if cycles is not None else "unknown"),
    theme.stat("Operating conditions", conditions, foot="altitude, Mach, throttle"),
    theme.stat("Size", f"{len(content) / 1024:,.0f}", "KB"),
])
with st.expander("Preview first 20 rows"):
    st.dataframe(df.head(20), width="stretch")

# Model choice: automatic by default, any trained subset on request.
trained = available_subsets()
options = ["auto"] + trained
labels = {"auto": f"Automatic: {auto_subset}, {auto_reason}",
          **{s: f"{s}: {subset_summary(s)}" for s in trained}}
pick, run, _ = st.columns([2.2, 0.8, 1.6], vertical_alignment="bottom")
with pick:
    choice = st.selectbox("Model", options, format_func=labels.get, key="ingest_model",
                          help="Each C-MAPSS subset has its own model. Automatic uses the subset named in the file, "
                               "or else the one that matches how many operating conditions the data contains.")
with run:
    start = st.button("Run analysis", type="primary", width="stretch")
if start:
    subset = None if choice == "auto" else choice
    with st.spinner(f"Running the {subset or auto_subset} model on {n_units or 'the'} engines"):
        run_analysis(name, content, subset=subset)
    st.rerun()  # redraw the sidebar with the model that scored this file

result = st.session_state.get("last_run")
if result is None:
    st.stop()

if result.status == "FAILED":
    error = result.error
    title = "Invalid data" if error["code"] == "INVALID_DATASET" else "Analysis failed"
    st.error(f"{title} ({error['code']}). {error['message']}  \nRequest ID: `{error['requestId']}`")
    st.stop()

artifacts = require_model(result.subset)
if result.status == "PARTIAL":
    failed = [k for k, v in result.stages.items() if v != "ok"]
    st.warning(f"Partial result. These stages failed: {', '.join(failed)}. The other results are still shown.")
else:
    st.success(f"Analysis complete: {len(result.units)} engines in {result.duration_ms:.0f} ms with the "
               f"{result.subset} model ({result.profile['reason']}). Job {result.job_id}, model {result.model_version}.")

# Processing report: what each stage did, with this run's numbers and timings.
v, c, units, prof, t = result.validation, result.cleaning, result.units, result.profile, result.timings
corrected = prof["corrected"]
steps = [
    ("Validate", f"{v['rows']:,} rows", f"{v['units']} engines, {len(v['warnings'])} warnings", "ok", t.get("read", 0) + t.get("validate", 0)),
    ("Clean", f"{c['rows_out']:,} kept", f"{c['dropped_duplicates']} duplicates, {c['filled_values']} filled", "ok", t.get("clean")),
    ("Conditions", f"{prof['conditions_seen']} found", "corrected to sea level" if corrected else "single condition, no correction",
     "ok", t.get("conditions")),
    ("Health", f"{int((units['health_condition'] == 'abnormal').sum())} abnormal", "drift from healthy baseline", "ok", t.get("health")),
    ("Features", f"{len(artifacts.metadata['features'])} per cycle", "rolling stats, trends, drift",
     result.stages.get("preprocessing", "ok"), t.get("features")),
    ("RUL model", "XGBoost", "with 80% range", result.stages.get("rul", "n/a"), t.get("rul")),
    ("Risk model", "XGBoost", "four risk bands", result.stages.get("risk", "n/a"), t.get("risk")),
    ("Explain", "SHAP", "top sensors per engine", result.stages.get("explain", "n/a"), t.get("explain")),
]
theme.section("Processing report", f"{result.subset} model, {result.duration_ms:,.0f} ms end to end")
st.html(f'<div class="as-steps" style="--n:{len(steps)}">' + "".join(
    f'<div class="st" style="--c:{"#42be65" if s == "ok" else "#fa4d56"}"><div class="n"><i></i>{esc(n)}</div>'
    f'<div class="v">{esc(val)}</div><div class="d">{esc(d if s == "ok" else s)}</div>'
    f'{f"<div class=ms>{ms:,.0f} ms</div>" if ms is not None else ""}</div>'
    for n, val, d, s, ms in steps) + "</div>")
for warning in v["warnings"]:
    st.caption(f"Data warning: {warning}")

if {"setting_1", "setting_2", "setting_3"} <= set(result.history.columns):
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        theme.section("Operating envelope", "where these engines flew; rings are the conditions the model was trained on")
        theme.chart(envelope_chart(result.history, prof["condition_table"]), key="ingest_envelope")
    with right:
        theme.section("What the correction does")
        if corrected:
            theme.note("Most readings change more with altitude, speed and throttle than with wear. Before modelling, "
                       "every reading is mapped to the value it would show at the sea-level, full-throttle reference "
                       f"condition, using statistics from the {result.subset} training engines. The charts and the 3D "
                       "model show these corrected readings.")
        else:
            theme.note("All cycles were flown at a single condition, so readings are used as recorded. Files with several "
                       "operating conditions are scored by the FD002 or FD004 model, which corrects each reading to the "
                       "sea-level reference first.")
        unknown = int((~result.history["condition_known"]).sum())
        if unknown:
            st.warning(f"{unknown:,} cycles were flown at conditions the {result.subset} model never saw. Choose a model "
                       "trained on several operating conditions (FD002 or FD004).")

ranked = fleet(result)
theme.distribution(insights.state_counts(ranked))

top = ranked.iloc[0]
unit = int(top["unit"])
theme.section("Most urgent engine", f"Engine {unit:03d}, {STATES[top['state']]['label'].lower()}")
engine_twin(twin_payload(result, unit, artifacts.health, st.session_state.get("source_name", name)), height=760, key="upload_twin")
links = st.columns([1, 1, 3])
links[0].page_link("views/overview.py", label="Open fleet overview", icon=":material/grid_view:")
links[1].page_link("views/engine.py", label="Open engine status", icon=":material/speed:")
