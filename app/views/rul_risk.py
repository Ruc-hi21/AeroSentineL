"""RUL and risk, the timing page: how long the unit has left, when to service it and how sure the model is; then
the forecast over its life, the probability of each risk band, and a deferral check: drag the next scheduled
check along the time axis and read the chance the unit reaches end of life first."""

import streamlit as st

from app import insights, theme
from app.components import band_bars, failure_curve, model_trust, require_result, review_box, simple_rul_chart, unit_picker
from app.theme import BAND_COLORS, BAND_TEXT, STATES, esc

result = require_result()
spec = result.spec
noun = spec.actions.get("noun", "unit")
t = spec.time_title.lower()
life_word = spec.rul_short if spec.has_life else "Condition margin"
theme.page_head(f"{spec.rul_short} and risk", f"How long this {noun} has left, when to act, and whether it can wait."
                if spec.has_life else f"How much condition margin the weakest part of this {noun} has left, and how risky that is.",
                kicker=f"{spec.name} · timing")

pick, _, help_col = st.columns([3.2, 4.0, 1.8], vertical_alignment="bottom")
with pick:
    row = unit_picker(result.units, key="rul")
with help_col:
    theme.guide([
        ("Best estimate", f"The model's single forecast of the {insights.life_word(spec)} left."),
        ("Likely range", "The range the model is 80% sure of. The footnote says how often it held the true value in test."),
        ("Risk band", "Normal, At risk, High risk or Failure likely, with the classifier's probability for each."),
        ("Deferral check", "Drag the slider to the next scheduled check: the curve gives the chance of reaching end of life first."),
    ])
has_rul = "predicted_rul" in row and row["predicted_rul"] == row["predicted_rul"]
band = row.get("risk_band") if isinstance(row.get("risk_band"), str) else None
trust = model_trust(result)

# Time left, the range around it, when to service, and the risk band.
theme.section(f"{spec.rul_long} estimate", f"at its latest reading, {t} {int(row['cycle'])}", kicker="Estimate")
items = []
if has_rul:
    covered = (f"held the true value for {trust['covered']} of {insights.count(trust['units'], spec)} in test"
               if trust and trust["covered"] is not None else "the model's 80% range")
    width = (float(row["rul_high"]) - float(row["rul_low"])) / spec.rul_cap
    items += [theme.stat("Best estimate", insights.life(row["predicted_rul"], spec), meter=float(row["predicted_rul"]) / spec.rul_cap,
                         foot=f"of a {insights.life(spec.rul_cap, spec)} ceiling",
                         tip=f"The model's single forecast. The bar shows it against the most the model can report, "
                             f"{insights.life(spec.rul_cap, spec)}."),
              theme.stat("Likely range", f"{row['rul_low']:.0f} to {insights.life(row['rul_high'], spec)}", foot=covered,
                         tip=f"The model is 80% sure the true value is in this range. It spans {width:.0%} of the scale: "
                             "a narrow range means a confident forecast.")]
service = insights.service_by(row)
if service:
    reading, left = service
    items.append(theme.stat("Service by", f"{spec.time_title} {reading}" if left else "Now",
                            foot=f"{insights.life(left, spec)} away" if left else "the low end of the range is reached",
                            tip="The unit's age plus the low end of the likely range: the cautious date to plan the work for."))
if band:
    items.append(theme.stat("Risk band", BAND_TEXT[band], color=BAND_COLORS[band], meter=row["risk_probability"],
                            foot=f"model is {row['risk_probability']:.0%} sure",
                            tip=f"The classifier's band for this {noun}: {insights.band_window(spec, band)}. The bar is its probability."))
if items:
    theme.stats(items)
else:
    st.error("No prediction is available for this analysis.")
if insights.at_cap(row):
    theme.note(f"The forecast is at the model's ceiling of {insights.life(spec.rul_cap, spec)}: read it as "
               f"{insights.life(spec.rul_cap, spec)} or more.")
review_box(row)

# How the forecast moved, next to how the model spreads its belief over the four bands.
left_col, right_col = st.columns([1.2, 1], gap="large")
with left_col:
    theme.section("Forecast trajectory", f"one forecast per {t}, on the four risk bands", kicker="History")
    if has_rul and "predicted_rul" in result.history:
        hist = result.history[result.history["unit"] == row["unit"]].sort_values("cycle")
        theme.chart(simple_rul_chart(hist, spec), key="rul_simple")
    else:
        st.info("No forecast is available for this analysis.")
with right_col:
    theme.section("Risk band probability", "the predicted band is solid", kicker="Classifier")
    if band and insights.failure_outlook(row):
        theme.chart(band_bars(row, spec), key="rul_band_bars")
    else:
        st.info("No risk band is available for this analysis.")

# Can it wait: the chance of reaching end of life before a check the maintainer names.
reach = spec.risk_limits["AT_RISK"]
if spec.has_life and insights.failure_chance(row, reach) is not None:
    theme.section("Deferral check", "can it wait until the next scheduled check?", kicker="Planning")
    left_col, right_col = st.columns([1, 1.2], gap="large")
    with left_col:
        n = st.slider(f"Next scheduled check, {spec.life_unit} from the latest reading", min_value=1, max_value=reach,
                      value=spec.risk_limits["HIGH_RISK"], step=1, key=f"rul_next_check_{spec.key}")
        p = insights.failure_chance(row, n)
        verdict, title, why = insights.defer_verdict(p, insights.engine_state(row))
        theme.stats([theme.stat("End of life before the check", insights.chance(p), meter=p, color=STATES[verdict]["color"],
                                foot=f"within {insights.life(n, spec)}"),
                     theme.stat("Verdict", title, color=STATES[verdict]["color"])])
        theme.note(esc(why))
    with right_col:
        theme.chart(failure_curve(row, spec, int(n)), key="rul_failure_curve")
    theme.note("From the band probabilities and the likely range. The cut-offs are a design choice, not a validated "
               "standard; confirm against approved maintenance data before deferring work.")
