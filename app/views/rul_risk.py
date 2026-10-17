"""RUL and risk, the maintainer view: time left, which of the four risk bands the unit is in, and how the
forecast moved over its life. The forecast range at every reading and every unit's band are in Admin, RUL history."""

import streamlit as st

from app import insights, theme
from app.components import require_result, review_box, simple_rul_chart, unit_picker
from app.theme import BAND_COLORS, BAND_TEXT
from src.config import RISK_BANDS

result = require_result()
spec = result.spec
noun = spec.actions.get("noun", "unit")
life_word = spec.rul_short if spec.has_life else "Condition margin"
theme.page_head(f"{spec.rul_short} and risk", f"How long this {noun} has left, and how risky that is."
                if spec.has_life else f"How much condition margin the weakest part of this {noun} has left, and how risky that is.")

row = unit_picker(result.units, key="rul")
has_rul = "predicted_rul" in row and row["predicted_rul"] == row["predicted_rul"]
band = row.get("risk_band") if isinstance(row.get("risk_band"), str) else None

# 1. Time left, in words.
theme.section(f"1. {life_word} left")
items = []
if has_rul:
    items += [theme.stat("Best estimate", insights.life(row["predicted_rul"], spec)),
              theme.stat("Likely range", f"{insights.life(row['rul_low'], spec)} to {insights.life(row['rul_high'], spec)}",
                         foot="8 times out of 10 the true value falls inside")]
if band:
    items.append(theme.stat("Risk", BAND_TEXT[band], color=BAND_COLORS[band], foot=f"the model is {row['risk_probability']:.0%} sure"))
if items:
    theme.stats(items)
else:
    st.error("No prediction is available for this analysis.")
review_box(row)

# 2. The four risk bands, with this unit's band marked.
theme.section("2. Where it sits on the risk ladder", f"bands by {insights.life_word(spec)} left")
limits = spec.risk_limits
ranges = {"FAILURE_LIKELY": f"{insights.life(limits['FAILURE_LIKELY'], spec)} or less",
          "HIGH_RISK": f"up to {insights.life(limits['HIGH_RISK'], spec)}",
          "AT_RISK": f"up to {insights.life(limits['AT_RISK'], spec)}",
          "NORMAL": f"more than {insights.life(limits['AT_RISK'], spec)}"}
theme.stats([theme.stat(BAND_TEXT[b], "This one" if b == band else "", foot=ranges[b],
                        color=BAND_COLORS[b] if b == band else None)
             for b in reversed(RISK_BANDS)])

# 3. How the forecast moved over the unit's life.
if has_rul and "predicted_rul" in result.history:
    theme.section(f"3. {life_word} left over time", f"one point per {spec.time_title.lower()}")
    hist = result.history[result.history["unit"] == row["unit"]].sort_values("cycle")
    theme.chart(simple_rul_chart(hist, spec), key="rul_simple")
    theme.note(f"The line falls as the {noun} wears and crosses into the coloured bands as the risk rises.")

st.page_link("views/admin_rul.py", label="RUL history (admin): forecast range per reading and every unit's band",
             icon=":material/admin_panel_settings:")
