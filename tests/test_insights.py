"""Failure outlook: band probabilities turned into a chance per risk window and a deferral verdict."""

import pandas as pd
import pytest

from app import insights


def unit(**changes):
    row = {"component": "turbofan", "unit": 1, "cycle": 120, "predicted_rul": 40.0, "rul_low": 33.0, "rul_high": 48.0,
           "p_normal": 0.1, "p_at_risk": 0.7, "p_high_risk": 0.15, "p_failure_likely": 0.05,
           "health_condition": "normal", "health_score": 0.5, "review_reasons": []}
    return pd.Series({**row, **changes})


def test_outlook_adds_the_bands_into_nested_windows():
    out = insights.failure_outlook(unit())
    assert [o["limit"] for o in out] == [15, 30, 60]
    assert [o["p"] for o in out] == pytest.approx([0.05, 0.2, 0.9])


def test_outlook_needs_every_band_probability():
    assert insights.failure_outlook(unit().drop("p_normal")) == []
    assert insights.failure_chance(unit().drop("p_normal"), 10) is None


def test_chance_equals_the_band_probabilities_at_the_band_limits():
    row = unit()
    for o in insights.failure_outlook(row):
        assert insights.failure_chance(row, o["limit"]) == pytest.approx(o["p"])


def test_chance_grows_with_time_and_stays_a_probability():
    row = unit()
    values = [insights.failure_chance(row, n) for n in range(0, 61)]
    assert values[0] < 0.01
    assert all(0 <= v <= 1 for v in values)
    assert all(b >= a - 1e-12 for a, b in zip(values, values[1:]))


def test_chance_follows_the_rul_range_inside_a_band():
    # Range 33 to 48: by 48 cycles most of the at-risk band has been used up. An even spread
    # over the 30-cycle band would give only 0.2 + 0.7 * 17.5 / 30 = 0.61.
    assert insights.failure_chance(unit(), 48) > 0.8


def test_chance_without_a_rul_range_spreads_evenly_inside_a_band():
    row = unit().drop(["predicted_rul", "rul_low", "rul_high"])
    assert insights.failure_chance(row, 45) == pytest.approx(0.2 + 0.7 * 0.5)  # 45 cycles = 45.5, mid-band


def test_zero_width_range_is_handled():
    assert 0 <= insights.failure_chance(unit(rul_low=40.0, rul_high=40.0), 41) <= 1


def test_chance_beyond_the_at_risk_limit_is_refused():
    with pytest.raises(ValueError):
        insights.failure_chance(unit(), 61)


def test_margin_component_has_an_outlook_but_no_check_date():
    row = unit(component="hydraulic")
    assert [o["limit"] for o in insights.failure_outlook(row)] == [10, 30, 70]
    assert insights.failure_chance(row, 5) is None


@pytest.mark.parametrize("p, state", [(0.6, "CRITICAL"), (0.5, "CRITICAL"), (0.3, "WARNING"), (0.1, "DEGRADING"),
                                      (0.01, "HEALTHY"), (0.0, "HEALTHY")])
def test_defer_verdict_levels(p, state):
    assert insights.defer_verdict(p)[0] == state


@pytest.mark.parametrize("unit_state", ["CRITICAL", "WARNING"])
def test_a_unit_in_trouble_is_never_told_plainly_it_can_wait(unit_state):
    assert insights.defer_verdict(0.01, unit_state)[0] == "DEGRADING"
    assert insights.defer_verdict(0.6, unit_state)[0] == "CRITICAL"
    assert insights.defer_verdict(0.01, "HEALTHY")[0] == "HEALTHY"


def test_chance_is_written_for_operators():
    assert [insights.chance(p) for p in (0.001, 0.37, 0.999)] == ["<1%", "37%", ">99%"]
