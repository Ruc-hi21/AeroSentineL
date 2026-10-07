import streamlit as st

from app import theme
from app.components import band_label, factor_chart, require_result, unit_picker
from app.theme import BAND_COLORS
from src.config import REPORTS_DIR
from src.explainability.sensor_names import describe

theme.page_header("Explainable AI · SHAP attribution", "Explainability",
                  "SHAP values show which sensors pushed each prediction up or down. They show <b>correlation with the "
                  "prediction, not proof of a root cause.</b>")
result = require_result()

row = unit_picker(result.units, key="explain")
left, right = st.columns(2)

with left:
    theme.section("Why this RUL?")
    factors = row.get("rul_factors")
    if isinstance(factors, list):
        theme.chart(factor_chart(factors, "RUL impact (cycles)", "#ff2e4d", "#19f5a0"), key="rul_shap")
        items = "".join(
            f"<li><span>✦ <b>{describe(f['sensor'])}</b> {'lowered' if f['impact'] < 0 else 'raised'} the predicted RUL "
            f"by about <b>{abs(f['impact']):.0f} cycles</b></span></li>" for f in factors[:3])
        theme.card("Top drivers", f"<ul class='as-list'>{items}</ul>")
    else:
        st.warning("No RUL explanation available for this analysis.")

with right:
    theme.section("Why this risk band?")
    factors = row.get("risk_factors")
    if isinstance(factors, list):
        band = band_label(row["risk_band"])
        theme.chart(factor_chart(factors, f"push towards {band} (log-odds)", "#7f95bd",
                                 BAND_COLORS.get(row["risk_band"], "#ff8a1f")), key="risk_shap")
        items = "".join(
            f"<li><span>✦ <b>{describe(f['sensor'])}</b> pushed the prediction "
            f"{'towards' if f['impact'] > 0 else 'away from'} <b>{band}</b></span></li>" for f in factors[:3])
        theme.card("Top drivers", f"<ul class='as-list'>{items}</ul>")
    else:
        st.warning("No risk explanation available for this analysis.")

theme.section("Across the whole validation set")
figures = REPORTS_DIR / "figures"
cols = st.columns(2)
for col, name, caption in [(cols[0], "shap_rul.png", "Average influence on RUL"),
                           (cols[1], "shap_risk.png", "Average influence on risk band")]:
    if (figures / name).exists():
        col.image(str(figures / name), caption=caption)
    else:
        col.info("Run `python -m training.train` to generate this chart.")
