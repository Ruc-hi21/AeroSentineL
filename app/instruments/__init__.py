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
