"""What AeroSentinel needs to know about a monitored component.

Every component (turbofan, battery cell, bearing) is described once by a ComponentSpec. The
pipeline, the component-recognition model and the console all read from it, so adding a component
means adding a spec, a data builder and a trained model, not changing the pipeline.

Internally every table uses the same two key columns: `unit` (which engine, cell or bearing) and
`cycle` (its age: engine cycle, discharge cycle or minute of running). Upload files may use the
component's own names for them (`cell`, `bearing`, `minute`), which the reader maps.
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Channel:
    key: str  # column name in the canonical table
    code: str  # short engineering symbol, e.g. "T50", "Cap", "RMSh"
    name: str  # compact name for tight layouts
    description: str  # full plain-language name
    unit: str
    decimals: int
    module: str  # module (part of the component) the reading reports on


@dataclass(frozen=True)
class Profile:
    """A trained model variant within a component (for the turbofan, one per C-MAPSS subset)."""
    key: str
    description: str
    conditions: int  # distinct operating conditions in its training data
    fault_modes: tuple = ()
    train_units: int = 0
    test_units: int = 0


@dataclass(frozen=True)
class ComponentSpec:
    key: str
    name: str  # "Turbofan engine"
    unit_title: str  # "Engine"
    unit_plural: str  # "engines"
    id_column: str  # id column name in upload files ("unit", "cell", "bearing")
    time_column: str  # age column name in upload files ("cycle", "minute")
    time_title: str  # "Cycle", "Minute"
    life_unit: str  # unit of RUL: "cycles", "minutes"
    settings: tuple  # operating-setting columns (define operating conditions)
    setting_labels: tuple  # axis labels for the operating-envelope chart, same order as settings
    setting_scale: tuple  # typical span of each setting, for distances between conditions
    reference_settings: tuple  # the condition every reading is corrected to
    channels: tuple  # Channel, ...
    modules: tuple  # (key, name), in physical order
    profiles: dict  # key -> Profile
    rul_cap: int  # early life counts as fully healthy beyond this many life units
    risk_limits: dict  # band -> upper RUL limit, most severe first
    min_history: int  # fewer cycles than this = insufficient data
    baseline_cycles: int  # first N cycles of each training unit = healthy reference
    derived: tuple = ()  # Channels computed from the measured ones (not in upload files)
    settings_as_features: bool = False  # give the models the operating settings when they set the wear rate
    unit_prefix: str = ""  # for labels: "B" + 0005
    unit_digits: int = 3
    actions: dict = field(default_factory=dict)  # wording of suggested actions
    data_note: str = ""  # one line on where the training data comes from

    @property
    def channel_keys(self):
        return [c.key for c in self.channels]

    @property
    def model_channels(self):
        """Channels the models may use: measured plus derived."""
        return [*self.channel_keys, *(c.key for c in self.derived)]

    @property
    def columns(self):
        """Canonical internal column order: unit, cycle, settings, channels."""
        return ["unit", "cycle", *self.settings, *self.channel_keys]

    @property
    def upload_columns(self):
        return [self.id_column, self.time_column, *self.settings, *self.channel_keys]

    @property
    def default_profile(self):
        return next(iter(self.profiles))

    def label(self, unit):
        """'Engine 034', 'Cell B0005', 'Bearing 1_3'."""
        return f"{self.unit_title} {self.unit_id(unit)}"

    def unit_id(self, unit):
        if self.key == "bearing":  # FEMTO naming: condition _ index
            u = int(unit)
            return f"{u // 10}_{u % 10}"
        return f"{self.unit_prefix}{int(unit):0{self.unit_digits}d}"

    def module_name(self, key):
        return dict(self.modules).get(key, key)

    def scale(self):
        return np.asarray(self.setting_scale, dtype=float)
