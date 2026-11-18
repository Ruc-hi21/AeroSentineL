"""Ingest data: the system status card, a centred drop zone (or a bundled sample), a pre-flight animation while the
file is processed, then the file itself: a confirmation and the uploaded table. What the analysis found is on
Fleet details."""

import io
import time

import streamlit as st

from app import theme
from app.components import (
    SAMPLE_INFO, SAMPLES, get_result, require_model, run_analysis, sample_choice, sample_truth, subset_summary,
)
from app.theme import esc
from src.data.loader import read_sensor_file

MIN_SHOW = 3.6  # seconds the pre-flight animation stays up, so its stages can be read even on a fast run
SHOW_ROWS = 200_000  # rows sent to the browser table; bigger files show their first rows (the analysis uses every row)
MAX_UPLOAD = f"{st.get_option('server.maxUploadSize') / 1024:g} GB"


def size_text(n):
    """'34 KB', '12.4 MB', '1.8 GB'."""
    for unit, scale in (("GB", 1024 ** 3), ("MB", 1024 ** 2)):
        if n >= scale:
            return f"{n / scale:,.1f} {unit}"
    return f"{n / 1024:,.0f} KB"


theme.page_head("Ingest data", "Drop in a sensor log, or pick a bundled sample. Each row is one cycle (or minute) of one unit, "
                "from its first record to its latest.", kicker="Data intake")
require_model()

_, mid, _ = st.columns([1, 2.4, 1])
with mid:
    # What the console holds right now: waiting for a file, or the file it last analysed.
    loaded = get_result()
    if loaded is not None and loaded.units is not None:
        st.html(theme.status_card(st.session_state.get("source_name", "loaded file"), [
            ("Component", loaded.spec.name), (loaded.spec.unit_plural.capitalize(), f"{len(loaded.units)}"),
            ("Model", f"{loaded.model_version} {loaded.subset or ''}".strip()),
        ]))
    else:
        st.html(theme.status_card("Waiting for data", [
            ("Models", "5 components ready"), ("Formats", ".txt or .csv"), ("Limit", f"up to {MAX_UPLOAD} per file"),
        ], ready=False))

    st.html('<div class="as-drop-title"><div class="k">Upload</div><h2>Drop a sensor file to begin</h2>'
            f'<p>.txt (NASA C-MAPSS layout) or .csv, any of the five components, up to {esc(MAX_UPLOAD)}</p></div>')
    with st.container(key="ingest_drop"):
        uploaded = st.file_uploader("Sensor data file (.txt or .csv)", type=["txt", "csv"], label_visibility="collapsed")
    st.html('<div class="as-or">or try a sample</div>')
    s_left, s_right = st.columns([3, 1.2], vertical_alignment="bottom")
    with s_left:
        sample = sample_choice("ingest_sample")
    with s_right:
        use_sample = st.button("Use this sample", key="use_sample", width="stretch")
    summary = subset_summary(SAMPLE_INFO[sample]["profile"])
    truth = sample_truth(sample)
    st.caption(summary[0].upper() + summary[1:] + "." + (f" True remaining life: {truth}." if truth else ""))
    with st.expander("File layout per component"):
        st.html("""<dl class="as-kv">
<dt>Turbofan</dt><dd>NASA C-MAPSS .txt (26 columns, no header) or .csv: <code>unit</code>, <code>cycle</code>,
<code>setting_1..3</code>, <code>sensor_1..21</code></dd>
<dt>Battery</dt><dd>.csv: <code>cell</code>, <code>cycle</code>, <code>ambient_c</code>, <code>load_a</code>, capacity, timing,
voltage, resistance and temperature per discharge</dd>
<dt>Gearbox</dt><dd>.csv: <code>bearing</code>, <code>minute</code>, <code>speed_rpm</code>, <code>load_kn</code>, casing
vibration features per axis (<code>h_rms</code>, <code>v_kurt</code>, ...)</dd>
<dt>Hydraulics</dt><dd>.csv: <code>session</code>, <code>cycle</code>, the 17 rig sensors' cycle means (<code>ps1</code> ..
<code>se</code>) and PS2 / FS1 in six 10 s windows (<code>ps2_w0</code> .. <code>fs1_w5</code>)</dd>
<dt>Power electronics</dt><dd>.csv: <code>device</code>, <code>minute</code>, <code>vce_on</code>, <code>r_on</code>,
<code>vce_ripple</code>, <code>vce_off</code>, <code>ice_on</code>, <code>vge_on</code>, <code>pkg_temp</code></dd></dl>""")

if use_sample:
    st.session_state["pending"] = (SAMPLES[sample].name, SAMPLES[sample].read_bytes())
elif uploaded is not None:
    st.session_state["pending"] = (uploaded.name, uploaded.getvalue())

pending = st.session_state.get("pending")
if pending is not None:
    name, content = pending
    _, go, _ = st.columns([1, 1.4, 1])
    with go:
        start = st.button(f"Run analysis on {name}", type="primary", width="stretch")
    if start:
        stage = st.empty()
        stage.html(theme.preflight(name, MIN_SHOW))
        t0 = time.perf_counter()
        run_analysis(name, content)
        time.sleep(max(0.0, MIN_SHOW + 0.3 - (time.perf_counter() - t0)))  # let the checklist finish
        stage.empty()
        st.session_state.pop("pending", None)
        st.rerun()  # redraw the page with the file that was analysed

result = st.session_state.get("last_run")
last = st.session_state.get("last_file")
if result is None or last is None:
    st.stop()
name, content = last

if result.status == "FAILED":
    st.html(f'<div class="as-done fail"><div class="ok"></div><div><b>The file could not be analysed</b>'
            f'<span>{esc(name)} · {esc(result.error["message"])}</span></div></div>')
    st.page_link("views/fleet_detail.py", label="Fleet details, Data check tab: see why, or choose the model by hand",
                 icon=":material/dataset:")
    st.stop()


@st.cache_data(show_spinner=False, max_entries=2)
def read_table(file_name, size, _raw):
    """The uploaded file as a table. Keyed on name and size, so a large file is not hashed on every rerun."""
    return read_sensor_file(io.BytesIO(_raw))


table = read_table(name, len(content), content)
st.html(f'<div class="as-done"><div class="ok"></div><div><b>Data uploaded</b>'
        f'<span>{esc(name)} · {len(table):,} rows · {table.shape[1]} columns · {size_text(len(content))}</span></div></div>')
st.page_link("views/fleet_detail.py", label="See what the analysis found on Fleet details", icon=":material/table_chart:")
shown = len(table) <= SHOW_ROWS
theme.section("Uploaded data", "every row of the file, as it was read" if shown else
              f"the first {SHOW_ROWS:,} of {len(table):,} rows; the analysis used every row", kicker="Dataset")
st.dataframe(table if shown else table.head(SHOW_ROWS), hide_index=True, width="stretch", height=560)
