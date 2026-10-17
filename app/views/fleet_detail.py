"""Fleet details: everything about the loaded fleet in three tabs. Overview (units by condition, what needs
attention, time left), Forecast and history (80% ranges, health history heatmap, fleet drivers, every unit) and
Data check (data profile, recognition, a manual model choice and the processing report, from views/data_check.py)."""

import runpy
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import insights, theme
from app.components import (
    FAULT_TEXT, band_label, fleet, fleet_bars, health_heatmap, ladder_chart, profile_spec, require_model,
    require_result, sensor_label, show_table,
)
from app.theme import MONO, SANS, TOKENS, esc
from src.config import CRITICAL_HEALTH_MULTIPLE, RISK_BANDS, SUBSETS
from src.explainability.sensor_names import SENSOR_INFO

VIEWS = Path(__file__).resolve().parent


def open_engine(unit):
    st.session_state["selected_unit"] = int(unit)
    st.switch_page("views/engine.py")


def open_engine_detail(unit):
    st.session_state["selected_unit"] = int(unit)
    st.switch_page("views/engine_detail.py")


result = require_result()
units = fleet(result)
spec = result.spec
noun = spec.actions.get("noun", "unit")
theme.page_head("Fleet details", f"Which {spec.unit_plural} need attention, how the forecasts and health developed, and how "
                "the file was checked and processed.",
                f"<b>{esc(st.session_state.get('source_name', ''))}</b><br>{insights.count(len(units), spec)}, "
                f"{len(result.history):,} {spec.time_title.lower()}s")

tab_overview, tab_detail, tab_data = st.tabs(["Overview", "Forecast and history", "Data check"])

with tab_overview:
    # 1. How the fleet stands: one count per condition.
    theme.section(f"1. {spec.unit_plural.capitalize()} by condition")
    theme.distribution(insights.state_counts(units))

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        # 2. What to do first: the units that are not healthy, most urgent first, in plain words.
        attention = units[units["state"] != "HEALTHY"]
        theme.section("2. Needs attention", f"{insights.count(len(attention), spec)}, most urgent first; select a row")
        if len(attention):
            table = attention.head(15).reset_index(drop=True)
            view = pd.DataFrame({
                spec.unit_title: table["unit"].map(spec.unit_id),
                "Condition": table["state"].map(lambda s: theme.STATES[s]["label"]),
                f"{spec.rul_short} left": [insights.life(v, spec) if pd.notna(v) else "n/a" for v in table.get("predicted_rul", [None] * len(table))],
                "Next step": [insights.recommendations(r, r["state"])[0]["action"] for _, r in table.iterrows()],
            })
            event = st.dataframe(view.style.map(lambda v: f"color: {next((x['color'] for x in theme.STATES.values() if x['label'] == v), '')}",
                                                subset=["Condition"]),
                                 hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                                 key="fleet_simple_queue", height=min(36 * (len(view) + 1) + 4, 560))
            rows = event.selection.rows if event and event.selection else []
            if rows:
                open_engine(table.iloc[rows[0]]["unit"])
        else:
            st.success(f"Every {noun} is healthy. No action needed.")
    with right:
        # 3. Time left at a glance: one bar per unit, coloured by condition.
        theme.section(f"3. {spec.rul_short} left", f"{insights.count(min(15, len(units)), spec)}, most urgent first")
        if "predicted_rul" in units:
            theme.chart(fleet_bars(units.head(15), spec), key="fleet_simple_bars")
            theme.note(f"Shorter bar = less {insights.life_word(spec)} left. Colours match the conditions above.")

with tab_detail:
    theme.spec(profile_spec(result))
    has_rul = "predicted_rul" in units
    show_all = st.session_state.get("fleet_all", False)
    theme.section(f"{spec.rul_short} forecast", f"80% range and point estimate, {'all ' + spec.unit_plural if show_all else 'top 25 by urgency'}")
    st.toggle(f"Show all {spec.unit_plural}", key="fleet_all")
    limit = None if show_all else 25
    if has_rul:
        event = theme.chart(ladder_chart(units, limit), key="fleet_ladder", on_select="rerun")
        points = event.selection.points if event and event.selection else []
        if points:
            point = points[0]
            open_engine_detail(point["customdata"][0] if point.get("customdata") else int(point["y"]))
    else:
        st.warning("RUL prediction failed for this analysis, so the forecast is unavailable.")

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

    # Every unit, filterable: the record behind the charts above.
    theme.section(f"All {spec.unit_plural}", "filter by risk band; select a row to open its detail")
    f_left, f_right = st.columns([3, 1], vertical_alignment="bottom")
    bands = f_left.multiselect("Risk bands", RISK_BANDS, default=RISK_BANDS, format_func=band_label) if "risk_band" in units else None
    review_only = f_right.toggle("Needs review only", key="fleet_review_only")
    table = units if bands is None else units[units["risk_band"].isin(bands)]
    if review_only:
        table = table[table["needs_review"]]
    df, event = show_table(table, ["Engine", "State", "Cycles", "RUL", "Range", "Band", "Confidence", "Health", "Condition", "Flags"],
                           key="fleet_all_units", on_select="rerun")
    rows = event.selection.rows if event and event.selection else []
    if rows:
        open_engine_detail(df.iloc[rows[0]]["_unit"])

with tab_data:
    runpy.run_path(str(VIEWS / "data_check.py"), run_name="fleet_tab")
