"""AeroSentinel admin console, for the model analyst: how good every model is and where it is wrong.

A separate app from the user dashboard, on its own port. Run from the repo root:
    streamlit run app/admin_app.py --server.port 8502
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # `streamlit run` only puts app/ on the path
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="AeroSentinel admin", page_icon=str(ROOT / "assets" / "logo_icon.svg"),
                   layout="wide", initial_sidebar_state="expanded")

from app import theme  # noqa: E402
from app.components import sidebar_status  # noqa: E402

theme.inject()
st.logo(str(ROOT / "assets" / "logo.svg"), size="large", icon_image=str(ROOT / "assets" / "logo_icon.svg"))

# Model analysis only: every model's results, its errors on held-out units and what drives it in training.
# Everything about the loaded data and the units is in the user dashboard (app/streamlit_app.py).
VIEWS = ROOT / "app" / "views"
pages = {
    "Admin": [
        st.Page(VIEWS / "admin_models.py", title="Model evaluation", icon=":material/fact_check:", default=True),
    ],
}

sidebar_status()
theme.motion()
st.navigation(pages).run()
