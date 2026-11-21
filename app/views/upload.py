"""Ingest data: the five component models, a centred drop zone (or a bundled sample), a pre-flight animation while the
file is processed, then the file itself: a confirmation and the uploaded table. What the analysis found is on
Fleet details."""

import io
import time

import streamlit as st

from app import theme
from app.components import SAMPLES, get_result, history_store, require_model, run_analysis, sample_choice, sample_truth
from app.theme import esc
from src.components import COMPONENTS
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


def records_html(records, spec):
    """What the past-records database did for this analysis: history joined per unit, rows saved, or why not."""
    if not records:
        return ""
    t = spec.time_title.lower()
    parts = [f'<span class="db">{esc(records["backend"])}</span>']
    for unit, j in records["joined"].items():
        parts.append(f'<span>joined <b>{j["cycles"]:,}</b> stored {t}s of {esc(spec.label(unit))} '
                     f'({j["from"]:g}–{j["to"]:g})</span>')
    if records["stored"]:
        parts.append(f'<span>saved <b>{records["stored"]:,}</b> {t}s for next time</span>')
    if records["error"]:
        parts.append(f'<span class="err">{esc(records["error"])}</span>')
    return f'<div class="as-rec">{"".join(parts)}</div>'


def records_table(store):
    """Units on record, newest first."""
    try:
        summary = store.summary()
    except Exception:  # noqa: BLE001
        return None
    if summary.empty:
        return summary
    summary["component"] = summary["component"].map(lambda k: COMPONENTS[k].name if k in COMPONENTS else k)
    return (summary.sort_values("stored_at", ascending=False)
            .rename(columns={"component": "Component", "fleet": "Fleet", "unit": "Unit", "cycles": "Records",
                             "last_cycle": "Latest", "stored_at": "Last upload"}))


def columns_html(spec):
    """Every column a file of this component needs, in order, grouped, each with its sensor name and unit.
    Built from the component's own definition (src/components/), so it always matches what the models read."""
    def chip(key, label, cls=""):
        return f'<span class="c {cls}" title="{esc(label)}"><code>{esc(key)}</code>{esc(label)}</span>'

    layout = ("<b>NASA C-MAPSS .txt</b> (no header, columns in this order) or <b>.csv</b> with these headers"
              if spec.key == "turbofan" else "<b>.csv</b> with these headers, one row per " + esc(spec.time_title.lower()))
    groups = [
        ("Identifier and age", [chip(spec.id_column, spec.unit_title, "id"), chip(spec.time_column, spec.time_title, "id")]),
    ]
    if spec.settings:
        groups.append(("Operating settings", [chip(k, label, "set") for k, label in zip(spec.settings, spec.setting_labels)]))
    groups.append((f"Sensors · {len(spec.channels)}", [chip(c.key, f"{c.code} · {c.name}" + (f" ({c.unit})" if c.unit else ""))
                                                       for c in spec.channels]))
    body = "".join(f'<div class="g">{esc(name)}</div><div class="chips">{"".join(chips)}</div>' for name, chips in groups)
    return f'<div class="as-cols"><div class="fmt">{layout} · {len(spec.upload_columns)} columns</div>{body}</div>'


theme.page_head("Ingest data", kicker="Data intake")
require_model()

_, mid, _ = st.columns([1, 2.4, 1])
with mid:
    # The five component models, live: all ready, or the loaded file's component lit.
    loaded = get_result()
    current = loaded.spec.key if loaded is not None and loaded.units is not None else None
    store = history_store()
    st.html(theme.readiness(
        [(k, s.name, "ready" if current is None else "on" if k == current else "dim") for k, s in COMPONENTS.items()],
        "5 models online" if current is None else f"Loaded · <b>{esc(st.session_state.get('source_name', ''))}</b>",
        f".txt · .csv · up to {esc(MAX_UPLOAD)} · records: <b>{esc(store.backend) if store else 'off'}</b>"))

    with st.container(key="ingest_drop"):
        uploaded = st.file_uploader("Sensor data file (.txt or .csv)", type=["txt", "csv"], label_visibility="collapsed")
    st.html('<div class="as-or">or try a sample</div>')
    s_left, s_right = st.columns([3, 1.2], vertical_alignment="bottom")
    with s_left:
        sample = sample_choice("ingest_sample", label="Sample")
    with s_right:
        use_sample = st.button("Use this sample", key="use_sample", width="stretch")
    truth = sample_truth(sample)
    if truth:
        st.caption(f"True remaining life: {truth}")
    if store is not None:
        with st.expander("Past records"):
            records = records_table(store)
            if records is None:
                st.warning("The records database could not be reached.")
            elif records.empty:
                st.caption("Nothing stored yet. Each analysed file is kept here, and a later file for the same unit is "
                           "joined to it before scoring.")
            else:
                st.dataframe(records, hide_index=True, width="stretch", height=min(36 * (len(records) + 1) + 4, 320),
                             column_config={"Last upload": st.column_config.DatetimeColumn(format="D MMM YYYY, HH:mm")})
    with st.expander("Required columns, per component"):
        tabs = st.tabs([s.name for s in COMPONENTS.values()])
        for tab, (key, spec) in zip(tabs, COMPONENTS.items()):
            with tab:
                st.html(columns_html(spec))
                st.download_button("Download a template", data=",".join(spec.upload_columns) + "\n",
                                   file_name=f"{key}_template.csv", mime="text/csv", key=f"template_{key}",
                                   icon=":material/download:")

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
st.html(records_html(result.records, result.spec))
st.page_link("views/fleet_detail.py", label="See what the analysis found on Fleet details", icon=":material/table_chart:")
shown = len(table) <= SHOW_ROWS
theme.section("Uploaded data", "every row of the file, as it was read" if shown else
              f"the first {SHOW_ROWS:,} of {len(table):,} rows; the analysis used every row", kicker="Dataset")
st.dataframe(table if shown else table.head(SHOW_ROWS), hide_index=True, width="stretch", height=560)
