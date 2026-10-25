from __future__ import annotations

from pitraincontroller.s88.dump import format_bits


def test_format_bits_groups_of_eight_contact_one_leftmost():
    bits = [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    assert format_bits(bits) == "10000000 01000000"


def test_format_bits_partial_last_group():
    assert format_bits([1, 1, 1], group=2) == "11 1"
