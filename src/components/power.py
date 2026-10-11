"""Power electronics: IGBT switches under thermal overstress (NASA PCoE), one row per minute of ageing.

Readings come from 2 ms oscilloscope captures of the switching transistor (see power_data.py). The
on-state collector-emitter voltage and on-resistance rise as the die attach and bond wires degrade;
the gate and current readings show the drive and the load the device still carries.
"""

from src.components.base import Channel, ComponentSpec, Profile

POWER = ComponentSpec(
    key="power", name="Power electronics", unit_title="Device", unit_plural="devices",
    id_column="device", time_column="minute", time_title="Minute", life_unit="minutes",
    settings=(), setting_labels=(), setting_scale=(), reference_settings=(),
    channels=(
        Channel("vce_on", "VCE(on)", "On-state voltage", "Collector-emitter voltage while switched on", "V", 3, "bond"),
        Channel("r_on", "Ron", "On-resistance", "On-state voltage over collector current", "ohm", 3, "bond"),
        Channel("vce_ripple", "dVCE", "On-state ripple", "Variation of the on-state voltage within a capture", "V", 4, "bond"),
        Channel("vce_off", "VCE(off)", "Off-state voltage", "Collector-emitter voltage while switched off", "V", 3, "die"),
        Channel("ice_on", "IC", "Collector current", "Collector current while switched on", "A", 3, "die"),
        Channel("vge_on", "VGE", "Gate voltage", "Gate-emitter voltage while switched on", "V", 2, "gate"),
        Channel("pkg_temp", "Tpkg", "Package temp", "Package temperature (logger counts, relative only)", "", 1, "thermal"),
    ),
    modules=(("gate", "Gate drive"), ("die", "IGBT die"), ("bond", "Bond wires and die attach"),
             ("thermal", "Package and heat sink")),
    profiles={"IGBT": Profile("IGBT", "IRG4BC30K IGBTs aged by thermal overstress with a square gate signal", 1,
                              ("latch-up after thermal overstress",), 3, 1)},
    rul_cap=40, risk_limits={"FAILURE_LIKELY": 5, "HIGH_RISK": 10, "AT_RISK": 20},
    min_history=3, baseline_cycles=3, unit_prefix="D", unit_digits=2,
    actions={"remove": "Replace the switch before minute {cycle}",
             "schedule": "Plan a power-module replacement within {life}",
             "inspect": "Inspect the {module}",
             "noun": "device"},
    data_note="NASA PCoE IGBT accelerated ageing (thermal overstress), four devices with usable switching captures",
)
