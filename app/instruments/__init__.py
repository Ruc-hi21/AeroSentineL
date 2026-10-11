"""GSAP-driven instrument panels, served as one Streamlit custom component (./frontend).

The iframe persists across reruns, so when the selected engine changes its readouts tween
from the previous engine's values to the new ones: the motion shows what changed.
"""

import mimetypes
from pathlib import Path

import streamlit.components.v1 as components

from app import insights
from app.theme import BAND_COLORS, BAND_TEXT, STATES

mimetypes.add_type("text/javascript", ".js")  # the Windows registry can map .js to text/plain
_component = components.declare_component("aerosentinel_instruments", path=str(Path(__file__).parent / "frontend"))


def status_payload(row, drift=None):
    """Everything the engine status panel shows, derived from one unit row."""
    spec = insights.spec_of(row)
    state = insights.engine_state(row)
    conf = insights.confidence(row)
    acts = insights.recommendations(row, state, drift)
    has_rul = "predicted_rul" in row and "rul_low" in row
    cycle = int(row["cycle"])
    band = row.get("risk_band") if isinstance(row.get("risk_band"), str) else None
    return {
        "unit": int(row["unit"]),
        "label": spec.label(row["unit"]),
        "time_title": spec.time_title,
        "life_unit": spec.life_unit,
        "rul_short": spec.rul_short,
        "rul_long": spec.rul_long,
        "has_life": spec.has_life,
        "cycle": cycle,
        "state": {"key": state, "label": STATES[state]["label"], "color": STATES[state]["color"]},
        "reason": insights.state_reason(row, state),
        "rul": float(row["predicted_rul"]) if has_rul else None,
        "low": float(row["rul_low"]) if has_rul else None,
        "high": float(row["rul_high"]) if has_rul else None,
        "cap": spec.rul_cap,
        "limits": [{"at": spec.risk_limits[b], "label": BAND_TEXT[b], "color": BAND_COLORS[b]}
                   for b in ("FAILURE_LIKELY", "HIGH_RISK", "AT_RISK")],
        "band": {"label": BAND_TEXT[band], "color": BAND_COLORS[band]} if band else None,
        "probability": conf["probability"],
        "confidence": conf["level"],
        "flags": conf["flags"],
        "action": acts[0] if acts else None,
    }


def engine_status(payload, key=None, height=214):
    return _component(kind="engine_status", data=payload, height=height, key=key, default=None)


DRIFT_STATUS_COLORS = {"Critical": STATES["CRITICAL"]["color"], "Warning": STATES["WARNING"]["color"],
                       "Elevated": STATES["DEGRADING"]["color"]}
SCHEMATIC_TITLES = {"turbofan": "Gas path, inlet to exhaust", "battery": "Cell cross-section, negative to positive",
                    "bearing": "Gearbox section, input shaft to output shaft",
                    "hydraulic": "Hydraulic circuit, pump to cooler",
                    "power": "IGBT module stack, gate drive to heat sink"}


def condition_text(spec, last):
    """The operating condition of a reading in engineering units."""
    if not spec.settings:
        return {"hydraulic": "constant 60 s load cycle", "power": "square gate drive, package held above rating"}.get(spec.key, "")
    if spec.key == "turbofan":
        return f"{last['setting_1']:.0f} kft  M{last['setting_2']:.2f}  TRA {last['setting_3']:.0f}"
    if spec.key == "battery":
        return f"{last['ambient_c']:.0f} °C ambient  {last['load_a']:.1f} A discharge"
    return f"{last['speed_rpm']:.0f} rpm  {last['load_kn']:.1f} kN radial load"


def gas_path_payload(row, drift, unit_history, profile=None):
    """Module condition along the component for one unit, plus the operating condition of its latest reading."""
    spec = insights.spec_of(row)
    names = dict(spec.modules)
    modules = []
    for key, name in spec.modules:
        part = drift[drift["module"] == names[key]] if len(drift) else drift
        worst = part.iloc[0] if len(part) else None  # drift is sorted, strongest first
        modules.append({
            "key": key, "name": name,
            "status": worst["status"] if worst is not None else None,
            "color": DRIFT_STATUS_COLORS.get(worst["status"]) if worst is not None else None,
            "drift": float(worst["drift"]) if worst is not None else None,
            "sensors": [{"code": r["code"], "drift": float(r["drift"]), "status": r["status"]} for _, r in part.iterrows()],
        })
    # Parts with their own classifier (hydraulic) take the colour of their predicted condition.
    by_module = {p["module"]: p for p in insights.parts(row)}
    sev_status = {3: "Critical", 2: "Warning", 1: "Elevated"}
    for m in modules:
        p = by_module.get(m["key"])
        if p is not None:
            m["status"] = sev_status.get(p["severity"], "Nominal")
            m["color"] = DRIFT_STATUS_COLORS.get(m["status"]) if m["status"] else None
            m["sensors"] = [{"code": p["label"], "drift": 0.0, "status": m["status"] or "Nominal"}] + m["sensors"]
    last = unit_history.iloc[-1]
    condition = None
    if spec.settings and set(spec.settings) <= set(unit_history.columns):
        condition = {"id": int(last["condition"]) if "condition" in last else None, "text": condition_text(spec, last),
                     "known": bool(last.get("condition_known", True)),
                     "corrected": bool((profile or {}).get("corrected"))}
    return {"component": spec.key, "title": SCHEMATIC_TITLES[spec.key], "unit": int(row["unit"]),
            "label": spec.label(row["unit"]), "time_title": spec.time_title, "cycle": int(row["cycle"]),
            "modules": modules, "condition": condition}


def gas_path(payload, key=None, height=300):
    return _component(kind="gas_path", data=payload, height=height, key=key, default=None)
