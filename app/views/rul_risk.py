import streamlit as st

from app import theme
from app.components import band_label, require_result, review_box, rul_chart, show_table, unit_banner, unit_picker
from app.theme import BAND_COLORS
from src.config import RISK_BANDS, RUL_CAP, RUL_INTERVAL

theme.page_header("Prognostics · remaining useful life", "RUL & Risk",
                  "XGBoost predicts how many cycles each engine has left, with an 80% range, and an XGBoost ensemble "
                  "places it in one of four risk bands.")
result = require_result()
units = result.units
interval_pct = round((RUL_INTERVAL[1] - RUL_INTERVAL[0]) * 100)

row = unit_picker(units, key="rul")
unit_banner(row)

gauges = []
if "predicted_rul" in units:
    color = BAND_COLORS.get(row.get("risk_band"), theme.CYAN)
    gauges.append(theme.gauge("Predicted RUL", row["predicted_rul"] / RUL_CAP, f"{row['predicted_rul']:.0f}", color,
                              "cycles until failure"))
    gauges.append(theme.gauge(f"{interval_pct}% range", (row["rul_high"] - row["rul_low"]) / RUL_CAP,
                              f"{row['rul_low']:.0f}–{row['rul_high']:.0f}", theme.VIOLET, "prediction interval"))
else:
    st.error("RUL prediction failed for this analysis.")
if "risk_band" in units:
    color = BAND_COLORS[row["risk_band"]]
    gauges.append(theme.gauge("Risk band", (RISK_BANDS.index(row["risk_band"]) + 1) / 4,
                              band_label(row["risk_band"]).split(" ", 1)[1].upper(), color, "4-band classification"))
    gauges.append(theme.gauge("Confidence", row["risk_probability"], f"{row['risk_probability']:.0%}", color,
                              "probability of the chosen band"))
else:
    st.error("Risk classification failed for this analysis.")
theme.gauge_row(gauges)
review_box(row)

if "predicted_rul" in result.history:
    theme.section("Predicted RUL at every cycle", "dotted lines = risk-band limits")
    unit_history = result.history[result.history["unit"] == row["unit"]]
    theme.chart(rul_chart(unit_history), key="rul_curve")
    st.caption("The coloured strip along the bottom is the risk band the model assigned at each cycle.")

theme.section("All units")
left, right = st.columns([3, 1])
bands = left.multiselect("Risk bands", RISK_BANDS, default=RISK_BANDS, format_func=band_label) \
    if "risk_band" in units else None
review_only = right.toggle("Needs review only")

table = units
if bands is not None:
    table = table[table["risk_band"].isin(bands)]
if review_only:
    table = table[table["needs_review"]]
if "predicted_rul" in table:
    table = table.sort_values("predicted_rul")
show_table(table, ["unit", "cycle", "predicted_rul", "rul_low", "rul_high", "risk",
                   "risk_probability", "health", "review"])
