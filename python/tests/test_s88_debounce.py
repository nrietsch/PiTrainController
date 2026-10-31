from __future__ import annotations

from pitraincontroller.s88.debounce import OffDelayFilter


def test_on_is_reported_immediately():
    f = OffDelayFilter(2, 0.5)
    assert f.update([0, 1], 0.0) == [(1, 0, 1)]


def test_off_waits_for_the_delay():
    f = OffDelayFilter(1, 0.5)
    f.update([1], 0.0)
    assert f.update([0], 0.1) == []
    assert f.update([0], 0.4) == []
    assert f.update([0], 0.5) == [(0, 1, 0)]


def test_a_single_scan_pulse_stays_on_for_the_whole_delay():
    f = OffDelayFilter(1, 0.5)
    assert f.update([1], 1.0) == [(0, 0, 1)]
    assert f.update([0], 1.05) == []
    assert f.update([0], 1.45) == []
    assert f.update([0], 1.5) == [(0, 1, 0)]


def test_flicker_within_the_delay_is_one_continuous_occupancy():
    f = OffDelayFilter(1, 0.5)
    events = []
    # on, off for 180ms, on, off for 250ms, on: each gap shorter than the delay
    for now, bit in [(0.0, 1), (0.2, 0), (0.38, 1), (0.6, 0), (0.63, 1)]:
        events += f.update([bit], now)
    assert events == [(0, 0, 1)]


def test_off_gap_restarts_the_delay_each_time_the_contact_comes_back():
    f = OffDelayFilter(1, 0.5)
    f.update([1], 0.0)
    f.update([0], 0.3)
    f.update([1], 0.4)  # back before the 0.5s were up
    assert f.update([0], 0.8) == []  # only 0.4s since last on
    assert f.update([0], 0.9) == [(0, 1, 0)]


def test_zero_delay_reports_every_change_as_read():
    f = OffDelayFilter(1, 0.0)
    assert f.update([1], 0.0) == [(0, 0, 1)]
    assert f.update([0], 0.05) == [(0, 1, 0)]
    assert f.update([1], 0.10) == [(0, 0, 1)]


def test_bits_are_independent():
    f = OffDelayFilter(2, 0.5)
    f.update([1, 1], 0.0)
    assert f.update([0, 1], 0.6) == [(0, 1, 0)]
