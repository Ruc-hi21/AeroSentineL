"""Ingest data. States: empty, file loaded (preview), processing, success, partial, invalid, failure."""

import io

import streamlit as st

from app import insights, theme
from app.components import SAMPLE, fleet, require_model, run_analysis
from app.engine3d import engine_twin, twin_payload
from app.theme import STATES, esc
from src.data.loader import read_sensor_file
from src.errors import InvalidDataError

theme.page_head("Ingest data", "Upload engine sensor data in NASA C-MAPSS format. Each row is one operating cycle of one engine.")
artifacts = require_model()

left, right = st.columns([1.6, 1], gap="large")
with left:
    uploaded = st.file_uploader("Sensor data file (.txt or .csv)", type=["txt", "csv"])
with right:
    st.html("""<dl class="as-kv" style="margin-top:4px">
<dt>Raw .txt</dt><dd>26 space-separated columns, no header</dd>
<dt>.csv</dt><dd><code>unit</code>, <code>cycle</code>, <code>setting_1..3</code>, <code>sensor_1..21</code></dd>
<dt>Minimum</dt><dd>30 cycles per engine for a reliable prediction</dd></dl>""")
    use_sample = SAMPLE.exists() and st.button(f"Use the sample file ({SAMPLE.name}, 100 engines)")
if use_sample:
    st.session_state["pending"] = (SAMPLE.name, SAMPLE.read_bytes())
elif uploaded is not None:
    st.session_state["pending"] = (uploaded.name, uploaded.getvalue())

pending = st.session_state.get("pending")
if pending is None:
    current = st.session_state.get("result")
    if current is not None and current.units is not None:
        theme.note(f"Currently loaded: {esc(st.session_state.get('source_name', ''))}, {len(current.units)} engines "
                   f"(job {esc(current.job_id)}). Uploading a new file replaces it.")
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
theme.stats([
    theme.stat("Rows", f"{len(df):,}"),
    theme.stat("Engines", n_units if n_units is not None else "unknown"),
    theme.stat("Cycles per engine", f"{cycles.min()} to {cycles.max()}" if cycles is not None else "unknown"),
    theme.stat("Columns", df.shape[1]),
    theme.stat("Size", f"{len(content) / 1024:,.0f}", "KB"),
])
with st.expander("Preview first 20 rows"):
    st.dataframe(df.head(20), width="stretch")

if st.button("Run analysis", type="primary"):
    with st.spinner("Validating, cleaning and running the RUL and risk models"):
        run_analysis(name, content)

result = st.session_state.get("last_run")
if result is None:
    st.stop()

if result.status == "FAILED":
    error = result.error
    title = "Invalid data" if error["code"] == "INVALID_DATASET" else "Analysis failed"
    st.error(f"{title} ({error['code']}). {error['message']}  \nRequest ID: `{error['requestId']}`")
    st.stop()

if result.status == "PARTIAL":
    failed = [k for k, v in result.stages.items() if v != "ok"]
    st.warning(f"Partial result. These stages failed: {', '.join(failed)}. The other results are still shown.")
else:
    st.success(f"Analysis complete: {len(result.units)} engines in {result.duration_ms:.0f} ms. "
               f"Job {result.job_id}, model {result.model_version}.")

# Processing report: what each stage did, with this run's numbers.
v, c, units = result.validation, result.cleaning, result.units
steps = [
    ("Validate", f"{v['rows']:,} rows", f"{v['units']} engines, {len(v['warnings'])} warnings", "ok"),
    ("Clean", f"{c['rows_out']:,} kept", f"{c['dropped_duplicates']} duplicates, {c['filled_values']} filled", "ok"),
    ("Health", f"{int((units['health_condition'] == 'abnormal').sum())} abnormal", "drift from healthy baseline", "ok"),
    ("Features", f"{len(artifacts.metadata['features'])} per cycle", "rolling stats, trends, drift", result.stages.get("preprocessing", "ok")),
    ("RUL model", "XGBoost", "with 80% range", result.stages.get("rul", "n/a")),
    ("Risk model", "XGBoost", "four risk bands", result.stages.get("risk", "n/a")),
    ("Explain", "SHAP", "top sensors per engine", result.stages.get("explain", "n/a")),
]
theme.section("Processing report")
st.html('<div class="as-steps">' + "".join(
    f'<div class="st" style="--c:{"#42be65" if s == "ok" else "#fa4d56"}"><div class="n"><i></i>{esc(n)}</div>'
    f'<div class="v">{esc(val)}</div><div class="d">{esc(d if s == "ok" else s)}</div></div>'
    for n, val, d, s in steps) + "</div>")
for warning in v["warnings"]:
    st.caption(f"Data warning: {warning}")

ranked = fleet(result)
theme.distribution(insights.state_counts(ranked))

top = ranked.iloc[0]
unit = int(top["unit"])
theme.section("Most urgent engine", f"Engine {unit:03d}, {STATES[top['state']]['label'].lower()}")
engine_twin(twin_payload(result, unit, artifacts.health, st.session_state.get("source_name", name)), height=760, key="upload_twin")
links = st.columns([1, 1, 3])
links[0].page_link("views/overview.py", label="Open fleet overview", icon=":material/grid_view:")
links[1].page_link("views/engine.py", label="Open engine status", icon=":material/speed:")
