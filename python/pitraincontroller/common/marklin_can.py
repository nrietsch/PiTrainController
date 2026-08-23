"""
Marklin CAN protocol: frame construction shared by the S88 driver and the
CS2/CS3 gateway (so both encode/decode against one definition, not two).

Grounded in the official "CAN CS2 Protokoll" spec, version 2.0
(streaming.maerklin.de/public-media/cs2/cs2CAN-Protokoll-2_0.pdf),
sections referenced in each function's docstring.

CAN identifier layout (all Marklin CAN messages use 29-bit extended IDs):

    bit 28-25 (4 bits)  Priority
    bit 24-17 (8 bits)  Command
    bit 16    (1 bit)   Response flag
    bit 15-0  (16 bits) Hash

>>> IMPORTANT: the `hash_value` this module uses is currently a
>>> placeholder (see `derive_hash_placeholder`), not the real Marklin
>>> hash-collision-avoidance algorithm. That algorithm isn't implemented
>>> yet. This is fine for bench testing against a single fixed listener
>>> (e.g. Rocrail, a packet sniffer) but is NOT spec-correct for sharing a
>>> live bus with other real CS2/CS3-protocol devices, which rely on the
>>> hash field to detect and resolve ID collisions. Wire up the real
>>> algorithm here as part of M4 (the CAN/CS2-CS3 gateway, which also owns
>>> the device-UID assignment handshake) before relying on this outside a
>>> controlled bench setup.
"""

from __future__ import annotations

import struct

import can


def build_can_id(priority: int, command: int, response: bool, hash_value: int) -> int:
    if not 0 <= priority <= 0xF:
        raise ValueError("priority must fit in 4 bits (0-15)")
    if not 0 <= command <= 0xFF:
        raise ValueError("command must fit in 8 bits (0-255)")
    if not 0 <= hash_value <= 0xFFFF:
        raise ValueError("hash_value must fit in 16 bits")
    return (priority << 25) | (command << 17) | ((1 if response else 0) << 16) | hash_value


def parse_can_id(can_id: int) -> tuple[int, int, bool, int]:
    """Inverse of build_can_id: returns (priority, command, response, hash_value)."""
    priority = (can_id >> 25) & 0xF
    command = (can_id >> 17) & 0xFF
    response = bool((can_id >> 16) & 0x1)
    hash_value = can_id & 0xFFFF
    return priority, command, response, hash_value


def derive_hash_placeholder(device_uid: int) -> int:
    """Placeholder only -- see module docstring. Returns device_uid as-is,
    truncated to 16 bits."""
    return device_uid & 0xFFFF


# Command 0x11, "Rueckmelde Event" / S88 Event (spec section 5.2, page 40).
# CAN-ID command nibble is documented directly as 0x22 = 0x11 << 1 | resp(0),
# consistent with the bit layout above.
S88_EVENT_COMMAND = 0x11


def encode_s88_event(
    device_uid: int,
    contact_id: int,
    state_old: int,
    state_new: int,
    time_ticks: int,
    hash_value: int,
) -> can.Message:
    """
    Builds the DLC=8 "Rueckmelde Event" (S88 Event) frame -- spec section
    5.2 describes this form as both the unsolicited change notification
    and the reply to a query/subscribe request; the spec text says "the
    response to a command is always DLC=8", so Response is set for this
    form. Priority is 1 per the spec's example table (queries use 0).

    Data layout (big-endian throughout), 8 bytes:
        D0-D1  Geraetekennung   (16-bit device UID)
        D2-D3  Kontaktkennung   (16-bit contact ID)
        D4     Zustand alt      (previous state, typically 0/1)
        D5     Zustand neu      (new state, typically 0/1)
        D6-D7  Zeit             (time since last change; unit not pinned
                                 down precisely in the extracted spec text
                                 -- 10ms ticks is the widely-used
                                 community convention, applied by the
                                 caller before this function sees it)
    """
    data = struct.pack(
        ">HHBBH",
        device_uid & 0xFFFF,
        contact_id & 0xFFFF,
        state_old & 0xFF,
        state_new & 0xFF,
        time_ticks & 0xFFFF,
    )
    arbitration_id = build_can_id(priority=1, command=S88_EVENT_COMMAND, response=True, hash_value=hash_value)
    return can.Message(arbitration_id=arbitration_id, is_extended_id=True, data=data, dlc=8)
