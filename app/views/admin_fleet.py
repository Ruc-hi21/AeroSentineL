"""Admin, fleet detail: forecast ranges, attention queue, health history heatmap and fleet drivers.
The maintainer's simple fleet view is the fleet section of views/overview.py."""

import plotly.graph_objects as go
import streamlit as st

from app import insights, theme
from app.components import (
    FAULT_TEXT, fleet, health_heatmap, ladder_chart, profile_spec, require_model, require_result, sensor_label,
    show_table,
)
from app.theme import MONO, SANS, TOKENS, esc
from src.config import CRITICAL_HEALTH_MULTIPLE, SUBSETS
from src.explainability.sensor_names import SENSOR_INFO


def open_engine(unit):
    st.session_state["selected_unit"] = int(unit)
    st.switch_page("views/admin_engine.py")


result = require_result()
units = fleet(result)
source = st.session_state.get("source_name", "")
spec = result.spec
theme.page_head("Fleet detail", f"{spec.unit_plural.capitalize()} ranked by urgency, with forecast ranges, health history and drivers. Select one to open its detail.",
                f"<b>{esc(source)}</b><br>{insights.count(len(units), spec)}, {len(result.history):,} {spec.time_title.lower()}s<br>"
                f"job {esc(result.job_id)}, {result.duration_ms:.0f} ms")
theme.spec(profile_spec(result))
theme.distribution(insights.state_counts(units))

has_rul = "predicted_rul" in units
left, right = st.columns([1.3, 1], gap="large")
with left:
    show_all = st.session_state.get("fleet_all", False)
    theme.section(f"{spec.rul_short} forecast", f"80% range and point estimate, {'all ' + spec.unit_plural if show_all else 'top 25 by urgency'}")
    st.toggle(f"Show all {spec.unit_plural}", key="fleet_all")
    limit = None if show_all else 25
    if has_rul:
        event = theme.chart(ladder_chart(units, limit), key="fleet_ladder", on_select="rerun")
        points = event.selection.points if event and event.selection else []
        if points:
            point = points[0]
            open_engine(point["customdata"][0] if point.get("customdata") else int(point["y"]))
    else:
        st.warning("RUL prediction failed for this analysis, so the forecast is unavailable.")
with right:
    attention = units[units["state"] != "HEALTHY"]
    theme.section("Attention queue", f"{insights.count(len(attention), spec)} not healthy, select a row to open")
    df, event = show_table(attention if len(attention) else units.head(10),
                           ["Engine", "State", "RUL", "Range", "Confidence"],
                           key="fleet_queue", on_select="rerun", height=min(36 * (len(attention) + 1) + 4, 560))
    rows = event.selection.rows if event and event.selection else []
    if rows:
        open_engine(df.iloc[rows[0]]["_unit"])

left, right = st.columns([1.3, 1], gap="large")
with left:
    theme.section("Health trend", f"health state over the last 60 {spec.time_title.lower()}s, 20 most urgent {spec.unit_plural}")
    threshold = require_model().health.threshold
    theme.chart(health_heatmap(units, result.history, threshold, CRITICAL_HEALTH_MULTIPLE * threshold), key="fleet_heat")
    theme.note(f"Each cell is the average health score over 5 {spec.time_title.lower()}s. Grey is healthy, amber is "
               f"abnormal (score above {threshold:.2f}), red is critical (above {CRITICAL_HEALTH_MULTIPLE * threshold:.2f}). "
               f"Read each row left to right to see when a {spec.unit_title.lower()} started to degrade.")
with right:
    theme.section("Fleet drivers", f"sensors that move the {spec.rul_short} forecast most, average {spec.life_unit} per "
                                   f"{spec.actions.get('noun', 'unit')}")
    if "rul_factors" in units:
        total = {}
        for factors in units["rul_factors"]:
            for f in factors if isinstance(factors, list) else []:
                total[f["sensor"]] = total.get(f["sensor"], 0.0) + abs(f["impact"])
        ranked = sorted(total.items(), key=lambda kv: kv[1], reverse=True)[:8]
        values = [v / len(units) for _, v in ranked]
        rows = list(range(len(ranked)))
        # Name above each bar (full width, no squeezed axis labels), value at the bar's end.
        fig = go.Figure(go.Bar(
            x=values, y=rows, orientation="h", width=0.42, marker_color=TOKENS["accent"],
            text=[f"{v:.1f}" for v in values], textposition="outside", cliponaxis=False,
            textfont=dict(family=MONO, size=12, color=TOKENS["text_1"]),
            customdata=[sensor_label(s) for s, _ in ranked],
            hovertemplate="%{customdata}<br>%{x:.2f} " + spec.life_unit + "<extra></extra>"))
        for i, (s, _) in enumerate(ranked):
            label = "Age (" + spec.time_title.lower() + "s)" if s == "cycle" else f"{SENSOR_INFO[s][1]}  ·  {SENSOR_INFO[s][0]}"
            fig.add_annotation(x=0, y=i - 0.3, text=label, showarrow=False, xanchor="left", yanchor="bottom",
                               font=dict(family=SANS, size=12, color=TOKENS["text_2"]))
        fig.update_layout(height=60 + 44 * len(ranked), margin=dict(t=8, b=40, l=8, r=40),
                          xaxis_title=f"average effect on the forecast ({spec.life_unit})")
        fig.update_yaxes(visible=False, range=[len(ranked) - 0.4, -0.75])
        theme.chart(fig, key="fleet_drivers")
        comp = result.component or "turbofan"
        faults = SUBSETS.get(result.subset, {}).get("fault_modes", ())
        if comp == "battery":
            theme.note("Battery life is set by capacity fade, so state of health, capacity and the charge timings that "
                       "track it are expected to lead; the operating settings show how temperature and load speed it up.")
        elif comp == "bearing":
            theme.note("Gearbox bearing damage shows up as rising vibration energy and impulsiveness on the casing, so RMS, "
                       "band energies and kurtosis are expected to lead, mostly in the last hour before failure.")
        elif comp == "hydraulic":
            theme.note("Cooler fouling shows in the oil temperatures and cooling efficiency, valve lag in the pressure profile "
                       "after the valve, and pump leakage in the main flow profile, so those channels are expected to lead.")
        elif comp == "power":
            theme.note("Thermal overstress wears the die attach and bond wires, so the on-state voltage, on-resistance and "
                       "package temperature are expected to lead. Four devices only: read the drivers as indicative.")
        elif "Fan" in faults:
            theme.note(f"{esc(result.subset)} has two fault modes, {FAULT_TEXT['HPC']} and {FAULT_TEXT['Fan']}, so fan speed "
                       "and bypass channels can lead alongside the compressor pressures and temperatures.")
        else:
            theme.note(f"{esc(result.subset)} has a single fault mode, high-pressure compressor degradation, so HPC "
                       "pressure and temperature channels are expected to lead.")
    else:
        st.info("Explanations are unavailable for this analysis.")
