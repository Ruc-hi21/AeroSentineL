"""Component registry, column mapping, derived channels and the recognition fingerprint."""

import numpy as np
import pandas as pd

from src.components import COMPONENTS, channel, get, spec_of_profile, to_canonical
from src.features.engineering import derive_channels, extra_features
from src.router import FEATURE_NAMES, fingerprint
from tests.conftest import make_engines


def test_every_profile_names_its_component_and_channels_are_unique():
    keys = [c.key for spec in COMPONENTS.values() for c in (*spec.channels, *spec.derived)]
    assert len(keys) == len(set(keys))
    assert spec_of_profile("FD003").key == "turbofan"
    assert spec_of_profile("PCOE").key == "battery"
    assert spec_of_profile("FEMTO").key == "bearing"


def test_unit_labels_read_like_the_component():
    assert get("turbofan").label(34) == "Engine 034"
    assert get("battery").label(6) == "Cell B0006"
    assert get("bearing").label(13) == "Bearing 1_3"


def test_component_columns_map_to_unit_and_cycle():
    df = pd.DataFrame({"bearing": [11, 11], "minute": [1, 2], "h_rms": [0.3, 0.4]})
    out = to_canonical(df, get("bearing"))
    assert list(out.columns[:2]) == ["unit", "cycle"]


def test_channel_lookup_spans_components():
    assert channel("sensor_11").code == "Ps30"
    assert channel("capacity_ah").module == "stack"
    assert channel("v_kurt").module == "races"
    assert channel("ambient_c").code == "Tamb"  # operating settings are named too


def test_state_of_health_is_relative_to_the_first_discharges():
    df = pd.DataFrame({"unit": [1] * 6, "cycle": range(1, 7), "capacity_ah": [2.0, 2.0, 2.0, 1.8, 1.7, 1.6]})
    out = derive_channels(df, get("battery"))
    assert np.allclose(out["soh"], [100, 100, 100, 90, 85, 80])
    extra = extra_features(out.assign(ambient_c=24.0, load_a=2.0), get("battery"))
    assert {"soh__margin", "soh__extrap10", "ambient_c__setting"} <= set(extra.columns)
    assert extra_features(make_engines(), get("turbofan")) is None  # turbofan inputs are unchanged


def test_fingerprint_ignores_column_names_and_order():
    df = make_engines(n_units=3, cycles=50)
    renamed = df.rename(columns={c: f"col_{i}" for i, c in enumerate(df.columns)})
    values = list(renamed.columns[2:])
    shuffled = renamed[[*renamed.columns[:2], *values[::-1]]]
    a, b = fingerprint(df), fingerprint(shuffled)
    assert set(a) == set(FEATURE_NAMES)
    assert all(np.isclose(a[k], b[k]) for k in FEATURE_NAMES)
    assert a["has_units"] == 1.0 and np.isclose(a["log_units"], np.log10(3))
