"""Turbofan engine: NASA C-MAPSS, one model per subset (FD001-FD004)."""

from src.components.base import Channel, ComponentSpec, Profile

_C = [  # key, code, name, description, unit, decimals, module (NASA C-MAPSS documentation)
    ("sensor_1", "T2", "Fan inlet temp", "Fan inlet temperature (T2)", "°R", 2, "fan"),
    ("sensor_2", "T24", "LPC outlet temp", "LPC outlet temperature (T24)", "°R", 2, "lpc"),
    ("sensor_3", "T30", "HPC outlet temp", "HPC outlet temperature (T30)", "°R", 2, "hpc"),
    ("sensor_4", "T50", "LPT outlet temp", "LPT outlet temperature (T50)", "°R", 2, "lpt"),
    ("sensor_5", "P2", "Fan inlet pressure", "Fan inlet pressure (P2)", "psia", 2, "fan"),
    ("sensor_6", "P15", "Bypass-duct press.", "Bypass-duct pressure (P15)", "psia", 2, "byp"),
    ("sensor_7", "P30", "HPC outlet pressure", "HPC outlet pressure (P30)", "psia", 2, "hpc"),
    ("sensor_8", "Nf", "Fan speed", "Physical fan speed (Nf)", "rpm", 2, "fan"),
    ("sensor_9", "Nc", "Core speed", "Physical core speed (Nc)", "rpm", 1, "hpc"),
    ("sensor_10", "epr", "Engine press. ratio", "Engine pressure ratio (epr)", "", 2, "noz"),
    ("sensor_11", "Ps30", "HPC static press.", "HPC outlet static pressure (Ps30)", "psia", 2, "hpc"),
    ("sensor_12", "phi", "Fuel flow / Ps30", "Fuel flow to Ps30 ratio (phi)", "pps/psi", 2, "comb"),
    ("sensor_13", "NRf", "Corr. fan speed", "Corrected fan speed (NRf)", "rpm", 2, "fan"),
    ("sensor_14", "NRc", "Corr. core speed", "Corrected core speed (NRc)", "rpm", 1, "hpc"),
    ("sensor_15", "BPR", "Bypass ratio", "Bypass ratio (BPR)", "", 4, "byp"),
    ("sensor_16", "farB", "Burner fuel-air", "Burner fuel-air ratio (farB)", "", 3, "comb"),
    ("sensor_17", "htBleed", "Bleed enthalpy", "Bleed enthalpy (htBleed)", "", 0, "hpc"),
    ("sensor_18", "Nf_dmd", "Demanded fan spd", "Demanded fan speed (Nf_dmd)", "rpm", 0, "fan"),
    ("sensor_19", "PCNfR", "Demanded corr. Nf", "Demanded corrected fan speed (PCNfR_dmd)", "rpm", 2, "fan"),
    ("sensor_20", "W31", "HPT coolant bleed", "HPT coolant bleed (W31)", "lbm/s", 2, "hpt"),
    ("sensor_21", "W32", "LPT coolant bleed", "LPT coolant bleed (W32)", "lbm/s", 3, "lpt"),
]

TURBOFAN = ComponentSpec(
    key="turbofan", name="Turbofan engine", unit_title="Engine", unit_plural="engines",
    id_column="unit", time_column="cycle", time_title="Cycle", life_unit="cycles",
    settings=("setting_1", "setting_2", "setting_3"),
    setting_labels=("altitude (kft)", "Mach number", "throttle (TRA)"),
    setting_scale=(42.0, 0.84, 40.0), reference_settings=(0.0, 0.0, 100.0),
    channels=tuple(Channel(*c) for c in _C),
    modules=(("fan", "Fan"), ("lpc", "LPC"), ("hpc", "HPC"), ("comb", "Combustor"), ("hpt", "HPT"),
             ("lpt", "LPT"), ("noz", "Nozzle"), ("byp", "Bypass duct")),
    profiles={
        "FD001": Profile("FD001", "1 operating condition, HPC degradation", 1, ("HPC",), 100, 100),
        "FD002": Profile("FD002", "6 operating conditions, HPC degradation", 6, ("HPC",), 260, 259),
        "FD003": Profile("FD003", "1 operating condition, HPC and fan degradation", 1, ("HPC", "Fan"), 100, 100),
        "FD004": Profile("FD004", "6 operating conditions, HPC and fan degradation", 6, ("HPC", "Fan"), 249, 248),
    },
    rul_cap=125, risk_limits={"FAILURE_LIKELY": 15, "HIGH_RISK": 30, "AT_RISK": 60},
    min_history=30, baseline_cycles=30,
    actions={"remove": "Plan removal or shop visit before cycle {cycle}",
             "schedule": "Schedule maintenance within {life}",
             "inspect": "Inspect the {module} module",
             "noun": "engine"},
    data_note="NASA C-MAPSS turbofan degradation simulation, FD001 to FD004",
)
