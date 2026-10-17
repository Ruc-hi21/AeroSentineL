"""Engine detail: the full engineering view of one unit (status instrument, schematic, trend, sensor drift,
failure outlook, can-it-wait check, and SHAP for the RUL and the risk band). The simple view is views/engine.py."""

import streamlit as st

from app import insights, theme
from app.components import (
    drift_table, factor_chart, require_model, require_result, step_unit, trend_chart,
    unit_picker,
)
from app.instruments import engine_status, gas_path, gas_path_payload, status_payload
from app.theme import BAND_COLORS, BAND_TEXT, TOKENS, esc
from src.config import CRITICAL_HEALTH_MULTIPLE

artifacts = require_model()
result = require_result()
units = result.units

spec = result.spec
noun = spec.actions.get("noun", "unit")
theme.page_head(f"{spec.unit_title} detail", f"Engineering view of one {noun}: instruments, trend, sensor drift, failure outlook and SHAP.",
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

# 1-3. Condition, time left, risk and the single most important action.
engine_status(status_payload(row, drift), key="engine_status")

# Where on the component: part condition on its schematic, and the operating condition of the latest reading.
gas_path(gas_path_payload(row, drift, hist, result.profile), key="engine_gas_path")
example = {"turbofan": "compressor wear shifts fan speed too", "battery": "capacity fade also lengthens charge times",
           "bearing": "a bearing defect raises vibration in every band", "hydraulic": "a worn cooler warms the whole circuit",
           "power": "die-attach wear raises the package temperature too"}[spec.key]
if spec.diagnosis:
    theme.note("Each part takes the colour of its predicted condition (the part classifiers below); hover a part for its "
               "readings.")
else:
    theme.note("Each part takes the colour of its most-drifted sensor; hover a part for its readings. Sensors also "
               f"respond to faults elsewhere ({example}), so shading shows where the evidence is measured, not a confirmed root cause.")

# Part condition, for components whose data labels it (hydraulic cooler, valve and pump).
found = insights.parts(row)
if found:
    theme.section("Part condition", "predicted by one classifier per part, latest load cycle")
    sev = {0: "HEALTHY", 1: "DEGRADING", 2: "WARNING", 3: "CRITICAL"}
    theme.stats([theme.stat(p["name"], p["label"], foot=f"{p['p']:.0%} confidence",
                            color=theme.STATES[sev[p["severity"]]]["color"]) for p in found])
    if spec.not_assessed:
        theme.note(esc(spec.not_assessed))

# 4-5. What is changing.
left, right = st.columns([1.5, 1], gap="large")
with left:
    theme.section("Trend", f"predicted {spec.rul_short} above health score, per {spec.time_title.lower()}")
    threshold = artifacts.health.threshold
    theme.chart(trend_chart(hist, row, threshold, CRITICAL_HEALTH_MULTIPLE * threshold), key="engine_trend")
with right:
    hot = int(drift["status"].isin(["Critical", "Warning"]).sum())
    theme.section("Sensor drift", f"{hot} of {len(drift)} sensors beyond 2.4 sigma" if hot else "all sensors within 2.4 sigma")
    show_all = st.toggle("Show all sensors", key="engine_all_sensors")
    drift_table(drift, rows=None if show_all else 8, compact=True, unit=spec.life_unit)
    theme.note(f"Drift is the directed z-score against the healthy baseline learned from the first {spec.life_unit} of the "
               f"training {spec.unit_plural}. Positive values move in the direction degradation pushes that sensor.")

# 5b. How likely it is to fail inside each risk window, and whether it can wait for its next check.
outlook = insights.failure_outlook(row)
if outlook:
    added = {"FAILURE_LIKELY": "failure-likely band", "HIGH_RISK": "adds the high-risk band", "AT_RISK": "adds the at-risk band"}
    left, right = st.columns([1, 1], gap="large")
    with left:
        if spec.has_life:
            theme.section("Failure outlook", "chance of reaching end of life within each window")
            theme.stats([theme.stat(f"Within {insights.life(o['limit'], spec)}", insights.chance(o["p"]), foot=added[o["band"]])
                         for o in outlook])
        else:
            theme.section("Margin outlook", "chance the weakest part's margin is at or below each limit")
            theme.stats([theme.stat(f"Margin {insights.life(o['limit'], spec)} or less", insights.chance(o["p"]),
                                    foot=added[o["band"]]) for o in outlook])
        theme.note("From the risk model's four band probabilities at the latest reading. Each window adds the next band, "
                   "so the chance can only grow with the window.")
    with right:
        theme.section("Can it wait until the next check?")
        if spec.has_life:
            reach = spec.risk_limits["AT_RISK"]
            n = st.number_input(f"Next scheduled check, {spec.life_unit} from the latest reading", min_value=1,
                                max_value=reach, value=spec.risk_limits["HIGH_RISK"], step=1,
                                key=f"engine_next_check_{spec.key}")
            p = insights.failure_chance(row, n)
            verdict, title, why = insights.defer_verdict(p, state)
            theme.stats([theme.stat("Chance of reaching end of life first", insights.chance(p), foot=f"within {insights.life(n, spec)}"),
                         theme.stat("Verdict", title, color=theme.STATES[verdict]["color"])])
            provisional = insights.confidence(row)["flags"]
            theme.note(f"{why} The risk model sets how likely each band is; the 80% {spec.rul_short} range spreads that "
                       f"inside the band. It looks {reach} {spec.life_unit} ahead at most."
                       + (f" Provisional: {esc(', '.join(provisional))}." if provisional else ""))
        else:
            theme.note(f"The {noun} was not run to failure, so its output is a condition margin with no time to failure "
                       "to compare a check date against. Use the margin outlook instead.")

# 6-7. Why, and what to do.
left, right = st.columns([1, 1], gap="large")
with left:
    theme.section("Suggested actions")
    theme.actions(insights.recommendations(row, state, drift))
    theme.note("Frontend guidance derived from AeroSentinel's risk thresholds and sensor drift. "
               "Confirm against approved maintenance data before acting.")
with right:
    factors = row.get("rul_factors")
    theme.section("Why the model predicts this", f"SHAP contribution to the {spec.rul_short} estimate, {spec.life_unit}")
    if isinstance(factors, list):
        theme.chart(factor_chart(factors, f"change in predicted {spec.rul_short} ({spec.life_unit})", "#ff832b", TOKENS["accent"]), key="engine_shap")
        theme.note("Bars to the left shortened the predicted life. SHAP shows correlation with the prediction, "
                   "not proof of a root cause.")
    else:
        st.info("No explanation available for this analysis.")
    risk_factors = row.get("risk_factors")
    if isinstance(risk_factors, list) and isinstance(row.get("risk_band"), str):
        band = BAND_TEXT[row["risk_band"]]
        theme.section("Why this risk band", f"push towards {band.lower()}, log-odds")
        theme.chart(factor_chart(risk_factors, f"push towards {band.lower()} (log-odds)", TOKENS["text_3"],
                                 BAND_COLORS.get(row["risk_band"], TOKENS["accent"])), key="engine_risk_shap")

st.divider()
links = st.columns(4)
links[0].page_link("views/health.py", label="Degradation", icon=":material/trending_down:")
links[1].page_link("views/rul_risk.py", label=f"{spec.rul_short} and risk", icon=":material/timelapse:")
links[2].page_link("views/explainability.py", label="Explanations", icon=":material/account_tree:")
links[3].page_link("views/twin.py", label="Open 3D model", icon=":material/view_in_ar:")
