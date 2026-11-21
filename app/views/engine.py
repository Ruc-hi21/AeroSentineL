"""Unit status: the decision page for one unit. A verdict panel (condition, time left, its place on the risk
bands), four readouts (when to service, risk, where to look, how far to trust the model), what to do next to
the sensors that lead the change, the forecast over the unit's life, and the component schematic. The sensors,
the timing and the explanation each have their own page (Degradation, RUL and risk, Explanations)."""

import streamlit as st

from app import insights, theme
from app.components import (DRIFT_COLORS, history_store, past_forecasts_chart, require_model, require_result, rul_chart,
                            step_unit, unit_picker)
from app.instruments import gas_path, gas_path_payload
from app.theme import BAND_COLORS, BAND_TEXT, STATES, esc

RECENT = 60  # readings shown by the "recent" view of the forecast
TOP_INDICATORS = 4

artifacts = require_model()
result = require_result()
units = result.units
spec = result.spec
noun = spec.actions.get("noun", "unit")
t = spec.time_title.lower()
word = insights.life_word(spec)
theme.page_head(f"{spec.unit_title} status", f"Is this {noun} all right, how long has it got, and what should be done.",
                f"<b>{esc(st.session_state.get('source_name', ''))}</b><br>{insights.count(len(units), spec)}, "
                f"model {esc(result.model_version)} {esc(result.subset or '')}", kicker=f"{spec.name} · unit view")

pick, prev, nxt, _, help_col = st.columns([3.2, 0.7, 0.7, 2.6, 1.8], vertical_alignment="bottom")
with pick:
    row = unit_picker(units, key="engine", label=f"{spec.unit_title} (most urgent first)")
if len(units) > 1:  # stepping only makes sense when the file holds several units
    prev.button("Previous", key="engine_prev", on_click=step_unit, args=(units, "engine", -1), width="stretch")
    nxt.button("Next", key="engine_next", on_click=step_unit, args=(units, "engine", 1), width="stretch")
with help_col:
    theme.guide([
        ("Condition", "Critical, Warning, Degrading or Healthy, from the model's risk band and the sensor drift."),
        (spec.rul_short, f"{spec.rul_long}: the model's best estimate. The frame on the scale is the range it is 80% sure of."),
        ("Service by", "The low end of that range, added to the unit's age. Planning to it is the cautious choice."),
        ("Drift", "How far a sensor sits from a healthy reading, in standard deviations (σ). Warning starts at 2.4σ."),
        ("Hover", "Tiles marked with an i explain themselves. Every chart shows exact values under the cursor."),
    ])

unit = int(row["unit"])
hist = result.history[result.history["unit"] == unit].sort_values("cycle")
drift = insights.sensor_drift(hist, artifacts.health)
state = insights.engine_state(row)
has_rul = "predicted_rul" in row and row["predicted_rul"] == row["predicted_rul"]
band = row.get("risk_band") if isinstance(row.get("risk_band"), str) else None

# The verdict: condition and why, the headline number, and where it sits on the four risk bands.
if has_rul:
    rul = float(row["predicted_rul"])
    has_range = "rul_low" in row and row["rul_low"] == row["rul_low"]
    shown_band = band or next((b for b in ("FAILURE_LIKELY", "HIGH_RISK", "AT_RISK") if rul <= spec.risk_limits[b]), "NORMAL")
    gauge = theme.life_gauge(rul, row["rul_low"] if has_range else None, row["rul_high"] if has_range else None, spec.rul_cap,
                             spec.risk_limits, shown_band, insights.life(rul, spec))
    theme.verdict(
        state, f"{spec.label(unit)} · {t} {int(row['cycle'])}", insights.state_reason(row, state),
        number=f"{rul:.0f}", number_label=spec.rul_long, unit=f"{spec.life_unit} left" if spec.has_life else "of margin left",
        range_html=(f"likely between <b>{row['rul_low']:.0f}</b> and <b>{esc(insights.life(row['rul_high'], spec))}</b>"
                    "<br>the model's 80% range") if has_range else "", gauge=gauge)
else:
    theme.verdict(state, f"{spec.label(unit)} · {t} {int(row['cycle'])}", insights.state_reason(row, state))
if insights.at_cap(row):
    theme.note(f"The forecast is at the model's ceiling of {insights.life(spec.rul_cap, spec)}: read it as "
               f"{insights.life(spec.rul_cap, spec)} or more.")

# Four readouts that turn the verdict into a plan.
items = []
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
hot = drift[drift["status"].isin(["Critical", "Warning"])]
part = insights.worst_part(row)
if part:  # hydraulic: the part its own classifier calls worst
    items.append(theme.stat("Where to look", part["name"], foot=f"{esc(part['label'].lower())}, {part['p']:.0%} confidence",
                            color=STATES["WARNING"]["color"], meter=part["p"],
                            tip="The part whose own condition classifier reports the worst state."))
else:
    items.append(theme.stat("Where to look", hot.iloc[0]["module"] if len(hot) else "Nothing flagged",
                            foot=f"{len(hot)} of {len(drift)} sensors past warning",
                            color=STATES["WARNING"]["color"] if len(hot) else None, meter=len(hot) / max(1, len(drift)),
                            tip="The part that carries the most-drifted sensor. It shows where the evidence is measured, "
                                "not a confirmed root cause."))
theme.stats(items)

found = insights.parts(row)
if found:  # hydraulic: the condition of each assessed part
    sev = {0: "HEALTHY", 1: "DEGRADING", 2: "WARNING", 3: "CRITICAL"}
    theme.section("Part condition", "each part has its own classifier", kicker="Diagnosis")
    theme.stats([theme.stat(p["name"], p["label"], foot=f"{p['p']:.0%} confidence", meter=p["p"],
                            color=STATES[sev[p["severity"]]]["color"]) for p in found])
    if spec.not_assessed:
        theme.note(esc(spec.not_assessed))

# What to do, next to the sensors that lead the change.
left_col, right_col = st.columns([1, 1.15], gap="large")
with left_col:
    theme.section("Recommended maintenance", kicker="Action")
    theme.actions(insights.recommendations(row, state, drift)[:3])
    theme.note("Guidance from AeroSentinel's risk limits and sensor drift. Confirm against approved maintenance data "
               "before acting.")
with right_col:
    theme.section("Leading indicators", f"the {min(TOP_INDICATORS, len(drift))} most-drifted sensors, latest 60 {t}s", kicker="Evidence")
    theme.indicators([{**r, "color": DRIFT_COLORS[r["status"]], "status": "Normal" if r["status"] == "Nominal" else r["status"]}
                      for r in drift.head(TOP_INDICATORS).to_dict("records")], per=f"per 10 {t}s")
    st.page_link("views/health.py", label="Inspect every sensor on Degradation", icon=":material/sensors:")

# The forecast over the unit's life, with a switch between the whole life and the latest readings.
theme.section(f"{spec.rul_short} forecast", f"one forecast per {t}; the bar is the likely range now",
              kicker="Trajectory")
if has_rul and "predicted_rul" in result.history:
    view = "Whole life"
    if len(hist) > RECENT * 1.5:
        view = st.segmented_control("Forecast window", ["Whole life", f"Latest {RECENT} {t}s"], default="Whole life",
                                    key="engine_window", label_visibility="collapsed") or "Whole life"
    fig = rul_chart(hist, row, height=340)
    if view != "Whole life":
        fig.update_xaxes(range=[int(row["cycle"]) - RECENT, int(row["cycle"]) + 2])
    theme.chart(fig, key="engine_rul_chart")
else:
    st.info("No forecast is available for this analysis.")

# Every earlier forecast for this unit, from the past-records database: how the outlook moved upload by upload.
store = history_store()
try:
    past = store.forecasts_of(spec.key, result.subset, row["unit"]) if store is not None and has_rul else None
except Exception:  # noqa: BLE001 - the database being down must not break the page
    past = None
if past is not None and len(past) > 1:
    theme.section("Past forecasts", f"{len(past)} uploads on record · {store.backend}", kicker="Records")
    theme.chart(past_forecasts_chart(past, spec), key="engine_past_chart")

# Where on the component the evidence sits.
theme.section("Component map", "the component, part by part; hover a part for its readings", kicker="Location")
gas_path(gas_path_payload(row, drift, hist, result.profile), key="engine_gas_path")
theme.note("Each part takes the colour of its predicted condition." if spec.diagnosis else
           "Each part takes the colour of its most-drifted sensor. Shading shows where the evidence is measured, "
           "not a confirmed root cause.")

st.divider()
links = st.columns(4)
links[0].page_link("views/health.py", label="Degradation", icon=":material/sensors:")
links[1].page_link("views/rul_risk.py", label=f"{spec.rul_short} and risk", icon=":material/timelapse:")
links[2].page_link("views/explainability.py", label="Explanations", icon=":material/account_tree:")
links[3].page_link("views/twin.py", label="3D model", icon=":material/view_in_ar:")
