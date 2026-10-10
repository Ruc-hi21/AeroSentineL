"""Plain-language names for every component's channels, built from the component registry.

Turbofan names follow the NASA C-MAPSS documentation; battery and bearing names are defined in
src/components/battery.py and src/components/bearing.py.
"""

from src.components import COMPONENTS, channel

SENSOR_DESCRIPTIONS = {"cycle": "Age (cycles or minutes operated)"}
# Short symbol, compact name, unit and display decimals, used by the 3D model HUD and the tables.
SENSOR_INFO = {}
for _spec in COMPONENTS.values():
    for _key in [*_spec.model_channels, *_spec.settings]:
        _ch = channel(_key)
        SENSOR_DESCRIPTIONS[_ch.key] = _ch.description
        SENSOR_INFO[_ch.key] = (_ch.code, _ch.name, _ch.unit, _ch.decimals)


def describe(sensor):
    """'sensor_11' -> 'sensor_11 · HPC outlet static pressure (Ps30)'; other components by code."""
    name = SENSOR_DESCRIPTIONS.get(sensor)
    if sensor == "cycle" or not name:
        return name or sensor
    if sensor.startswith("sensor_"):
        return f"{sensor} · {name}"
    return f"{SENSOR_INFO[sensor][0]} · {name}"
