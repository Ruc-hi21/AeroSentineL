"""3D digital-twin component: a Three.js turbofan with every sensor pinned to its engine station.

The frontend (./frontend) is served by Streamlit as a custom component, so the WebGL scene
persists across reruns; only the payload changes when another unit is picked. Clicking a
sensor returns {"sensor", "unit", "t"} to Python.
"""

import math
import mimetypes
from pathlib import Path

import streamlit.components.v1 as components

from src.config import CRITICAL_HEALTH_MULTIPLE, RISK_BANDS, RISK_LIMITS, SENSOR_COLS
from src.explainability.sensor_names import SENSOR_INFO

# The Windows registry can map .js to text/plain, which browsers refuse for ES modules.
mimetypes.add_type("text/javascript", ".js")
_component = components.declare_component(
    "aerosentinel_engine3d", path=str(Path(__file__).parent / "frontend")
)

Z_SMOOTHING = 5  # cycles; per-sensor drift is smoothed so hotspot colours do not flicker


def _round(values, decimals):
    """JSON-safe rounded list (NaN/inf are not valid JSON)."""
    return [round(float(v), decimals) if math.isfinite(v) else 0.0 for v in values]


def twin_payload(result, unit, health, source=""):
    """Everything the twin needs to replay one unit's life, cycle by cycle."""
    hist = result.history[result.history["unit"] == unit].sort_values("cycle")
    row = result.units.set_index("unit").loc[unit]
    # Directed z-score vs. the healthy baseline: positive = drifting the way degradation pushes it.
    drift = health.sensor_deviation(hist).rolling(Z_SMOOTHING, min_periods=1).mean()

    sensors = []
    for key in SENSOR_COLS:
        if key not in hist:
            continue
        code, name, unit_label, decimals = SENSOR_INFO[key]
        modeled = key in health.sensors
        sensors.append({
            "key": key, "code": code, "name": name, "unit": unit_label, "decimals": decimals,
            "modeled": modeled,
            "values": _round(hist[key], decimals + 2),
            "z": _round(drift[key], 2) if modeled else None,
        })

    factors = row.get("rul_factors")
    has = hist.columns
    return {
        "id": f"{result.job_id}:{unit}",
        "unit": int(unit),
        "source": source,
        "model": result.model_version,
        "cycles": hist["cycle"].astype(int).tolist(),
        "health": _round(hist["health_score"], 3),
        "threshold": round(health.threshold, 3),
        "critical": round(CRITICAL_HEALTH_MULTIPLE * health.threshold, 3),
        "rul": _round(hist["predicted_rul"], 1) if "predicted_rul" in has else None,
        "band": [RISK_BANDS.index(b) for b in hist["risk_band"]] if "risk_band" in has else None,
        "prob": _round(hist["risk_probability"], 3) if "risk_probability" in has else None,
        "rul_low": float(row["rul_low"]) if "rul_low" in row else None,
        "rul_high": float(row["rul_high"]) if "rul_high" in row else None,
        "limits": [RISK_LIMITS[b] for b in RISK_BANDS[1:]],
        "sensors": sensors,
        "factors": [f["sensor"] for f in factors[:3]] if isinstance(factors, list) else [],
    }


def engine_twin(payload=None, mode="twin", height=820, key=None):
    """Render the twin. mode='hero' shows the engine alone (no data, no HUD)."""
    return _component(mode=mode, height=height, payload=payload, key=key, default=None)
