"""Explanations: which sensors made the model predict this, and whether the measurements back it up. Two SHAP
charts (the RUL and the risk band), a cross-check that sets each top sensor's effect on the forecast next to its
drift, and an inspector that opens any driver's own readings."""

import pandas as pd
import streamlit as st

from app import insights, theme
from app.components import DRIFT_COLORS, factor_chart, focus_chart, reason_text, require_model, require_result, unit_picker
from app.theme import BAND_COLORS, BAND_TEXT, STATES, TOKENS, esc
from src.explainability.sensor_names import SENSOR_INFO

artifacts = require_model()
result = require_result()
spec = result.spec
noun = spec.actions.get("noun", "unit")
word = insights.life_word(spec)
theme.page_head("Explanations", f"Which sensors made the model predict this {word} for this {noun}, and whether they are "
                "really drifting. It shows what the model relied on, not a confirmed root cause.",
                kicker=f"{spec.name} · model reasoning")

pick, _, help_col = st.columns([3.2, 4.0, 1.8], vertical_alignment="bottom")
with pick:
    row = unit_picker(result.units, key="explain")
with help_col:
    theme.guide([
        ("Driver", "A sensor that moved this forecast. Its bar is how much it moved it (a SHAP value)."),
        ("Forecast drivers", f"Bars to the left shortened the predicted {word}; bars to the right lengthened it."),
        ("Risk drivers", "Bars to the right pushed the model towards the predicted risk band."),
        ("Cross-check", "A driver that is also drifting is real evidence. A driver that is not drifting deserves a look first."),
        ("Inspector", "Click a driver chip to see that sensor's own readings and drift."),
    ])
factors = row.get("rul_factors")
if not isinstance(factors, list) or not factors:
    st.info("No explanation is available for this analysis.")
    st.stop()

# Each top sensor's effect on the forecast, next to what the sensor itself is doing.
hist = result.history[result.history["unit"] == row["unit"]].sort_values("cycle")
drift = insights.sensor_drift(hist, artifacts.health).set_index("sensor")
rows = []
for f in factors:
    s = f["sensor"]
    code, name = SENSOR_INFO[s][:2] if s in SENSOR_INFO else ("", f"Age ({spec.time_title.lower()}s)")
    d = drift.loc[s] if s in drift.index else None
    status = "Not a wear sensor" if d is None else "Normal" if d["status"] == "Nominal" else d["status"]
    rows.append({"Sensor": f"{code}  {name}".strip(), "Part": "Age" if s == "cycle" else insights.module_of(s),
                 "Effect": f["impact"], "Drift": None if d is None else d["drift"], "Status": status,
                 "Evidence": "No drift to check" if d is None else "Not drifting" if d["status"] == "Nominal" else "Drifting too"})
table = pd.DataFrame(rows)
agree = int((table["Evidence"] == "Drifting too").sum())
checkable = int((table["Evidence"] != "No drift to check").sum())
by_part = table.assign(size=table["Effect"].abs()).groupby("Part")["size"].sum().sort_values(ascending=False)
shorten = [f for f in factors if f["impact"] < 0]

# In short.
theme.section("Model reasoning", f"the top {len(factors)} sensors behind this forecast", kicker="Summary")
top_what, top_why = reason_text(factors[0], spec)
theme.stats([
    theme.stat("Strongest driver", table["Sensor"].iloc[0].split("  ")[0], foot=f"{esc(top_what)}: {esc(top_why[0].lower() + top_why[1:])}",
               tip="The sensor with the largest effect on this forecast, and which way it moved it."),
    theme.stat("Part behind most of it", by_part.index[0], meter=by_part.iloc[0] / by_part.sum(),
               foot=f"{by_part.iloc[0] / by_part.sum():.0%} of the top sensors' effect",
               tip="The top sensors' effects added up by the part each one measures."),
    theme.stat("Drivers also drifting", f"{agree} of {len(table)}", meter=agree / max(1, checkable),
               color=STATES["WARNING"]["color"] if agree else None, foot="top sensors past the elevated level",
               tip="How many of the model's top sensors are themselves away from healthy. On a healthy unit, expect none."),
    theme.stat(f"Shortening the {word}", f"{len(shorten)} of {len(factors)}", meter=len(shorten) / len(factors),
               foot="top sensors pulling the forecast down",
               tip=f"Sensors whose readings made the model predict less {word} than it otherwise would."),
])

# What moved the forecast, and what moved the risk band.
left, right = st.columns(2, gap="large")
with left:
    theme.section("Forecast drivers", f"change in the predicted {word}, {spec.life_unit}", kicker=f"Why this {word}")
    theme.chart(factor_chart(factors, f"change in predicted {word} ({spec.life_unit})", "#ff832b", TOKENS["accent"]),
                key="explain_simple")
    theme.note(f"Orange bars pointing left shortened the predicted {word}; blue bars pointing right lengthened it.")
with right:
    risk_factors = row.get("risk_factors")
    if isinstance(risk_factors, list) and risk_factors and isinstance(row.get("risk_band"), str):
        band = BAND_TEXT[row["risk_band"]]
        theme.section("Risk band drivers", f"push towards {band.lower()}", kicker="Why this risk band")
        theme.chart(factor_chart(risk_factors, f"push towards {band.lower()} (log-odds)", TOKENS["text_3"],
                                 BAND_COLORS[row["risk_band"]]), key="explain_risk")
        theme.note(f"Bars pointing right pushed the model towards {esc(band.lower())}; bars pointing left pushed away from it.")
    else:
        theme.section("Risk band drivers", kicker="Why this risk band")
        st.info("No risk explanation is available for this analysis.")

# Does the evidence agree: the same sensors, with their drift.
theme.section("Evidence cross-check", "each top sensor's effect on the forecast next to its own drift", kicker="Validation")
st.dataframe(table.style.map(lambda v: f"color: {DRIFT_COLORS.get(v, TOKENS['text_1'])}", subset=["Status"]),
             hide_index=True, width="stretch", column_config={
                 "Effect": st.column_config.NumberColumn(f"Effect on forecast ({spec.life_unit})", format="%+.1f"),
                 "Drift": st.column_config.NumberColumn("Drift now (sigma)", format="%+.1f",
                                                        help="Standard deviations from a healthy reading; positive means wearing"),
             })
theme.note("A sensor that both drives the forecast and is drifting is real evidence. A driver that is not drifting means "
           "the model is leaning on a pattern the limits do not show yet: look at it before acting. On a healthy "
           f"{noun}, expect none to be drifting.")

# One driver in full: the sensor's own readings behind its bar.
sensors = [f["sensor"] for f in factors if f["sensor"] in hist.columns and f["sensor"] in SENSOR_INFO]
if sensors:
    theme.section("Driver inspector", "pick a driver: its reading above its drift, on one time axis", kicker="Inspect")
    chosen = st.pills("Driver", sensors, default=sensors[0], key=f"explain_inspect_{spec.key}", label_visibility="collapsed",
                      format_func=lambda s: f"{SENSOR_INFO[s][0]}  {SENSOR_INFO[s][1]}") or sensors[0]
    theme.chart(focus_chart(hist, artifacts.health, chosen, spec), key="explain_focus")
    what, why = reason_text(next(f for f in factors if f["sensor"] == chosen), spec)
    theme.note(f"{esc(what)}: {esc(why[0].lower() + why[1:])}")
