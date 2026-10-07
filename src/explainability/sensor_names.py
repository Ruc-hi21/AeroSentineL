"""Plain-language names for C-MAPSS sensors (from the NASA C-MAPSS documentation)."""

SENSOR_DESCRIPTIONS = {
    "cycle": "Engine age (cycles operated)",
    "sensor_1": "Fan inlet temperature (T2)",
    "sensor_2": "LPC outlet temperature (T24)",
    "sensor_3": "HPC outlet temperature (T30)",
    "sensor_4": "LPT outlet temperature (T50)",
    "sensor_5": "Fan inlet pressure (P2)",
    "sensor_6": "Bypass-duct pressure (P15)",
    "sensor_7": "HPC outlet pressure (P30)",
    "sensor_8": "Physical fan speed (Nf)",
    "sensor_9": "Physical core speed (Nc)",
    "sensor_10": "Engine pressure ratio (epr)",
    "sensor_11": "HPC outlet static pressure (Ps30)",
    "sensor_12": "Fuel flow to Ps30 ratio (phi)",
    "sensor_13": "Corrected fan speed (NRf)",
    "sensor_14": "Corrected core speed (NRc)",
    "sensor_15": "Bypass ratio (BPR)",
    "sensor_16": "Burner fuel-air ratio (farB)",
    "sensor_17": "Bleed enthalpy (htBleed)",
    "sensor_18": "Demanded fan speed (Nf_dmd)",
    "sensor_19": "Demanded corrected fan speed (PCNfR_dmd)",
    "sensor_20": "HPT coolant bleed (W31)",
    "sensor_21": "LPT coolant bleed (W32)",
}


# Short symbol, compact name, unit and display decimals, used by the 3D digital twin HUD.
SENSOR_INFO = {
    "sensor_1": ("T2", "Fan inlet temp", "°R", 2),
    "sensor_2": ("T24", "LPC outlet temp", "°R", 2),
    "sensor_3": ("T30", "HPC outlet temp", "°R", 2),
    "sensor_4": ("T50", "LPT outlet temp", "°R", 2),
    "sensor_5": ("P2", "Fan inlet pressure", "psia", 2),
    "sensor_6": ("P15", "Bypass-duct press.", "psia", 2),
    "sensor_7": ("P30", "HPC outlet pressure", "psia", 2),
    "sensor_8": ("Nf", "Fan speed", "rpm", 2),
    "sensor_9": ("Nc", "Core speed", "rpm", 1),
    "sensor_10": ("epr", "Engine press. ratio", "", 2),
    "sensor_11": ("Ps30", "HPC static press.", "psia", 2),
    "sensor_12": ("phi", "Fuel flow / Ps30", "pps/psi", 2),
    "sensor_13": ("NRf", "Corr. fan speed", "rpm", 2),
    "sensor_14": ("NRc", "Corr. core speed", "rpm", 1),
    "sensor_15": ("BPR", "Bypass ratio", "", 4),
    "sensor_16": ("farB", "Burner fuel-air", "", 3),
    "sensor_17": ("htBleed", "Bleed enthalpy", "", 0),
    "sensor_18": ("Nf_dmd", "Demanded fan spd", "rpm", 0),
    "sensor_19": ("PCNfR", "Demanded corr. Nf", "rpm", 2),
    "sensor_20": ("W31", "HPT coolant bleed", "lbm/s", 2),
    "sensor_21": ("W32", "LPT coolant bleed", "lbm/s", 3),
}


def describe(sensor):
    """'sensor_11' -> 'sensor_11 · HPC outlet static pressure (Ps30)'."""
    name = SENSOR_DESCRIPTIONS.get(sensor)
    return f"{sensor} · {name}" if name and sensor != "cycle" else (name or sensor)
