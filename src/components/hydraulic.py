"""Hydraulic system: the ZeMA hydraulic test rig (UCI dataset 447), one row per 60 s load cycle.

The rig's condition was varied on purpose: cooler efficiency, valve switching lag, internal pump
leakage and accumulator pre-charge pressure, in a designed sweep. It was not run to failure, so the
model predicts the remaining condition margin (0 to 100 %) of the weakest assessed part instead of a
remaining life, plus the condition of each part. A unit is one test session at constant conditions.

Channels are the per-cycle means of the rig's 17 sensors, and the pressure after the valve (PS2) and
the main flow (FS1) in six 10-second windows of the load cycle, which carry the valve's switching
behaviour and the pump's delivery.
"""

from src.components.base import Channel, ComponentSpec, Diagnosis, Profile

_SENSORS = [  # key, code, name, description, unit, decimals, module
    ("ps1", "PS1", "Pump outlet pressure", "Pressure at the pump outlet (cycle mean)", "bar", 1, "pump"),
    ("ps2", "PS2", "Valve outlet pressure", "Pressure after the switching valve (cycle mean)", "bar", 1, "valve"),
    ("ps3", "PS3", "Working line pressure", "Pressure in the working line (cycle mean)", "bar", 2, "valve"),
    ("ps4", "PS4", "Accumulator pressure", "Pressure at the accumulator (cycle mean)", "bar", 2, "accumulator"),
    ("ps5", "PS5", "Return pressure", "Pressure in the return line (cycle mean)", "bar", 2, "accumulator"),
    ("ps6", "PS6", "Tank line pressure", "Pressure in the tank line (cycle mean)", "bar", 2, "accumulator"),
    ("eps1", "EPS1", "Motor power", "Electrical power of the pump motor (cycle mean)", "W", 0, "pump"),
    ("fs1", "FS1", "Main flow", "Volume flow in the main circuit (cycle mean)", "l/min", 2, "pump"),
    ("fs2", "FS2", "Cooling flow", "Volume flow in the cooling circuit (cycle mean)", "l/min", 2, "cooler"),
    ("ts1", "TS1", "Tank temperature", "Oil temperature in the tank (cycle mean)", "°C", 2, "cooler"),
    ("ts2", "TS2", "Pump inlet temp", "Oil temperature at the pump inlet (cycle mean)", "°C", 2, "cooler"),
    ("ts3", "TS3", "Cooler inlet temp", "Oil temperature before the cooler (cycle mean)", "°C", 2, "cooler"),
    ("ts4", "TS4", "Cooler outlet temp", "Oil temperature after the cooler (cycle mean)", "°C", 2, "cooler"),
    ("vs1", "VS1", "Pump vibration", "Vibration velocity on the pump (cycle mean)", "mm/s", 3, "pump"),
    ("ce", "CE", "Cooling efficiency", "Cooling efficiency, virtual sensor (cycle mean)", "%", 1, "cooler"),
    ("cp", "CP", "Cooling power", "Cooling power, virtual sensor (cycle mean)", "kW", 3, "cooler"),
    ("se", "SE", "Pump efficiency", "Efficiency factor of the pump, virtual sensor (cycle mean)", "%", 1, "pump"),
]
WINDOWS = 6  # 10-second windows of the 60 s load cycle
_PROFILE = [  # (raw sensor, key, code, name, unit, decimals, module)
    ("PS2", "ps2", "PS2", "Valve outlet pressure", "bar", 1, "valve"),
    ("FS1", "fs1", "FS1", "Main flow", "l/min", 2, "pump"),
]

HYDRAULIC = ComponentSpec(
    key="hydraulic", name="Hydraulic system", unit_title="Session", unit_plural="sessions",
    id_column="session", time_column="cycle", time_title="Load cycle", life_unit="%",
    settings=(), setting_labels=(), setting_scale=(), reference_settings=(),
    channels=(
        *(Channel(k, c, n, d, u, dec, m) for k, c, n, d, u, dec, m in _SENSORS),
        *(Channel(f"{key}_w{i}", f"{code}.{i + 1}", f"{name}, {10 * i}-{10 * i + 10} s",
                  f"{name} averaged over seconds {10 * i} to {10 * i + 10} of the load cycle", unit, dec, mod)
          for _, key, code, name, unit, dec, mod in _PROFILE for i in range(WINDOWS)),
    ),
    modules=(("pump", "Pump and motor"), ("valve", "Switching valve"), ("accumulator", "Accumulator"),
             ("cooler", "Cooler and tank")),
    profiles={"UCI": Profile("UCI", "ZeMA hydraulic test rig: designed sweep of cooler, valve, pump and accumulator faults",
                             1, ("cooler fouling", "valve switching lag", "internal pump leakage"), 146, 48)},
    rul_cap=100, risk_limits={"FAILURE_LIKELY": 10, "HIGH_RISK": 30, "AT_RISK": 70},
    min_history=3, baseline_cycles=0,
    actions={"remove": "Stop the rig and service the {module} now",
             "schedule": "Plan a hydraulic service ({module})",
             "inspect": "Inspect the {module}",
             "noun": "hydraulic system"},
    data_note="ZeMA hydraulic test rig, UCI Machine Learning Repository dataset 447 (Helwig, Pignanelli, Schütze 2015)",
    target="margin", rul_short="Margin", rul_long="Remaining condition margin", group="block",
    diagnosis=(
        Diagnosis("cooler", "Cooler", "cooler", ((100, "Full efficiency", 0), (20, "Reduced efficiency", 2),
                                                  (3, "Close to total failure", 3))),
        Diagnosis("valve", "Switching valve", "valve", ((100, "Optimal switching", 0), (90, "Small lag", 1),
                                                         (80, "Severe lag", 2), (73, "Close to total failure", 3))),
        Diagnosis("pump", "Pump", "pump", ((0, "No leakage", 0), (1, "Weak leakage", 1), (2, "Severe leakage", 3))),
    ),
    not_assessed=("Accumulator pre-charge is not assessed: each pressure level was recorded in a single test "
                  "block, so a model cannot tell it apart from slow drift of the rig (0 to 19% correct on "
                  "held-out blocks)."),
)


def margin(cooler, valve, pump):
    """Remaining condition margin (%) of the weakest assessed part, 100 = all parts as new."""
    parts = ((cooler - 3) / 97, (valve - 73) / 27, (2 - pump) / 2)
    return 100 * min(max(0.0, min(1.0, p)) for p in parts)
