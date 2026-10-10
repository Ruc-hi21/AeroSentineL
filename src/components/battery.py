"""Li-ion battery cell: NASA PCoE ageing data, one row per discharge cycle."""

from src.components.base import Channel, ComponentSpec, Profile

_C = [  # key, code, name, description, unit, decimals, module
    ("capacity_ah", "Cap", "Capacity", "Discharge capacity to cut-off voltage", "Ah", 3, "stack"),
    ("discharge_min", "tDis", "Discharge time", "Time to discharge to cut-off voltage", "min", 1, "stack"),
    ("dvdt_mid", "dV/dt", "Voltage slope", "Mid-discharge voltage slope", "mV/min", 2, "stack"),
    ("cc_charge_min", "tCC", "CC charge time", "Constant-current charge time to 4.2 V", "min", 1, "stack"),
    ("v_mean", "Vavg", "Mean voltage", "Mean terminal voltage under load", "V", 3, "interface"),
    ("cv_charge_min", "tCV", "CV charge time", "Constant-voltage charge time at 4.2 V", "min", 1, "interface"),
    ("rct_ohm", "Rct", "Charge-transfer R", "Charge-transfer resistance (impedance test)", "ohm", 4, "interface"),
    ("re_ohm", "Re", "Electrolyte R", "Electrolyte resistance (impedance test)", "ohm", 4, "electrolyte"),
    ("v_start", "V0", "Loaded voltage", "Terminal voltage when the load is applied", "V", 3, "terminal"),
    ("temp_max_c", "Tmax", "Peak temperature", "Peak cell temperature during discharge", "°C", 1, "can"),
    ("temp_rise_c", "dT", "Temperature rise", "Temperature rise during discharge", "°C", 1, "can"),
    ("t_tmax_min", "tTmax", "Time to peak temp", "Time from start of discharge to peak temperature", "min", 1, "can"),
    ("charge_temp_max_c", "Tchg", "Charge temperature", "Peak cell temperature while charging", "°C", 1, "can"),
]

BATTERY = ComponentSpec(
    key="battery", name="Li-ion battery cell", unit_title="Cell", unit_plural="cells",
    id_column="cell", time_column="cycle", time_title="Cycle", life_unit="cycles",
    settings=("ambient_c", "load_a"),
    setting_labels=("ambient temperature (°C)", "discharge current (A)"),
    setting_scale=(40.0, 3.0), reference_settings=(24.0, 2.0),
    channels=tuple(Channel(*c) for c in _C),
    modules=(("stack", "Electrode stack"), ("interface", "Electrode interface"), ("electrolyte", "Electrolyte"),
             ("terminal", "Terminals"), ("can", "Can and thermal")),
    derived=(Channel("soh", "SOH", "State of health", "Capacity relative to the cell's first discharges", "%", 1,
                     "stack"),),
    settings_as_features=True,
    profiles={"PCOE": Profile("PCOE", "NASA PCoE 18650 cells, 4 to 24 °C, 1 to 4 A discharge", 4, ("capacity fade",), 11, 4)},
    rul_cap=80, risk_limits={"FAILURE_LIKELY": 10, "HIGH_RISK": 20, "AT_RISK": 40},
    min_history=10, baseline_cycles=5, unit_prefix="B", unit_digits=4,
    actions={"remove": "Replace the cell before cycle {cycle}",
             "schedule": "Plan cell replacement within {life}",
             "inspect": "Check the {module}",
             "noun": "cell"},
    data_note="NASA PCoE Li-ion battery ageing data; end of life at 80% of starting capacity",
)
