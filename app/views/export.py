"""Export: take the analysis out as CSV or JSON."""

import streamlit as st

from app import theme
from app.components import require_result
from app.theme import esc
from src.export import result_json, units_table

theme.page_head("Export", "Download the current analysis for reporting or further work.")
result = require_result()
stem = st.session_state.get("source_name", "analysis").rsplit(".", 1)[0]

theme.kv([("Job", f"<code>{esc(result.job_id)}</code>"), ("Model", esc(result.model_version)),
          ("Engines", str(len(result.units))), ("Cycles", f"{len(result.history):,}")])

theme.section("Files")
cols = st.columns(3, gap="medium")
with cols[0]:
    st.download_button("Engine results (CSV)", units_table(result.units).to_csv(index=False),
                       file_name=f"aerosentinel_{stem}_results.csv", mime="text/csv", width="stretch")
    theme.note("One row per engine: health, predicted RUL and range, risk band, top sensors, review flags.")
with cols[1]:
    st.download_button("Cycle history (CSV)", result.history.to_csv(index=False),
                       file_name=f"aerosentinel_{stem}_history.csv", mime="text/csv", width="stretch")
    theme.note("Every cycle: all sensor readings, health score, predicted RUL and risk band.")
with cols[2]:
    st.download_button("Full result (JSON)", result_json(result),
                       file_name=f"aerosentinel_{stem}_{result.job_id}.json", mime="application/json", width="stretch")
    theme.note("Job information, data-quality report, stage statuses and all engine results with explanations.")

theme.note("Exports are decision-support output, not certified airworthiness determinations.")
