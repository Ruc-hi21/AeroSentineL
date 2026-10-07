"""Explanations: which sensors pushed each prediction, per engine and across the training data."""

import streamlit as st

from app import theme
from app.components import band_label, factor_chart, require_result, unit_picker
from app.theme import BAND_COLORS, TOKENS
from src.config import REPORTS_DIR
from src.explainability.sensor_names import describe

theme.page_head("Explanations", "SHAP values show which sensors pushed each prediction up or down. They show correlation "
                "with the prediction, not proof of a root cause.")
result = require_result()

row = unit_picker(result.units, key="explain")
left, right = st.columns(2, gap="large")

with left:
    theme.section("Why this RUL", "contribution in cycles")
    factors = row.get("rul_factors")
    if isinstance(factors, list):
        theme.chart(factor_chart(factors, "change in predicted RUL (cycles)", "#ff832b", TOKENS["accent"]), key="rul_shap")
        theme.actions([{"action": describe(f["sensor"]),
                        "why": f"{'Shortened' if f['impact'] < 0 else 'Extended'} the predicted life by about "
                               f"{abs(f['impact']):.0f} cycles."} for f in factors[:3]])
    else:
        st.warning("No RUL explanation available for this analysis.")

with right:
    factors = row.get("risk_factors")
    band = band_label(row["risk_band"]) if "risk_band" in row else ""
    theme.section("Why this risk band", f"push towards {band.lower()}, log-odds")
    if isinstance(factors, list):
        theme.chart(factor_chart(factors, f"push towards {band.lower()} (log-odds)", TOKENS["text_3"],
                                 BAND_COLORS.get(row["risk_band"], TOKENS["accent"])), key="risk_shap")
        theme.actions([{"action": describe(f["sensor"]),
                        "why": f"Pushed the prediction {'towards' if f['impact'] > 0 else 'away from'} {band.lower()}."}
                       for f in factors[:3]])
    else:
        st.warning("No risk explanation available for this analysis.")

with st.expander("Average influence across training engines (training report figures)"):
    figures = REPORTS_DIR / "figures"
    cols = st.columns(2)
    for col, name, caption in [(cols[0], "shap_rul.png", "Average influence on RUL"),
                               (cols[1], "shap_risk.png", "Average influence on the risk band")]:
        if (figures / name).exists():
            col.image(str(figures / name), caption=caption)
        else:
            col.info("Run `python -m training.train` to generate this figure.")
