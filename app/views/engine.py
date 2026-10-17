"""Unit status: one page for one unit. On top, its condition and time left, what to do and why, in plain words;
below, the detail in four tabs: the component schematic, the forecast (with failure outlook and can-it-wait),
every sensor's drift, and the SHAP explanation of the RUL and of the risk band."""

import streamlit as st

from app import insights, theme
from app.components import (
    drift_bars, drift_table, factor_chart, reason_text, require_model, require_result, rul_chart, step_unit,
    unit_picker,
)
from app.instruments import gas_path, gas_path_payload
from app.theme import BAND_COLORS, BAND_TEXT, STATES, TOKENS, esc

artifacts = require_model()
result = require_result()
units = result.units
spec = result.spec
noun = spec.actions.get("noun", "unit")
t = spec.time_title.lower()
theme.page_head(f"{spec.unit_title} status", f"Is this {noun} all right, how long has it got, what should be done, and why.",
                f"<b>{esc(st.session_state.get('source_name', ''))}</b><br>{insights.count(len(units), spec)}, "
                f"model {esc(result.model_version)} {esc(result.subset or '')}")

pick, prev, nxt, _ = st.columns([3.2, 0.7, 0.7, 4.4], vertical_alignment="bottom")
with pick:
    row = unit_picker(units, key="engine", label=f"{spec.unit_title} (most urgent first)")
prev.button("Previous", key="engine_prev", on_click=step_unit, args=(units, "engine", -1), width="stretch")
nxt.button("Next", key="engine_next", on_click=step_unit, args=(units, "engine", 1), width="stretch")

unit = int(row["unit"])
hist = result.history[result.history["unit"] == unit].sort_values("cycle")
drift = insights.sensor_drift(hist, artifacts.health)
state = insights.engine_state(row)
has_rul = "predicted_rul" in row and row["predicted_rul"] == row["predicted_rul"]

# 1. Condition and time left.
theme.section(f"1. Condition and {insights.life_word(spec)} left", f"at its latest reading, {t} {int(row['cycle'])}")
items = [theme.stat("Condition", STATES[state]["label"], color=STATES[state]["color"])]
if has_rul:
    items.append(theme.stat(f"{spec.rul_short} left", insights.life(row["predicted_rul"], spec),
                            foot=f"likely between {insights.life(row['rul_low'], spec)} and {insights.life(row['rul_high'], spec)}"))
if isinstance(row.get("risk_band"), str):
    items.append(theme.stat("Risk", BAND_TEXT[row["risk_band"]], color=BAND_COLORS[row["risk_band"]],
                            foot=f"the model is {row['risk_probability']:.0%} sure"))
hot = int(drift["status"].isin(["Critical", "Warning"]).sum())
items.append(theme.stat("Sensors drifting", f"{hot} of {len(drift)}", foot="beyond 2.4 standard deviations",
                        color=STATES["WARNING"]["color"] if hot else None))
theme.stats(items)
theme.note(esc(insights.state_reason(row, state)))
found = insights.parts(row)
if found:  # hydraulic: the condition of each assessed part
    sev = {0: "HEALTHY", 1: "DEGRADING", 2: "WARNING", 3: "CRITICAL"}
    theme.stats([theme.stat(p["name"], p["label"], foot=f"{p['p']:.0%} confidence",
                            color=STATES[sev[p["severity"]]]["color"]) for p in found])
    if spec.not_assessed:
        theme.note(esc(spec.not_assessed))

left, right = st.columns(2, gap="large")
with left:
    theme.section("2. What to do")
    theme.actions(insights.recommendations(row, state, drift)[:3])
with right:
    theme.section("3. Why", "the three sensors that moved the prediction most")
    factors = row.get("rul_factors")
    if isinstance(factors, list) and factors:
        theme.actions([{"action": what, "why": why} for what, why in (reason_text(f, spec) for f in factors[:3])])
    else:
        st.info("No explanation is available for this analysis.")
theme.note("Guidance from AeroSentinel's risk limits and sensor drift. Confirm against approved maintenance data before acting.")

# Detail.
tab_schematic, tab_forecast, tab_sensors, tab_why = st.tabs(
    ["Schematic", f"{spec.rul_short} forecast", "Sensor drift", "Explanation"])

with tab_schematic:
    gas_path(gas_path_payload(row, drift, hist, result.profile), key="engine_gas_path")
    theme.note("Each part takes the colour of its predicted condition; hover a part for its readings." if spec.diagnosis else
               "Each part takes the colour of its most-drifted sensor; hover a part for its readings. Shading shows where "
               "the evidence is measured, not a confirmed root cause.")

with tab_forecast:
    if has_rul and "predicted_rul" in result.history:
        theme.section(f"{spec.rul_short} at every {t}", f"band limits dotted; the 80% range is for the latest {t}; "
                      f"squares show the band per {t}")
        theme.chart(rul_chart(hist, row), key="engine_rul_chart")
    outlook = insights.failure_outlook(row)
    if outlook:
        added = {"FAILURE_LIKELY": "failure-likely band", "HIGH_RISK": "adds the high-risk band", "AT_RISK": "adds the at-risk band"}
        left, right = st.columns(2, gap="large")
        with left:
            theme.section("Failure outlook" if spec.has_life else "Margin outlook",
                          "chance of reaching each risk window, from the four band probabilities")
            theme.stats([theme.stat(f"Within {insights.life(o['limit'], spec)}", insights.chance(o["p"]), foot=added[o["band"]])
                         for o in outlook])
        with right:
            if spec.has_life:
                theme.section("Can it wait until the next check?")
                reach = spec.risk_limits["AT_RISK"]
                n = st.number_input(f"Next scheduled check, {spec.life_unit} from the latest reading", min_value=1,
                                    max_value=reach, value=spec.risk_limits["HIGH_RISK"], step=1,
                                    key=f"engine_next_check_{spec.key}")
                p = insights.failure_chance(row, n)
                verdict, title, why = insights.defer_verdict(p, state)
                theme.stats([theme.stat("Chance of reaching end of life first", insights.chance(p),
                                        foot=f"within {insights.life(n, spec)}"),
                             theme.stat("Verdict", title, color=STATES[verdict]["color"])])
                theme.note(esc(why))

with tab_sensors:
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        theme.section("Drift now", f"every sensor at {t} {int(row['cycle'])}, strongest first")
        theme.chart(drift_bars(drift, spec), key="engine_drift_bars")
    with right:
        theme.section("Drift table", "latest value, drift, peak and recent trend")
        drift_table(drift, compact=True, unit=spec.life_unit)
    theme.note("Drift is how many standard deviations a reading sits from a healthy one, in the direction wear pushes "
               "that sensor. Elevated from 1.6, warning from 2.4, critical from 3.2.")

with tab_why:
    left, right = st.columns(2, gap="large")
    with left:
        theme.section("Why this RUL", f"SHAP contribution, {spec.life_unit}")
        if isinstance(factors, list) and factors:
            theme.chart(factor_chart(factors, f"change in predicted {insights.life_word(spec)} ({spec.life_unit})",
                                     "#ff832b", TOKENS["accent"]), key="engine_shap")
    with right:
        risk_factors = row.get("risk_factors")
        if isinstance(risk_factors, list) and isinstance(row.get("risk_band"), str):
            band = BAND_TEXT[row["risk_band"]]
            theme.section("Why this risk band", f"push towards {band.lower()}, log-odds")
            theme.chart(factor_chart(risk_factors, f"push towards {band.lower()} (log-odds)", TOKENS["text_3"],
                                     BAND_COLORS.get(row["risk_band"], TOKENS["accent"])), key="engine_risk_shap")
    theme.note("Bars to the left shortened the predicted life. SHAP shows what the model relied on, not a confirmed root cause.")

st.divider()
links = st.columns(4)
links[0].page_link("views/health.py", label="Sensors", icon=":material/sensors:")
links[1].page_link("views/rul_risk.py", label=f"{spec.rul_short} and risk", icon=":material/timelapse:")
links[2].page_link("views/explainability.py", label="Explanations", icon=":material/account_tree:")
links[3].page_link("views/twin.py", label="3D model", icon=":material/view_in_ar:")
