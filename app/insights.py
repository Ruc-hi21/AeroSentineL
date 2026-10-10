"""Presentation-layer interpretation of pipeline output.

Turns the backend's per-unit results (risk band, RUL + 80% range, health score, review
reasons, SHAP factors) into what an operator asks first: condition state, confidence,
which sensors are drifting, and a suggested next action. Each unit row carries its
`component`, so limits, life units, part names and wording come from that component's spec.

Nothing here re-runs or changes a model. The action rules are frontend guidance derived
from the same thresholds the backend uses; they are not maintenance procedures.
"""

import numpy as np
import pandas as pd

from src.components import channel, get, spec_of_channel
from src.config import RISK_BANDS
from src.explainability.sensor_names import SENSOR_INFO

STATE_ORDER = ["CRITICAL", "WARNING", "DEGRADING", "HEALTHY", "INSUFFICIENT"]
BAND_TO_STATE = {"FAILURE_LIKELY": "CRITICAL", "HIGH_RISK": "WARNING", "AT_RISK": "DEGRADING", "NORMAL": "HEALTHY"}
DRIFT_SMOOTHING = 5  # cycles, matches the 3D model
# Directed drift bands (sigma from the healthy baseline, + = degrading). Calibrated on FD001
# training engines: healthy ~0, RUL 30-60 ~1.5, last 15 cycles ~3-4.
DRIFT_LEVELS = [(3.2, "Critical"), (2.4, "Warning"), (1.6, "Elevated")]


def spec_of(row_or_units):
    """The component spec of a unit row or units table (turbofan when unknown)."""
    comp = row_or_units.get("component") if hasattr(row_or_units, "get") else None
    if isinstance(comp, pd.Series):
        comp = comp.iloc[0] if len(comp) else None
    return get(comp if isinstance(comp, str) else None)


def life(n, spec):
    """'1 cycle', '5 cycles', '12 minutes': n rounded to a whole life unit."""
    n = int(round(float(n)))
    unit = spec.life_unit
    return f"{n} {unit[:-1]}" if n == 1 else f"{n} {unit}"


def module_of(sensor):
    """Part of its component that a channel reports on, by name ('HPC', 'Races', 'Electrode stack')."""
    ch, spec = channel(sensor), spec_of_channel(sensor)
    return spec.module_name(ch.module) if ch is not None and ch.module else "Operating setting"


def _has(row, key):
    if key not in row:
        return False
    value = row[key]
    return isinstance(value, list) or not pd.isna(value)


def short_history(row):
    return any(r.startswith("short history") for r in row["review_reasons"])


def engine_state(row):
    """CRITICAL / WARNING / DEGRADING / HEALTHY / INSUFFICIENT for one unit row.

    Critical and warning are never masked by a data-quality flag: a short history only
    downgrades an otherwise healthy or degrading read to INSUFFICIENT.
    """
    spec = spec_of(row)
    band = row.get("risk_band")
    if not isinstance(band, str):
        if not _has(row, "predicted_rul"):
            return "INSUFFICIENT"
        rul = row["predicted_rul"]
        band = next((b for b in reversed(RISK_BANDS[1:]) if rul <= spec.risk_limits[b]), "NORMAL")
    state = BAND_TO_STATE[band]
    if state in ("CRITICAL", "WARNING"):
        return state
    if short_history(row):
        return "INSUFFICIENT"
    if state == "HEALTHY" and row["health_condition"] == "abnormal":
        return "DEGRADING"
    return state


def add_states(units):
    """units with a `state` column and an urgency order (most severe, then lowest RUL)."""
    out = units.assign(state=units.apply(engine_state, axis=1))
    out["_rank"] = out["state"].map(STATE_ORDER.index)
    out["_rul"] = out["predicted_rul"] if "predicted_rul" in out else 0.0
    return out.sort_values(["_rank", "_rul"]).drop(columns=["_rank", "_rul"])


def state_counts(units):
    states = units["state"] if "state" in units else units.apply(engine_state, axis=1)
    return {s: int((states == s).sum()) for s in STATE_ORDER}


def confidence(row):
    """Level (High/Medium/Low), the band probability and the review flags that qualify it."""
    spec = spec_of(row)
    p = row.get("risk_probability")
    p = float(p) if p is not None and not pd.isna(p) else None
    reasons = [r for r in row["review_reasons"] if r != "high risk"]
    if p is None:
        level = "Unknown"
    elif p >= 0.8 and not reasons:
        level = "High"
    elif p >= 0.6:
        level = "Medium"
    else:
        level = "Low"
    # A range wider than a third of the RUL scale: the band may be right but timing is uncertain.
    if level == "High" and _has(row, "rul_high") and row["rul_high"] - row["rul_low"] > spec.rul_cap / 3:
        level = "Medium"
    return {"level": level, "probability": p, "flags": reasons}


def band_window(spec, band):
    """'15 cycles or fewer', '16 to 30 cycles' for a band of this component."""
    lim = spec.risk_limits
    if band == "FAILURE_LIKELY":
        return f"{lim['FAILURE_LIKELY']} {spec.life_unit} or fewer"
    if band == "HIGH_RISK":
        return f"{lim['FAILURE_LIKELY'] + 1} to {lim['HIGH_RISK']} {spec.life_unit}"
    if band == "AT_RISK":
        return f"{lim['HIGH_RISK'] + 1} to {lim['AT_RISK']} {spec.life_unit}"
    return f"more than {lim['AT_RISK']} {spec.life_unit}"


def state_reason(row, state):
    """One sentence explaining the state in terms of the backend thresholds."""
    spec = spec_of(row)
    rul = row["predicted_rul"] if _has(row, "predicted_rul") else None
    if state == "INSUFFICIENT":
        if short_history(row):
            return (f"Only {life(row['cycle'], spec)} observed; predictions need {spec.min_history} or more "
                    "to be reliable.")
        return f"No RUL or risk prediction is available for this {spec.actions.get('noun', 'unit')}."
    if rul is None:
        return f"Risk band {row['risk_band'].replace('_', ' ').lower()}; RUL prediction unavailable."
    if state == "CRITICAL":
        return f"Predicted RUL {life(rul, spec)}, inside the failure-likely window ({band_window(spec, 'FAILURE_LIKELY')})."
    if state == "WARNING":
        return f"Predicted RUL {life(rul, spec)}, inside the high-risk window ({band_window(spec, 'HIGH_RISK')})."
    if state == "DEGRADING":
        if rul <= spec.risk_limits["AT_RISK"]:
            return f"Predicted RUL {life(rul, spec)}, inside the at-risk window ({band_window(spec, 'AT_RISK')})."
        return f"Health score {row['health_score']:.2f} is above the abnormal threshold although RUL is {life(rul, spec)}."
    return f"Predicted RUL {life(rul, spec)} and sensor drift within the healthy baseline."


def sensor_drift(unit_history, health):
    """Per modelled sensor: latest value, directed drift (sigma), peak drift, recent trend and status.

    Uses HealthAnalyzer.sensor_deviation exactly as the backend defines it (read-only).
    """
    hist = unit_history.sort_values("cycle")
    z = health.sensor_deviation(hist).rolling(DRIFT_SMOOTHING, min_periods=1).mean()
    rows = []
    for s in health.sensors:
        series = z[s]
        recent = series.tail(20).to_numpy()
        slope = float(np.polyfit(np.arange(len(recent)), recent, 1)[0]) if len(recent) > 2 else 0.0
        now = float(series.iloc[-1])
        rows.append({
            "sensor": s, "code": SENSOR_INFO[s][0], "name": SENSOR_INFO[s][1], "unit": SENSOR_INFO[s][2],
            "module": module_of(s), "value": float(hist[s].iloc[-1]),
            # trend = change in drift per 10 cycles over the last 20 cycles
            "drift": round(now, 2), "peak": round(float(series.max()), 2), "trend": round(slope * 10, 2),
            "status": next((label for limit, label in DRIFT_LEVELS if now >= limit), "Nominal"),
            "history": [round(float(v), 2) for v in series.tail(60)],
        })
    return pd.DataFrame(rows).sort_values("drift", ascending=False).reset_index(drop=True)


def recommendations(row, state, drift=None):
    """Suggested next actions, most important first: [{'action', 'why'}]."""
    spec = spec_of(row)
    say = spec.actions
    noun = say.get("noun", "unit")
    out = []
    cycle = int(row["cycle"])
    has_rul = _has(row, "predicted_rul") and _has(row, "rul_low")
    hot = drift[drift["status"].isin(["Critical", "Warning"])] if drift is not None else pd.DataFrame()
    module = hot.iloc[0]["module"] if len(hot) else None  # drift is sorted, strongest first
    codes = ", ".join(hot[hot["module"] == module]["code"].head(3)) if module else ""

    if state == "CRITICAL" and has_rul:
        out.append({"action": say["remove"].format(cycle=cycle + round(row["rul_low"])),
                    "why": f"Lower bound of the 80% RUL range is {life(row['rul_low'], spec)} from the latest reading."})
    elif state == "WARNING" and has_rul:
        out.append({"action": say["schedule"].format(life=life(row["rul_low"], spec)),
                    "why": f"80% RUL range {row['rul_low']:.0f} to {row['rul_high']:.0f} {spec.life_unit}; risk band is high."})
    elif state == "DEGRADING":
        out.append({"action": "Add to the watch list and re-assess at the next data upload",
                    "why": f"Degradation has started but the {noun} is outside the high-risk window."})
    elif state == "HEALTHY":
        out.append({"action": "No action required; continue routine monitoring",
                    "why": "RUL and sensor drift are within the healthy envelope."})
    else:
        out.append({"action": f"Collect at least {life(spec.min_history, spec)} before acting on this {noun}",
                    "why": "Rolling features are incomplete, so RUL and risk are provisional."})

    if module and state in ("CRITICAL", "WARNING", "DEGRADING"):
        out.append({"action": say["inspect"].format(module=module if spec.key == "turbofan" else module.lower()),
                    "why": f"{codes} drifting beyond 2.4 sigma from the healthy baseline."})
    flags = confidence(row)["flags"]
    if "RUL and risk band disagree" in flags:
        out.append({"action": "Route to engineering review: models disagree",
                    "why": "The RUL estimate and the risk classifier point to bands more than one level apart."})
    if "readings outside training range" in flags:
        out.append({"action": "Check sensor calibration and data quality",
                    "why": "Some readings fall outside the range seen in training; predictions extrapolate."})
    if "low confidence" in flags:
        out.append({"action": "Treat the risk band as provisional",
                    "why": f"Classifier confidence is {row['risk_probability']:.0%}, below the 60% review threshold."})
    return out


# Backwards-compatible names used by older views.
MODULE_NAMES = dict(get("turbofan").modules)
SENSOR_MODULE = {c.key: c.module for c in get("turbofan").channels}
