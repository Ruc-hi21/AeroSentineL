"""Upload & Analyze. States: empty, file loaded (preview), processing, success, partial, invalid, failure."""

import io

import streamlit as st

from app import fx, theme
from app.components import SAMPLE, band_label, require_model, run_analysis
from app.engine3d import engine_twin, twin_payload
from app.theme import CYAN
from src.config import RISK_BANDS
from src.data.loader import read_sensor_file
from src.errors import InvalidDataError

theme.page_header("Telemetry uplink · ingest & analyse", "Upload & Analyze",
                  "Drop engine sensor data in NASA C-MAPSS format — the raw <code>.txt</code> (26 space-separated columns, "
                  "no header) or a <code>.csv</code> with <code>unit</code>, <code>cycle</code>, <code>setting_1..3</code>, "
                  "<code>sensor_1..21</code>. One row = one operating cycle of one engine.")
artifacts = require_model()

left, right = st.columns([2, 1], vertical_alignment="bottom")
with left:
    uploaded = st.file_uploader("Sensor data file", type=["txt", "csv"])
with right:
    use_sample = SAMPLE.exists() and st.button(f"…or use the sample: {SAMPLE.name} (100 test engines)", width="stretch")
if use_sample:
    st.session_state["pending"] = (SAMPLE.name, SAMPLE.read_bytes())
elif uploaded is not None:
    st.session_state["pending"] = (uploaded.name, uploaded.getvalue())

pending = st.session_state.get("pending")
if pending is None:
    st.info("No file selected yet.", icon=":material/satellite_alt:")  # empty state
    st.stop()

name, content = pending
try:
    df = read_sensor_file(io.BytesIO(content))
except InvalidDataError as exc:  # invalid-file state, before running anything
    st.error(f"**Invalid file — {exc.code}.** {exc.message}")
    st.stop()

n_units = df["unit"].nunique() if "unit" in df else "?"
theme.kpi_row([
    theme.kpi("File", 0, "📄", f"{len(content) / 1024:,.0f} KB", CYAN, text=name, compact=True),
    theme.kpi("Rows", len(df), "🧾", "operating cycles", theme.VIOLET),
    theme.kpi("Engines", n_units if isinstance(n_units, int) else 0, "🛩️", "distinct units", "#19f5a0",
              text=None if isinstance(n_units, int) else "?"),
    theme.kpi("Columns", df.shape[1], "🧬", "settings + sensors", "#ffd23f"),
])
with st.expander("Preview first rows"):
    st.dataframe(df.head(20), width="stretch")

if st.button("⚡  Run analysis", type="primary"):
    with st.spinner("Uplinking telemetry · running XGBoost + SHAP…"):
        run_analysis(name, content)

result = st.session_state.get("last_run")
if result is None:
    st.stop()

if result.status == "FAILED":
    error = result.error
    title = "Invalid data" if error["code"] == "INVALID_DATASET" else "Analysis failed"
    st.error(f"**{title} — {error['code']}.** {error['message']}  \nRequest ID: `{error['requestId']}`")
    st.stop()

if result.status == "PARTIAL":
    failed = [k for k, v in result.stages.items() if v != "ok"]
    st.warning(f"**Partial result.** These stages failed: {', '.join(failed)}. The other results are still shown.")
else:
    st.success(f"Analysis complete — {len(result.units)} units. Job `{result.job_id}`, "
               f"model {result.model_version}, {result.duration_ms:.0f} ms.")

for warning in result.validation["warnings"]:
    st.caption(f"⚠️ {warning}")

fx.analysis_sequence(result, st.session_state.get("source_name", name))

cards = [
    theme.kpi("Rows cleaned", result.cleaning["rows_out"], "🧹", f"{result.cleaning['rows_in']:,} in", CYAN),
    theme.kpi("Duplicates removed", result.cleaning["dropped_duplicates"], "🧬", "(unit, cycle) pairs", theme.VIOLET),
    theme.kpi("Values filled", result.cleaning["filled_values"], "🩹", "per-unit forward/back fill", "#ffd23f"),
    theme.kpi("Flagged for review", int(result.units["needs_review"].sum()), "👀", "need a human look", "#ff8a1f"),
]
theme.kpi_row(cards)
if "risk_band" in result.units:
    counts = result.units["risk_band"].value_counts()
    st.html(" ".join(theme.band_pill(b, f" · {counts.get(b, 0)}") for b in RISK_BANDS))

# ---------------------------------------------------------------- straight into the twin
units = result.units
if "risk_band" in units:
    worst = units.assign(_s=units["risk_band"].map(RISK_BANDS.index),
                         _r=units.get("predicted_rul", 0)).sort_values(["_s", "_r"], ascending=[False, True]).iloc[0]
else:
    worst = units.iloc[0]
unit = int(worst["unit"])
band = worst.get("risk_band")
theme.section("Digital twin", f"most critical · unit {unit:03d}")
if isinstance(band, str):
    st.caption(f"Unit {unit:03d} is the most urgent engine in this upload ({band_label(band)}). "
               "Pick any other unit on the 3D Digital Twin page.")
engine_twin(twin_payload(result, unit, artifacts.health, st.session_state.get("source_name", name)),
            height=800, key="upload_twin")

left, right = st.columns(2)
with left:
    st.page_link("views/twin.py", label="Open the full 3D Digital Twin", icon=":material/view_in_ar:")
with right:
    st.page_link("views/overview.py", label="Back to Mission Control", icon=":material/radar:")
