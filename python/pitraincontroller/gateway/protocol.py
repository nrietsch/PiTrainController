"""
CS2/CS3 LAN (CAN2LAN) wire framing: pure pack/unpack logic, no I/O, so
it's directly unit-testable.

Per the observed/documented behavior of Marklin's own CAN2LAN gateways
(the CS2/CS3 and the Gleisbox 60113): the gateway listens on UDP port
15731, discards any packet whose length isn't exactly 13 bytes, and
otherwise interprets it as one CAN frame:

    bytes 0-3  CAN identifier, big-endian (network byte order), 32 bits
               wide though Marklin's protocol only ever populates the
               low 29 bits (extended frame format)
    byte  4    DLC (data length code), 0-8
    bytes 5-12 data, zero-padded out to 8 bytes if DLC < 8

Traffic in the other direction (CAN -> UDP) uses the identical framing,
broadcast to the LAN.
"""

from __future__ import annotations

import struct

UDP_PACKET_LEN = 13
MAX_DLC = 8

_STRUCT = struct.Struct(">IB8s")  # CAN ID (u32), DLC (u8), data (8 bytes, zero-padded)


def pack_udp_frame(can_id: int, data: bytes) -> bytes:
    if not 0 <= can_id <= 0xFFFFFFFF:
        raise ValueError("can_id must fit in 32 bits")
    if len(data) > MAX_DLC:
        raise ValueError(f"data must be at most {MAX_DLC} bytes, got {len(data)}")
    padded = data + b"\x00" * (MAX_DLC - len(data))
    return _STRUCT.pack(can_id, len(data), padded)


def unpack_udp_frame(packet: bytes) -> tuple[int, bytes]:
    if len(packet) != UDP_PACKET_LEN:
        raise ValueError(f"expected a {UDP_PACKET_LEN}-byte packet, got {len(packet)}")
    can_id, dlc, payload = _STRUCT.unpack(packet)
    if dlc > MAX_DLC:
        raise ValueError(f"invalid DLC {dlc} in packet (max {MAX_DLC})")
    return can_id, payload[:dlc]
