"""Past records: a later piece of a unit's log, joined to the stored earlier piece, scores like the complete log."""

import pytest

from src.config import SAMPLES_DIR
from src.data.loader import read_sensor_file
from src.pipeline import analyze
from src.store import HistoryStore

PIECES = [("FD001_engine_089_healthy.txt", "turbofan"), ("PCOE_cell_006_healthy.csv", "battery"),
          ("IGBT_device_003_healthy.csv", "power")]


@pytest.fixture
def store(tmp_path):
    s = HistoryStore(f"sqlite:///{tmp_path / 'history.db'}")
    yield s
    s.engine.dispose()


def _split(name):
    df = read_sensor_file(SAMPLES_DIR / name)
    age = df.columns[1]
    cut = df[age].quantile(0.6)
    return df, df[df[age] <= cut], df[df[age] > cut]


@pytest.mark.parametrize("name,component", PIECES)
def test_joined_piece_scores_like_the_full_log(store, name, component):
    full_df, first, second = _split(name)
    full = analyze(full_df, name=name, component=component)
    analyze(first, name=name, component=component, store=store)
    joined = analyze(second, name=name, component=component, store=store)

    assert joined.status != "FAILED" and joined.records["error"] is None
    assert len(joined.history) == len(full.history)
    assert joined.units.iloc[0]["predicted_rul"] == pytest.approx(full.units.iloc[0]["predicted_rul"])
    assert list(joined.records["joined"].values())[0]["cycles"] == len(first)


def test_full_reupload_replaces_instead_of_doubling(store):
    name = PIECES[0][0]
    full_df, _, _ = _split(name)
    for _ in range(2):
        r = analyze(full_df, name=name, component="turbofan", store=store)
    assert r.records["joined"] == {}
    assert store.summary()["cycles"].tolist() == [len(full_df)]
    assert len(store.forecasts_of("turbofan", r.subset, r.units.iloc[0]["unit"])) == 2


def test_units_of_other_fleets_stay_apart(store):
    full_df, first, second = _split(PIECES[0][0])
    analyze(first, name="FD001_x.txt", component="turbofan", store=store)
    r = analyze(second, name="FD003_x.txt", component="turbofan", store=store)
    assert r.records["joined"] == {}


def test_without_a_store_nothing_is_recorded():
    full_df, _, _ = _split(PIECES[0][0])
    assert analyze(full_df, name=PIECES[0][0], component="turbofan").records is None
