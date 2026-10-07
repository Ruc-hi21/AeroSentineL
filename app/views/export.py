import streamlit as st

from app import theme
from app.components import require_result
from app.theme import esc
from src.export import result_json, units_table

theme.page_header("Data downlink · export results", "Export",
                  "Take the analysis with you: per-unit results, the full cycle-by-cycle history, or everything as JSON.")
result = require_result()
stem = st.session_state.get("source_name", "analysis").rsplit(".", 1)[0]

theme.card("Analysis", f"<ul class='as-list'><li><span>Job</span><span class='as-mono'>{esc(result.job_id)}</span></li>"
           f"<li><span>Model</span><span class='as-mono'>{esc(result.model_version)}</span></li>"
           f"<li><span>Units</span><span class='as-mono'>{len(result.units)}</span></li>"
           f"<li><span>Cycles</span><span class='as-mono'>{len(result.history):,}</span></li></ul>")
st.write("")

cols = st.columns(3)
cols[0].download_button(
    "Unit results (CSV)", units_table(result.units).to_csv(index=False),
    file_name=f"aerosentinel_{stem}_results.csv", mime="text/csv", width="stretch",
    help="One row per engine: health, predicted RUL and range, risk band, top sensors, review flags",
)
cols[1].download_button(
    "Cycle-by-cycle history (CSV)", result.history.to_csv(index=False),
    file_name=f"aerosentinel_{stem}_history.csv", mime="text/csv", width="stretch",
    help="Every cycle: all sensor readings, health score, predicted RUL and risk band",
)
cols[2].download_button(
    "Full result (JSON)", result_json(result),
    file_name=f"aerosentinel_{stem}_{result.job_id}.json", mime="application/json", width="stretch",
    help="Job info, data-quality report, stage statuses and all unit results with explanations",
)

st.caption("Exports are decision-support output, not certified airworthiness determinations.")
