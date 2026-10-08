"""GSAP-driven instrument panels, served as one Streamlit custom component (./frontend).

The iframe persists across reruns, so when the selected engine changes its readouts tween
from the previous engine's values to the new ones: the motion shows what changed.
"""

import mimetypes
from pathlib import Path

import streamlit.components.v1 as components

from app import insights
from app.theme import BAND_COLORS, BAND_TEXT, STATES
from src.config import RISK_LIMITS, RUL_CAP

mimetypes.add_type("text/javascript", ".js")  # the Windows registry can map .js to text/plain
_component = components.declare_component("aerosentinel_instruments", path=str(Path(__file__).parent / "frontend"))


def status_payload(row, drift=None):
    """Everything the engine status panel shows, derived from one unit row."""
    state = insights.engine_state(row)
    conf = insights.confidence(row)
    acts = insights.recommendations(row, state, drift)
    has_rul = "predicted_rul" in row and "rul_low" in row
    cycle = int(row["cycle"])
    band = row.get("risk_band") if isinstance(row.get("risk_band"), str) else None
    return {
        "unit": int(row["unit"]),
        "cycle": cycle,
        "state": {"key": state, "label": STATES[state]["label"], "color": STATES[state]["color"]},
        "reason": insights.state_reason(row, state),
        "rul": float(row["predicted_rul"]) if has_rul else None,
        "low": float(row["rul_low"]) if has_rul else None,
        "high": float(row["rul_high"]) if has_rul else None,
        "cap": RUL_CAP,
        "limits": [{"at": RISK_LIMITS[b], "label": BAND_TEXT[b], "color": BAND_COLORS[b]}
                   for b in ("FAILURE_LIKELY", "HIGH_RISK", "AT_RISK")],
        "band": {"label": BAND_TEXT[band], "color": BAND_COLORS[band]} if band else None,
        "probability": conf["probability"],
        "confidence": conf["level"],
        "flags": conf["flags"],
        "action": acts[0] if acts else None,
    }


def engine_status(payload, key=None, height=214):
    return _component(kind="engine_status", data=payload, height=height, key=key, default=None)


GAS_PATH_MODULES = ["fan", "lpc", "hpc", "comb", "hpt", "lpt", "noz", "byp"]
DRIFT_STATUS_COLORS = {"Critical": STATES["CRITICAL"]["color"], "Warning": STATES["WARNING"]["color"],
                       "Elevated": STATES["DEGRADING"]["color"]}


def gas_path_payload(row, drift, unit_history, profile=None):
    """Module condition along the gas path for one engine, plus the operating condition of its latest cycle."""
    modules = []
    for key in GAS_PATH_MODULES:
        part = drift[drift["sensor"].map(insights.SENSOR_MODULE) == key] if len(drift) else drift
        worst = part.iloc[0] if len(part) else None  # drift is sorted, strongest first
        modules.append({
            "key": key, "name": insights.MODULE_NAMES[key],
            "status": worst["status"] if worst is not None else None,
            "color": DRIFT_STATUS_COLORS.get(worst["status"]) if worst is not None else None,
            "drift": float(worst["drift"]) if worst is not None else None,
            "sensors": [{"code": r["code"], "drift": float(r["drift"]), "status": r["status"]} for _, r in part.iterrows()],
        })
    last = unit_history.iloc[-1]
    condition = None
    if {"setting_1", "setting_2", "setting_3"} <= set(unit_history.columns):
        condition = {"id": int(last["condition"]) if "condition" in last else None,
                     "altitude": round(float(last["setting_1"]), 1), "mach": round(float(last["setting_2"]), 2),
                     "throttle": round(float(last["setting_3"])),
                     "known": bool(last.get("condition_known", True)),
                     "corrected": bool((profile or {}).get("corrected"))}
    return {"unit": int(row["unit"]), "cycle": int(row["cycle"]), "modules": modules, "condition": condition}


def gas_path(payload, key=None, height=300):
    return _component(kind="gas_path", data=payload, height=height, key=key, default=None)
