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
from app.components import active_spec  # noqa: E402

theme.inject()
st.logo(str(ROOT / "assets" / "logo.svg"), size="large", icon_image=str(ROOT / "assets" / "logo_icon.svg"))

# Information architecture: each simple page answers one question with two or three simple things, and its
# detail page sits right next to it in the same section. Model evaluation is the separate admin console for the
# model analyst, app/admin_app.py, on its own port. The unit section is named after the loaded component.
VIEWS = ROOT / "app" / "views"
unit = active_spec().unit_title
pages = {
    "Fleet": [
        st.Page(VIEWS / "overview.py", title="Fleet overview", icon=":material/grid_view:", default=True),
        st.Page(VIEWS / "fleet_detail.py", title="Fleet details", icon=":material/table_chart:"),
        st.Page(VIEWS / "upload.py", title="Ingest data", icon=":material/upload:"),
    ],
    unit: [
        st.Page(VIEWS / "engine.py", title=f"{unit} status", icon=":material/speed:", url_path="engine"),
        st.Page(VIEWS / "health.py", title="Degradation", icon=":material/trending_down:"),
        st.Page(VIEWS / "rul_risk.py", title=f"{active_spec().rul_short} and risk", icon=":material/timelapse:"),
        st.Page(VIEWS / "explainability.py", title="Explanations", icon=":material/account_tree:"),
        st.Page(VIEWS / "twin.py", title="3D model", icon=":material/view_in_ar:"),
    ],
    "Output": [
        st.Page(VIEWS / "export.py", title="Export", icon=":material/download:"),
    ],
}

theme.motion()
st.navigation(pages).run()
