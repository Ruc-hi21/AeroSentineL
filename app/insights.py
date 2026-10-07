"""Presentation-layer interpretation of pipeline output.

Turns the backend's per-unit results (risk band, RUL + 80% range, health score, review
reasons, SHAP factors) into what an operator asks first: condition state, confidence,
which sensors are drifting, and a suggested next action.

Nothing here re-runs or changes a model. The action rules are frontend guidance derived
from the same thresholds the backend uses; they are not maintenance procedures.
"""

import numpy as np
import pandas as pd

from src.config import RISK_BANDS, RISK_LIMITS, ROLLING_WINDOW
from src.explainability.sensor_names import SENSOR_INFO

STATE_ORDER = ["CRITICAL", "WARNING", "DEGRADING", "HEALTHY", "INSUFFICIENT"]
BAND_TO_STATE = {"FAILURE_LIKELY": "CRITICAL", "HIGH_RISK": "WARNING", "AT_RISK": "DEGRADING", "NORMAL": "HEALTHY"}
DRIFT_SMOOTHING = 5  # cycles, matches the 3D twin
# Directed drift bands (sigma from the healthy baseline, + = degrading). Calibrated on FD001
# training engines: healthy ~0, RUL 30-60 ~1.5, last 15 cycles ~3-4.
DRIFT_LEVELS = [(3.2, "Critical"), (2.4, "Warning"), (1.6, "Elevated")]

# Engine module each C-MAPSS sensor reports on (same layout as the 3D model).
MODULE_NAMES = {"fan": "Fan", "lpc": "LPC", "hpc": "HPC", "comb": "Combustor", "hpt": "HPT", "lpt": "LPT",
                "noz": "Nozzle", "byp": "Bypass duct"}
SENSOR_MODULE = {
    "sensor_1": "fan", "sensor_5": "fan", "sensor_8": "fan", "sensor_13": "fan", "sensor_18": "fan", "sensor_19": "fan",
    "sensor_2": "lpc", "sensor_3": "hpc", "sensor_7": "hpc", "sensor_9": "hpc", "sensor_11": "hpc", "sensor_14": "hpc",
    "sensor_17": "hpc", "sensor_12": "comb", "sensor_16": "comb", "sensor_20": "hpt", "sensor_4": "lpt",
    "sensor_21": "lpt", "sensor_10": "noz", "sensor_6": "byp", "sensor_15": "byp",
}


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
    band = row.get("risk_band")
    if not isinstance(band, str):
        if not _has(row, "predicted_rul"):
            return "INSUFFICIENT"
        rul = row["predicted_rul"]
        band = next((b for b in reversed(RISK_BANDS[1:]) if rul <= RISK_LIMITS[b]), "NORMAL")
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
    if level == "High" and _has(row, "rul_high") and row["rul_high"] - row["rul_low"] > 40:
        level = "Medium"  # wide RUL range: the band may be right but timing is uncertain
    return {"level": level, "probability": p, "flags": reasons}


def state_reason(row, state):
    """One sentence explaining the state in terms of the backend thresholds."""
    rul = row["predicted_rul"] if _has(row, "predicted_rul") else None
    if state == "INSUFFICIENT":
        if short_history(row):
            return f"Only {int(row['cycle'])} cycles observed; predictions need {ROLLING_WINDOW} or more to be reliable."
        return "No RUL or risk prediction is available for this engine."
    if rul is None:
        return f"Risk band {row['risk_band'].replace('_', ' ').lower()}; RUL prediction unavailable."
    if state == "CRITICAL":
        return f"Predicted RUL {rul:.0f} cycles, inside the failure-likely window (15 cycles or fewer)."
    if state == "WARNING":
        return f"Predicted RUL {rul:.0f} cycles, inside the high-risk window (16 to 30 cycles)."
    if state == "DEGRADING":
        if rul <= RISK_LIMITS["AT_RISK"]:
            return f"Predicted RUL {rul:.0f} cycles, inside the at-risk window (31 to 60 cycles)."
        return f"Health score {row['health_score']:.2f} is above the abnormal threshold although RUL is {rul:.0f} cycles."
    return f"Predicted RUL {rul:.0f} cycles and sensor drift within the healthy baseline."


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
            "module": MODULE_NAMES[SENSOR_MODULE[s]], "value": float(hist[s].iloc[-1]),
            # trend = change in drift per 10 cycles over the last 20 cycles
            "drift": round(now, 2), "peak": round(float(series.max()), 2), "trend": round(slope * 10, 2),
            "status": next((label for limit, label in DRIFT_LEVELS if now >= limit), "Nominal"),
            "history": [round(float(v), 2) for v in series.tail(60)],
        })
    return pd.DataFrame(rows).sort_values("drift", ascending=False).reset_index(drop=True)


def recommendations(row, state, drift=None):
    """Suggested next actions, most important first: [{'action', 'why'}]."""
    out = []
    cycle = int(row["cycle"])
    has_rul = _has(row, "predicted_rul") and _has(row, "rul_low")
    hot = drift[drift["status"].isin(["Critical", "Warning"])] if drift is not None else pd.DataFrame()
    module = hot.iloc[0]["module"] if len(hot) else None  # drift is sorted, strongest first
    codes = ", ".join(hot[hot["module"] == module]["code"].head(3)) if module else ""

    if state == "CRITICAL" and has_rul:
        out.append({"action": f"Plan removal or shop visit before cycle {cycle + round(row['rul_low'])}",
                    "why": f"Lower bound of the 80% RUL range is {row['rul_low']:.0f} cycles from the latest reading."})
    elif state == "WARNING" and has_rul:
        out.append({"action": f"Schedule maintenance within {round(row['rul_low'])} cycles",
                    "why": f"80% RUL range {row['rul_low']:.0f} to {row['rul_high']:.0f} cycles; risk band is high."})
    elif state == "DEGRADING":
        out.append({"action": "Add to the watch list and re-assess at the next data upload",
                    "why": "Degradation has started but the engine is outside the high-risk window."})
    elif state == "HEALTHY":
        out.append({"action": "No action required; continue routine monitoring",
                    "why": "RUL and sensor drift are within the healthy envelope."})
    else:
        out.append({"action": f"Collect at least {ROLLING_WINDOW} cycles before acting on this engine",
                    "why": "Rolling features are incomplete, so RUL and risk are provisional."})

    if module and state in ("CRITICAL", "WARNING", "DEGRADING"):
        out.append({"action": f"Inspect the {module} module",
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
