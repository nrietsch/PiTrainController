from __future__ import annotations

import pytest

from pitraincontroller.common.marklin_can import (
    build_can_id,
    encode_s88_event,
    parse_can_id,
)


def test_build_and_parse_can_id_round_trip():
    can_id = build_can_id(priority=1, command=0x11, response=True, hash_value=0x2F17)
    assert parse_can_id(can_id) == (1, 0x11, True, 0x2F17)


def test_build_can_id_matches_known_example():
    # From the original project's MFX walkthrough: Cmd 0x06, Hash 0x2F17.
    can_id = build_can_id(priority=0, command=0x06, response=False, hash_value=0x2F17)
    assert can_id == 0x000C2F17


@pytest.mark.parametrize(
    "kwargs",
    [
        {"priority": -1, "command": 0, "response": False, "hash_value": 0},
        {"priority": 16, "command": 0, "response": False, "hash_value": 0},
        {"priority": 0, "command": -1, "response": False, "hash_value": 0},
        {"priority": 0, "command": 256, "response": False, "hash_value": 0},
        {"priority": 0, "command": 0, "response": False, "hash_value": -1},
        {"priority": 0, "command": 0, "response": False, "hash_value": 0x10000},
    ],
)
def test_build_can_id_rejects_out_of_range_fields(kwargs):
    with pytest.raises(ValueError):
        build_can_id(**kwargs)


def test_encode_s88_event_byte_layout():
    msg = encode_s88_event(
        device_uid=0x4711,
        contact_id=0x0003,
        state_old=0,
        state_new=1,
        time_ticks=0x00AB,
        hash_value=0x2F17,
    )
    assert msg.is_extended_id
    assert msg.dlc == 8
    assert msg.data == bytes([0x47, 0x11, 0x00, 0x03, 0x00, 0x01, 0x00, 0xAB])
    # priority=1, command=0x11, response=True per the function's docstring
    assert parse_can_id(msg.arbitration_id) == (1, 0x11, True, 0x2F17)


def test_encode_s88_event_truncates_fields_to_declared_width():
    msg = encode_s88_event(
        device_uid=0x1FFFF,  # 17 bits -- should truncate to 16
        contact_id=0,
        state_old=0x1FF,  # 9 bits -- should truncate to 8
        state_new=0,
        time_ticks=0,
        hash_value=0,
    )
    assert msg.data[0:2] == bytes([0xFF, 0xFF])
    assert msg.data[4] == 0xFF
