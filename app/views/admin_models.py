"""Admin console, model evaluation (for the model analyst): every model's results (Models), where each one is
wrong on its held-out test units (Errors), and which sensors drive it across its training units (Training drivers).
The first two tabs run views/evaluation.py and views/error_analysis.py."""

import runpy
from pathlib import Path

import streamlit as st

from app import theme
from app.components import PROFILE_LABELS, active_subset
from src.components import PROFILES
from src.config import REPORTS_DIR

VIEWS = Path(__file__).resolve().parent
theme.page_head("Model evaluation", "Units are split by engine, cell or bearing, so none appears in both training and "
                "evaluation. Final models are refit on all training units, then scored once on the held-out test set.")
tab_models, tab_errors, tab_drivers = st.tabs(["Models", "Errors", "Training drivers"])
with tab_models:
    runpy.run_path(str(VIEWS / "evaluation.py"), run_name="admin_tab")
with tab_errors:
    runpy.run_path(str(VIEWS / "error_analysis.py"), run_name="admin_tab")
with tab_drivers:
    ready = [p for p in PROFILES if (REPORTS_DIR / p / "figures" / "shap_rul.png").exists()]
    if not ready:
        st.info("Run `python -m training.train` to generate the training figures.")
    else:
        default = active_subset() if active_subset() in ready else ready[0]
        subset = st.pills("Model", ready, default=default, key="drivers_subset", format_func=PROFILE_LABELS.get) or default
        theme.section("Average influence across the training units", "mean |SHAP| per sensor")
        cols = st.columns(2, gap="large")
        figures = REPORTS_DIR / subset / "figures"
        for col, name, caption in [(cols[0], "shap_rul.png", "On the RUL"), (cols[1], "shap_risk.png", "On the risk band")]:
            if (figures / name).exists():
                col.image(str(figures / name), caption=caption)
