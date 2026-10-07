import numpy as np
import plotly.graph_objects as go
import streamlit as st

from app import fx, theme
from app.components import band_count_chart, get_result, launch_sample_button, show_table
from app.engine3d import engine_twin
from app.theme import BAND_COLORS, CYAN, esc
from src.analysis.health import compute_fleet_health_distribution
from src.config import CRITICAL_HEALTH_MULTIPLE
from src.explainability.sensor_names import SENSOR_INFO, describe
from src.models.artifacts import load_artifacts, model_status

result = get_result()
status = model_status()
meta = load_artifacts().metadata if status["ready"] else None

# ---------------------------------------------------------------- no data yet: hero + launch
if result is None or result.units is None:
    left, right = st.columns([1.05, 1.25], vertical_alignment="center")
    with left:
        st.html("""<style>
.as-hero-k { font-family:'JetBrains Mono',monospace; letter-spacing:.32em; font-size:.75rem; color:#00e5ff; }
.as-hero-t { font-family:'Orbitron',sans-serif; font-weight:900; font-size:clamp(1.7rem,3.7vw,3.8rem); line-height:1.05; margin:.6rem 0;
  overflow-wrap:anywhere;
  background:linear-gradient(90deg,#fff,#9fe9ff 40%,#00e5ff 65%,#9b6bff); background-size:200% 100%; -webkit-background-clip:text;
  background-clip:text; color:transparent; animation:as-flow 7s ease infinite; filter:drop-shadow(0 0 24px rgba(0,229,255,.35)); }
.as-hero-type { display:inline-block; font-family:'Orbitron',sans-serif; font-size:clamp(.75rem,1.2vw,1.05rem); letter-spacing:.3em;
  color:#fff; padding-right:4px; border-right:2px solid #00e5ff; clip-path:inset(0 100% 0 0);
  animation:as-type 2.4s steps(27) .4s forwards, as-caret .8s step-end infinite; }
.as-hero-p { font-family:'Exo 2',sans-serif; color:#9fb3d6; font-size:1.02rem; line-height:1.6; margin-top:1rem; max-width:560px; }
@keyframes as-type { to { clip-path: inset(0 0 0 0); } }
@keyframes as-caret { 50% { border-color: transparent; } }
</style>
<div class="as-hero-k">◢ PREDICTIVE MAINTENANCE · NASA C-MAPSS TURBOFAN</div>
<div class="as-hero-t">AEROSENTINEL</div>
<div class="as-hero-type">PREDICT · PROTECT · PREVENT</div>
<div class="as-hero-p">Upload engine telemetry and watch every unit come alive as a 3D digital twin — sensors pinned to their
engine stations, a life replay cycle by cycle, remaining useful life and failure risk from XGBoost, and SHAP explaining why.</div>""")
        if meta:
            test, val = meta["metrics"]["test"], meta["metrics"]["validation"]["risk"]["xgboost"]
            theme.kpi_row([
                theme.kpi("Risk accuracy", val["accuracy"] * 100, "🎯", "20 unseen engines, every cycle", "#19f5a0", 1, "%"),
                theme.kpi("NASA test acc.", test["risk"]["accuracy"] * 100, "🧪", "100 engines, last cycle", CYAN, 1, "%"),
                theme.kpi("RUL error", test["rul"]["rmse"], "⏱️", "test RMSE · cycles", theme.VIOLET, 1),
            ])
        launch_sample_button(key="hero_launch")
        st.page_link("views/upload.py", label="Upload your own telemetry", icon=":material/upload_file:")
    with right:
        engine_twin(mode="hero", height=470, key="hero_engine")

    theme.section("How it works", "7-stage pipeline")
    steps = [("🛡️", "Validate", "schema & type checks"), ("🧹", "Clean", "dupes, gaps, bad values"),
             ("🩺", "Health", "drift from healthy baseline"), ("🧬", "Features", "trends, drift, rolling stats"),
             ("⏳", "RUL", "XGBoost regression + 80% range"), ("🚨", "Risk", "XGBoost ensemble, 4 bands"),
             ("🔍", "Explain", "SHAP sensor attribution")]
    theme.kpi_row([theme.kpi(f"Step {i + 1:02d}", 0, icon, sub, c, text=t, compact=True) for i, ((icon, t, sub), c) in
                   enumerate(zip(steps, [CYAN, "#3d8bff", theme.PINK, theme.VIOLET, CYAN, "#ff8a1f", "#19f5a0"]))])
    st.stop()

# ---------------------------------------------------------------- fleet dashboard
units = result.units
source = st.session_state.get("source_name", "")
theme.page_header("Mission control · fleet status live", "Mission Control",
                  f"<b>{esc(source)}</b> · {len(units)} engines · model {esc(result.model_version)} · job "
                  f"<code>{esc(result.job_id)}</code>")

has_risk, has_rul = "risk_band" in units, "predicted_rul" in units
severe = int(units["risk_band"].isin(["HIGH_RISK", "FAILURE_LIKELY"]).sum()) if has_risk else 0
failure = int((units["risk_band"] == "FAILURE_LIKELY").sum()) if has_risk else 0
cards = [
    theme.kpi("Engines analysed", len(units), "🛩️", f"{int(result.history['cycle'].count()):,} cycles of telemetry", CYAN),
    theme.kpi("Failure likely", failure, "🔴", "RUL ≤ 15 cycles", BAND_COLORS["FAILURE_LIKELY"]),
    theme.kpi("Severe risk", severe, "⚠️", "high risk + failure likely", BAND_COLORS["HIGH_RISK"]),
]
if has_rul:
    cards.append(theme.kpi("Mean predicted RUL", units["predicted_rul"].mean(), "⏳", "cycles across the fleet", theme.VIOLET, 1))
cards.append(theme.kpi("Flagged for review", int(units["needs_review"].sum()), "👀", "need a human look", "#ffd23f"))
theme.kpi_row(cards)

left, right = st.columns([1.35, 1])
with left:
    fx.fleet_radar(units, height=470)
with right:
    if has_risk:
        theme.chart(band_count_chart(units), key="band_donut", height=300)
    if status["ready"]:
        dist = compute_fleet_health_distribution(units["health_score"], load_artifacts().health.threshold)
        theme.card("Health condition · latest cycle", f"""<ul class="as-list">
<li><span>🟢 Normal</span><span class="as-mono">{dist['normal']}</span></li>
<li><span>🟠 Degraded (above abnormal threshold)</span><span class="as-mono">{dist['degraded']}</span></li>
<li><span>🔴 Critical (&gt; {CRITICAL_HEALTH_MULTIPLE:g}× threshold)</span><span class="as-mono">{dist['critical']}</span></li></ul>""")

# ---------------------------------------------------------------- AI insights + drivers
theme.section("Fleet intelligence", "AI insights")
left, right = st.columns([1, 1])
with left:
    lines = []
    if has_rul and has_risk:
        worst = units.sort_values("predicted_rul").iloc[0]
        lines.append(f"Most urgent: <b>unit {int(worst['unit']):03d}</b> — predicted RUL <b>{worst['predicted_rul']:.0f}</b> cycles "
                     f"({theme.BAND_TEXT[worst['risk_band']].lower()}, {worst['risk_probability']:.0%} confidence).")
        soon = int((units["predicted_rul"] <= 30).sum())
        lines.append(f"<b>{soon}</b> engine{'s' if soon != 1 else ''} expected to reach end of life within 30 cycles — "
                     "schedule shop visits now.")
    if "rul_factors" in units:
        top = {}
        for fs in units["rul_factors"]:
            if isinstance(fs, list) and fs:
                top[fs[0]["sensor"]] = top.get(fs[0]["sensor"], 0) + 1
        if top:
            s, n = max(top.items(), key=lambda kv: kv[1])
            code = SENSOR_INFO.get(s, (s,))[0]
            lines.append(f"<b>{esc(code)}</b> ({esc(describe(s))}) is the #1 RUL driver for <b>{n}</b> engines — "
                         "consistent with the HPC degradation fault mode of FD001.")
    flagged = int(units["needs_review"].sum())
    lines.append(f"<b>{flagged}</b> unit{'s' if flagged != 1 else ''} flagged for human review (low confidence, disagreement, "
                 "out-of-range readings or short history).")
    theme.card("AI insights", "<ul class='as-list'>" + "".join(f"<li><span>✦ {l}</span></li>" for l in lines) + "</ul>")
with right:
    if "rul_factors" in units:
        total = {}
        for fs in units["rul_factors"]:
            for f in fs if isinstance(fs, list) else []:
                total[f["sensor"]] = total.get(f["sensor"], 0) + abs(f["impact"])
        ranked = sorted(total.items(), key=lambda kv: -kv[1])[:6]
        info = {**SENSOR_INFO, "cycle": ("AGE", "Engine age (cycles)", "", 0)}
        peak = ranked[0][1] if ranked else 1
        rows = "".join(
            f"<li><span style='min-width:150px'>{esc(info.get(s, (s,))[0])} · <span style='color:#7f95bd'>"
            f"{esc(info.get(s, ('', s))[1])}</span></span><span class='as-bar'><b style='width:{v / peak * 100:.0f}%;"
            f"background:linear-gradient(90deg,#3d8bff,#00e5ff);box-shadow:0 0 10px #00e5ff'></b></span>"
            f"<span class='as-mono' style='min-width:54px;text-align:right'>{v / len(units):.1f}</span></li>"
            for s, v in ranked)
        theme.card("Top contributing sensors · mean |SHAP| on RUL (cycles)", f"<ul class='as-list'>{rows}</ul>")

# ---------------------------------------------------------------- RUL landscape + degradation surface
if has_rul:
    theme.section("Remaining useful life", "fleet landscape")
    left, right = st.columns([1.2, 1])
    with left:
        ordered = units.sort_values("predicted_rul").reset_index(drop=True)
        colors = [BAND_COLORS[b] for b in ordered["risk_band"]] if has_risk else CYAN
        fig = go.Figure(go.Bar(
            x=[f"U{u:03d}" for u in ordered["unit"]], y=ordered["predicted_rul"], marker=dict(color=colors),
            error_y=dict(type="data", symmetric=False, array=ordered["rul_high"] - ordered["predicted_rul"],
                         arrayminus=ordered["predicted_rul"] - ordered["rul_low"], color="rgba(219,232,255,0.35)", thickness=1),
            hovertemplate="%{x}: %{y:.0f} cycles<extra></extra>",
        ))
        fig.update_layout(height=380, xaxis=dict(showticklabels=len(ordered) <= 40, title="engines, most urgent first"),
                          yaxis_title="predicted RUL (cycles)", bargap=0.15)
        theme.chart(fig, key="rul_landscape")
    with right:
        hist = result.history
        worst_units = ordered["unit"].head(14).tolist()
        sub = hist[hist["unit"].isin(worst_units)]
        grid = sub.pivot_table(index="unit", columns="cycle", values="health_score").reindex(worst_units)
        z = grid.to_numpy()
        fig = go.Figure(go.Surface(
            z=z, x=grid.columns.to_numpy(), y=np.arange(len(worst_units)),
            colorscale=[[0, "#0b1f4a"], [0.35, "#00e5ff"], [0.7, "#ff8a1f"], [1, "#ff2e4d"]], showscale=False,
            contours=dict(z=dict(show=True, usecolormap=True, project_z=True, width=1)),
            hovertemplate="cycle %{x}<br>health %{z:.2f}<extra></extra>",
        ))
        fig.update_layout(height=380, margin=dict(t=10, b=0, l=0, r=0), scene=dict(
            xaxis_title="cycle", yaxis=dict(title="unit", tickvals=list(range(len(worst_units))),
                                            ticktext=[f"U{u:03d}" for u in worst_units]),
            zaxis_title="health", camera=dict(eye=dict(x=1.6, y=-1.4, z=0.9))))
        theme.chart(fig, key="deg_surface")
        st.caption("Degradation surface — health score over life for the 14 most urgent engines.")

theme.section("Most urgent units")
top = units.sort_values("predicted_rul") if has_rul else units
show_table(top.head(12), ["unit", "cycle", "predicted_rul", "risk", "risk_probability", "health", "review"])
st.page_link("views/twin.py", label="Open the 3D Digital Twin for these engines", icon=":material/view_in_ar:")
