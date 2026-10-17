"""AeroSentinel dashboard.

Run from the repo root:  streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # `streamlit run` only puts app/ on the path
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="AeroSentinel", page_icon=str(ROOT / "assets" / "logo_icon.svg"),
                   layout="wide", initial_sidebar_state="expanded")

from app import theme  # noqa: E402
from app.components import active_spec, sidebar_status  # noqa: E402

theme.inject()
st.logo(str(ROOT / "assets" / "logo.svg"), size="large", icon_image=str(ROOT / "assets" / "logo_icon.svg"))

# Information architecture: the maintainer's pages answer one question each with two or three simple things
# (which units need attention, then for one unit: condition and action, wear, time left and risk, why, where).
# Everything detailed (history charts, data checks, model evaluation, exports) sits in the Admin block.
# The unit section is named after the loaded component (Engine, Cell, Gearbox, ...).
VIEWS = ROOT / "app" / "views"
unit = active_spec().unit_title
pages = {
    "Fleet": [
        st.Page(VIEWS / "overview.py", title="Fleet overview", icon=":material/grid_view:", default=True),
        st.Page(VIEWS / "upload.py", title="Ingest data", icon=":material/upload:"),
    ],
    unit: [
        st.Page(VIEWS / "engine.py", title=f"{unit} status", icon=":material/speed:", url_path="engine"),
        st.Page(VIEWS / "health.py", title="Degradation", icon=":material/trending_down:"),
        st.Page(VIEWS / "rul_risk.py", title=f"{active_spec().rul_short} and risk", icon=":material/timelapse:"),
        st.Page(VIEWS / "explainability.py", title="Explanations", icon=":material/account_tree:"),
        st.Page(VIEWS / "twin.py", title="3D model", icon=":material/view_in_ar:"),
    ],
    "Admin": [
        st.Page(VIEWS / "admin_fleet.py", title="Fleet detail", icon=":material/table_chart:"),
        st.Page(VIEWS / "admin_engine.py", title=f"{unit} detail", icon=":material/monitor_heart:"),
        st.Page(VIEWS / "admin_degradation.py", title="Sensor history", icon=":material/show_chart:"),
        st.Page(VIEWS / "admin_rul.py", title="RUL history", icon=":material/history:"),
        st.Page(VIEWS / "admin_explanations.py", title="Explanation detail", icon=":material/insights:"),
        st.Page(VIEWS / "admin_data.py", title="Data check", icon=":material/dataset:"),
        st.Page(VIEWS / "evaluation.py", title="Model evaluation", icon=":material/fact_check:"),
        st.Page(VIEWS / "error_analysis.py", title="Error analysis", icon=":material/rule:"),
        st.Page(VIEWS / "export.py", title="Export", icon=":material/download:"),
    ],
}

sidebar_status()
theme.motion()
st.navigation(pages, expanded=True).run()  # show the whole Admin block
