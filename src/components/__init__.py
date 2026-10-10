"""Registry of monitored components. See src/components/base.py for what a component defines."""

from src.components.base import Channel, ComponentSpec, Profile
from src.components.battery import BATTERY
from src.components.bearing import BEARING
from src.components.turbofan import TURBOFAN

COMPONENTS = {c.key: c for c in (TURBOFAN, BATTERY, BEARING)}
DEFAULT_COMPONENT = TURBOFAN.key
_CHANNELS = {ch.key: (spec, ch) for spec in COMPONENTS.values() for ch in (*spec.channels, *spec.derived)}
# Operating settings as pseudo-channels, so labels and explanations can name them.
_SETTING_CODES = {"setting_1": ("Alt", "Altitude", "kft"), "setting_2": ("Mach", "Mach number", ""),
                  "setting_3": ("TRA", "Throttle", "%"), "ambient_c": ("Tamb", "Ambient temp", "°C"),
                  "load_a": ("I", "Discharge current", "A"), "speed_rpm": ("N", "Shaft speed", "rpm"),
                  "load_kn": ("Fr", "Radial load", "kN")}
for _spec in COMPONENTS.values():
    for _key, _label in zip(_spec.settings, _spec.setting_labels):
        _code, _name, _unit = _SETTING_CODES.get(_key, (_key, _label, ""))
        _CHANNELS.setdefault(_key, (_spec, Channel(_key, _code, _name, f"Operating setting: {_label}", _unit, 2, "")))
# Profile keys are unique across components, so a profile alone names its component.
PROFILES = {p: spec for spec in COMPONENTS.values() for p in spec.profiles}

__all__ = ["COMPONENTS", "DEFAULT_COMPONENT", "PROFILES", "Channel", "ComponentSpec", "Profile", "get", "channel",
           "spec_of_channel", "spec_of_profile", "to_canonical"]


def get(key=None):
    """The spec for a component key (the turbofan when key is None)."""
    return COMPONENTS[key or DEFAULT_COMPONENT]


def channel(key):
    """Channel definition for a column key of any component, or None (e.g. for 'cycle')."""
    hit = _CHANNELS.get(key)
    return hit[1] if hit else None


def spec_of_channel(key):
    hit = _CHANNELS.get(key)
    return hit[0] if hit else None


def spec_of_profile(profile):
    """The component a trained profile (FD001, PCOE, FEMTO, ...) belongs to."""
    return PROFILES.get(profile, COMPONENTS[DEFAULT_COMPONENT])


def to_canonical(df, spec):
    """Rename a component's own id and age columns (cell, bearing, minute) to unit and cycle."""
    rename = {}
    if spec.id_column != "unit" and spec.id_column in df.columns and "unit" not in df.columns:
        rename[spec.id_column] = "unit"
    if spec.time_column != "cycle" and spec.time_column in df.columns and "cycle" not in df.columns:
        rename[spec.time_column] = "cycle"
    return df.rename(columns=rename) if rename else df
