"""RUL and risk: the life estimate, its uncertainty and the four-level risk band."""

import streamlit as st

from app import insights, theme
from app.components import BAND_TEXT, band_label, require_result, review_box, rul_chart, show_table, unit_picker
from app.theme import BAND_COLORS
from src.config import RISK_BANDS, RUL_INTERVAL

theme.page_head("RUL and risk", "XGBoost predicts the cycles left before failure with an 80% range; an XGBoost ensemble "
                "places the engine in one of four risk bands.")
result = require_result()
units = result.units
interval_pct = round((RUL_INTERVAL[1] - RUL_INTERVAL[0]) * 100)

row = unit_picker(units, key="rul")
conf = insights.confidence(row)
items = []
if "predicted_rul" in units:
    items += [theme.stat("Predicted RUL", f"{row['predicted_rul']:.0f}", "cycles", foot=f"latest reading at cycle {int(row['cycle'])}"),
              theme.stat(f"{interval_pct}% range", f"{row['rul_low']:.0f} to {row['rul_high']:.0f}", "cycles",
                         foot=f"end of life between cycle {int(row['cycle']) + round(row['rul_low'])} and {int(row['cycle']) + round(row['rul_high'])}")]
else:
    st.error("RUL prediction failed for this analysis.")
if "risk_band" in units:
    items += [theme.stat("Risk band", BAND_TEXT[row["risk_band"]], color=BAND_COLORS[row["risk_band"]]),
              theme.stat("Band probability", f"{row['risk_probability']:.0%}", foot=f"confidence {conf['level'].lower()}")]
else:
    st.error("Risk classification failed for this analysis.")
theme.stats(items)
review_box(row)

if "predicted_rul" in result.history:
    theme.section("Predicted RUL at every cycle", "dotted lines are the band limits; squares below show the band per cycle")
    unit_history = result.history[result.history["unit"] == row["unit"]].sort_values("cycle")
    theme.chart(rul_chart(unit_history, row), key="rul_curve")
    st.caption("The 80% range is produced for the latest cycle only; earlier cycles show the point estimate.")

theme.section("All engines")
left, right = st.columns([3, 1], vertical_alignment="bottom")
bands = left.multiselect("Risk bands", RISK_BANDS, default=RISK_BANDS, format_func=band_label) \
    if "risk_band" in units else None
review_only = right.toggle("Needs review only")

table = units
if bands is not None:
    table = table[table["risk_band"].isin(bands)]
if review_only:
    table = table[table["needs_review"]]
show_table(insights.add_states(table) if len(table) else table,
           ["Engine", "State", "Cycles", "RUL", "Range", "Band", "Confidence", "Condition", "Flags"])
