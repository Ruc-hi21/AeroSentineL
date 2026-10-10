"""Rolling-element bearing: FEMTO-ST PRONOSTIA run-to-failure vibration, one row per minute."""

from src.components.base import Channel, ComponentSpec, Profile

_FEATURES = [  # suffix, code, name, description, unit, decimals, module
    ("rms", "RMS", "RMS level", "RMS vibration", "g", 3, "housing"),
    ("peak", "Pk", "Peak", "Peak vibration", "g", 2, "housing"),
    ("kurt", "Kurt", "Kurtosis", "Kurtosis (impulsiveness)", "", 2, "races"),
    ("crest", "CF", "Crest factor", "Crest factor (peak over RMS)", "", 2, "races"),
    ("skew", "Skew", "Skewness", "Skewness", "", 3, "races"),
    ("band1", "B1", "0-1 kHz", "Vibration RMS, 0 to 1 kHz band", "g", 3, "shaft"),
    ("band2", "B2", "1-3 kHz", "Vibration RMS, 1 to 3 kHz band", "g", 3, "rolling"),
    ("band3", "B3", "3-6 kHz", "Vibration RMS, 3 to 6 kHz band", "g", 3, "rolling"),
    ("band4", "B4", "6-12.8 kHz", "Vibration RMS, 6 to 12.8 kHz band", "g", 3, "races"),
    ("centroid_khz", "fc", "Spectral centroid", "Spectral centroid", "kHz", 2, "rolling"),
]
_AXES = (("h", "horizontal", "h"), ("v", "vertical", "v"))

BEARING = ComponentSpec(
    key="bearing", name="Rolling-element bearing", unit_title="Bearing", unit_plural="bearings",
    id_column="bearing", time_column="minute", time_title="Minute", life_unit="minutes",
    settings=("speed_rpm", "load_kn"),
    setting_labels=("shaft speed (rpm)", "radial load (kN)"),
    setting_scale=(300.0, 1.0), reference_settings=(1800.0, 4.0),
    channels=tuple(
        Channel(f"{ax}_{s}", f"{code}{tag}", f"{name}, {axis[:4]}.", f"{desc}, {axis} accelerometer", unit, dec, mod)
        for ax, axis, tag in _AXES for s, code, name, desc, unit, dec, mod in _FEATURES),
    modules=(("shaft", "Shaft"), ("rolling", "Rolling elements"), ("races", "Races"), ("housing", "Housing")),
    profiles={"FEMTO": Profile("FEMTO", "PRONOSTIA rig, 3 speed and load conditions, accelerated wear", 3,
                               ("rolling contact wear",), 12, 5)},
    # Damage on these bearings shows only late and suddenly, so beyond an hour every bearing looks the same.
    # 5-fold CV on training bearings: RUL cap 120 min gave RMSE 33.5, cap 60 gave 14.0 (minutes).
    rul_cap=60, risk_limits={"FAILURE_LIKELY": 10, "HIGH_RISK": 20, "AT_RISK": 40},
    min_history=20, baseline_cycles=20,
    actions={"remove": "Replace the bearing before minute {cycle}",
             "schedule": "Plan bearing replacement within {life}",
             "inspect": "Inspect the {module}",
             "noun": "bearing"},
    data_note="FEMTO-ST PRONOSTIA accelerated bearing degradation (IEEE PHM 2012 challenge)",
)
