"""AeroSentinel dashboard.

Run from the repo root:  streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # `streamlit run` only puts app/ on the path
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="AeroSentinel · Mission Control", page_icon=str(ROOT / "assets" / "logo_icon.svg"),
                   layout="wide", initial_sidebar_state="expanded")

from app import theme  # noqa: E402
from app.components import sidebar_status  # noqa: E402

theme.inject()
st.logo(str(ROOT / "assets" / "logo.svg"), size="large", icon_image=str(ROOT / "assets" / "logo_icon.svg"))

VIEWS = ROOT / "app" / "views"
pages = {
    "Command": [
        st.Page(VIEWS / "overview.py", title="Mission Control", icon=":material/radar:", default=True),
        st.Page(VIEWS / "upload.py", title="Upload & Analyze", icon=":material/upload_file:"),
    ],
    "Engine Intelligence": [
        st.Page(VIEWS / "twin.py", title="3D Digital Twin", icon=":material/view_in_ar:"),
        st.Page(VIEWS / "health.py", title="Component Health", icon=":material/monitor_heart:"),
        st.Page(VIEWS / "rul_risk.py", title="RUL & Risk", icon=":material/timer:"),
        st.Page(VIEWS / "explainability.py", title="Explainability", icon=":material/psychology:"),
    ],
    "Model": [
        st.Page(VIEWS / "evaluation.py", title="Model Evaluation", icon=":material/insights:"),
        st.Page(VIEWS / "error_analysis.py", title="Error Analysis", icon=":material/troubleshoot:"),
    ],
    "Output": [
        st.Page(VIEWS / "export.py", title="Export", icon=":material/download:"),
    ],
}

sidebar_status()
st.navigation(pages).run()
