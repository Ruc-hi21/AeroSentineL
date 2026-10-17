"""Ingest data, the maintainer view: choose a file or a sample, run it, and see three simple results. The data
profile, component recognition, manual model choice and processing report are in Admin, data check."""

import streamlit as st

from app import insights, theme
from app.components import (
    SAMPLE_INFO, SAMPLES, fleet, require_model, run_analysis, sample_choice, sample_truth, subset_summary,
)
from app.theme import STATES, esc

theme.page_head("Ingest data", "Upload a sensor file, or pick a sample, and run the analysis. Each row is one cycle "
                "(or minute) of one unit, from its first record to its latest.")
require_model()

left, right = st.columns([1.3, 1], gap="large")
with left:
    uploaded = st.file_uploader("Sensor data file (.txt or .csv)", type=["txt", "csv"])
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
with right:
    sample = sample_choice("ingest_sample")
    summary = subset_summary(SAMPLE_INFO[sample]["profile"])
    truth = sample_truth(sample)
    st.caption(summary[0].upper() + summary[1:] + "." + (f" True remaining life: {truth}." if truth else ""))
    use_sample = st.button("Use this sample", key="use_sample")

if use_sample:
    st.session_state["pending"] = (SAMPLES[sample].name, SAMPLES[sample].read_bytes())
elif uploaded is not None:
    st.session_state["pending"] = (uploaded.name, uploaded.getvalue())

pending = st.session_state.get("pending")
if pending is not None:
    name, content = pending
    go, _ = st.columns([1, 3], vertical_alignment="center")
    with go:
        start = st.button(f"Run analysis on {name}", type="primary", width="stretch")
    if start:
        with st.spinner("Recognising the component and predicting"):
            run_analysis(name, content)
        st.session_state.pop("pending", None)
        st.rerun()  # redraw the sidebar with the model that scored this file

result = st.session_state.get("last_run")
if result is None:
    st.stop()
if result.status == "FAILED":
    error = result.error
    st.error(f"The file could not be analysed. {error['message']}")
    st.page_link("views/data_check.py", label="Open the data check to see why, or to choose the model by hand",
                 icon=":material/dataset:")
    st.stop()

spec = result.spec
units = fleet(result)
noun = spec.actions.get("noun", "unit")
not_healthy = units[units["state"] != "HEALTHY"]

# 1. What was analysed.
theme.section("1. Analysis done", esc(st.session_state.get("source_name", "")))
theme.stats([
    theme.stat("Recognised as", spec.name),
    theme.stat(spec.unit_plural.capitalize(), len(units)),
    theme.stat("Need attention", len(not_healthy), color=STATES["WARNING"]["color"] if len(not_healthy) else None),
])
if result.status == "PARTIAL":
    st.warning("Part of the analysis failed; the rest is shown. The data check (admin) lists which step.")

# 2. How they stand.
theme.section(f"2. {spec.unit_plural.capitalize()} by condition")
theme.distribution(insights.state_counts(units))

# 3. The most urgent unit, and where to go next.
top = units.iloc[0]
state = top["state"]
theme.section(f"3. Most urgent {noun}", f"{spec.label(int(top['unit']))}")
items = [theme.stat("Condition", STATES[state]["label"], color=STATES[state]["color"])]
if "predicted_rul" in top and top["predicted_rul"] == top["predicted_rul"]:
    items.append(theme.stat(f"{spec.rul_short} left", insights.life(top["predicted_rul"], spec)))
theme.stats(items)
theme.actions(insights.recommendations(top, state)[:1])
links = st.columns([1, 1, 2])
links[0].page_link("views/overview.py", label="Open fleet overview", icon=":material/grid_view:")
links[1].page_link("views/engine.py", label=f"Open {spec.unit_title.lower()} status", icon=":material/speed:")
st.page_link("views/data_check.py", label="Data check: data profile, recognition and the processing report",
             icon=":material/dataset:")
