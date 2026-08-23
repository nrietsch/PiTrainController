from __future__ import annotations

import pytest

from pitraincontroller.gateway.protocol import pack_udp_frame, unpack_udp_frame


def test_pack_unpack_round_trip():
    can_id = 0x000C2F17
    data = bytes([0x00, 0x00, 0x40, 0x07, 0x00, 0x01])
    packet = pack_udp_frame(can_id, data)
    assert len(packet) == 13
    assert unpack_udp_frame(packet) == (can_id, data)


def test_pack_zero_pads_short_data():
    packet = pack_udp_frame(0x1, b"\xAB")
    assert packet[4] == 1  # DLC
    assert packet[5:13] == b"\xAB" + b"\x00" * 7


def test_pack_rejects_data_over_8_bytes():
    with pytest.raises(ValueError):
        pack_udp_frame(0x1, bytes(9))


def test_pack_rejects_can_id_over_32_bits():
    with pytest.raises(ValueError):
        pack_udp_frame(0x1_0000_0000, b"")


def test_unpack_rejects_wrong_length_packet():
    with pytest.raises(ValueError):
        unpack_udp_frame(b"\x00" * 12)
    with pytest.raises(ValueError):
        unpack_udp_frame(b"\x00" * 14)


def test_unpack_rejects_dlc_over_8():
    # Hand-craft a 13-byte packet with an invalid DLC byte (9).
    packet = bytes([0, 0, 0, 0, 9]) + bytes(8)
    with pytest.raises(ValueError):
        unpack_udp_frame(packet)
