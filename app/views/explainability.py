"""Explanations, the maintainer view: in one sentence, a short chart and three plain lines, which sensors made
the model predict this. The risk-band explanation and training-set averages are in Admin, explanation detail."""

import streamlit as st

from app import insights, theme
from app.components import factor_chart, reason_text, require_result, unit_picker
from app.theme import TOKENS, esc

result = require_result()
spec = result.spec
noun = spec.actions.get("noun", "unit")
theme.page_head("Explanations", f"Which sensors made the model predict this {insights.life_word(spec)} for this {noun}. "
                "It shows what the model relied on, not a confirmed root cause.")

row = unit_picker(result.units, key="explain")
factors = row.get("rul_factors")
if not isinstance(factors, list) or not factors:
    st.info("No explanation is available for this analysis.")
    st.stop()

# 1. In one sentence.
names = [reason_text(f, spec)[0] for f in factors[:2]]
shorten = [f for f in factors if f["impact"] < 0]
theme.section("1. In one sentence")
theme.note(f"The forecast is driven mostly by <b>{esc(names[0])}</b>" + (f" and <b>{esc(names[1])}</b>" if len(names) > 1 else "")
           + (f"; {len(shorten)} of the top {len(factors)} sensors are shortening the predicted {insights.life_word(spec)}."
              if shorten else f"; none of the top sensors is shortening the predicted {insights.life_word(spec)}."))

left, right = st.columns([1.3, 1], gap="large")
with left:
    # 2. The top sensors as bars: left = shortened the life, right = lengthened it.
    theme.section("2. Top sensors", f"change in predicted {insights.life_word(spec)}, {spec.life_unit}")
    theme.chart(factor_chart(factors, f"change in predicted {insights.life_word(spec)} ({spec.life_unit})", "#ff832b",
                             TOKENS["accent"]), key="explain_simple")
    theme.note("Orange bars pointing left shortened the predicted life; blue bars pointing right lengthened it.")
with right:
    # 3. The top three in words.
    theme.section("3. In plain words")
    theme.actions([{"action": what, "why": why} for what, why in (reason_text(f, spec) for f in factors[:3])])

