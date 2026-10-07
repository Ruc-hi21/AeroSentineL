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
from app.components import sidebar_status  # noqa: E402

theme.inject()
st.logo(str(ROOT / "assets" / "logo.svg"), size="large", icon_image=str(ROOT / "assets" / "logo_icon.svg"))

# Information architecture follows the operator's questions: which engines need attention
# (Fleet), then for one engine: condition, change, time left, risk, action (Engine).
VIEWS = ROOT / "app" / "views"
pages = {
    "Fleet": [
        st.Page(VIEWS / "overview.py", title="Fleet overview", icon=":material/grid_view:", default=True),
        st.Page(VIEWS / "upload.py", title="Ingest data", icon=":material/upload:"),
    ],
    "Engine": [
        st.Page(VIEWS / "engine.py", title="Engine status", icon=":material/speed:"),
        st.Page(VIEWS / "health.py", title="Degradation", icon=":material/trending_down:"),
        st.Page(VIEWS / "rul_risk.py", title="RUL and risk", icon=":material/timelapse:"),
        st.Page(VIEWS / "explainability.py", title="Explanations", icon=":material/account_tree:"),
        st.Page(VIEWS / "twin.py", title="3D model", icon=":material/view_in_ar:"),
    ],
    "Model": [
        st.Page(VIEWS / "evaluation.py", title="Evaluation", icon=":material/fact_check:"),
        st.Page(VIEWS / "error_analysis.py", title="Error analysis", icon=":material/rule:"),
    ],
    "Output": [
        st.Page(VIEWS / "export.py", title="Export", icon=":material/download:"),
    ],
}

sidebar_status()
st.navigation(pages).run()
