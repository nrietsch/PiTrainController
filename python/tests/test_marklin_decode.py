from __future__ import annotations

from pitraincontroller.common.marklin_can import build_can_id, encode_s88_event
from pitraincontroller.common.marklin_decode import decode_frame


def test_decode_lok_funktion_matches_original_walkthrough_example():
    # From ifoedit.com/RaspiCS2En.html#RocrailConfig: a Lok Funktion frame
    # revealing a newly-registered MFX loco's address (Loc-ID 0x4007 ->
    # MFX range starts at 0x4000, so decimal address 7).
    can_id = 0x000C2F17
    data = bytes.fromhex("000040070001")
    out = decode_frame(can_id, data)
    assert "Command: Lok Funktion:" in out
    assert "Loc-ID: [00004007]" in out
    assert "Funktion: [00]" in out
    assert "Wert: [01]" in out


def test_decode_system_stop_and_go():
    stop = decode_frame(0x00000000, bytes.fromhex("0000000000"))
    assert "System Stop" in stop
    go = decode_frame(0x00000000, bytes.fromhex("0000000001"))
    assert "System Go" in go


def test_decode_system_protocol_enable_flags():
    # sub-command 0x08, param byte 0x06 = MFX (0x02) | DCC (0x04)
    frame = decode_frame(0x00000000, bytes.fromhex("00000000" "08" "06"))
    assert "Gleisprotokoll Frei Schalten" in frame
    assert "(MFX, DCC)" in frame


def test_decode_ping_known_device_type():
    # Absender-UID arbitrary, SW-Version arbitrary, Geraetekennung 0x0010 = Gleisbox
    data = bytes.fromhex("00004711") + bytes.fromhex("0100") + bytes.fromhex("0010")
    out = decode_frame(build_can_id(0, 0x18, False, 0), data)
    assert "Gleisbox 60112 und 60113" in out


def test_decode_s88_event_round_trips_with_encoder():
    msg = encode_s88_event(
        device_uid=0x1234,
        contact_id=0x0056,
        state_old=0,
        state_new=1,
        time_ticks=0x000A,
        hash_value=0x9999,
    )
    out = decode_frame(msg.arbitration_id, bytes(msg.data))
    assert "Command: S88 Event:" in out
    assert "Geraetekennung: [1234]" in out
    assert "Kontaktkennung: [0056]" in out
    assert "Zustand alt: [00]" in out
    assert "Zustand neu: [01]" in out


def test_decode_unknown_command():
    can_id = build_can_id(priority=0, command=0x7F, response=False, hash_value=0)
    out = decode_frame(can_id, b"")
    assert "unknown (0x7F)" in out


def test_decode_handles_truncated_frame_without_raising():
    # System sub-command 0x05 (Lok Datenprotokoll) reads a byte past the
    # target-UID+subcmd fields; a 5-byte frame is one byte short of that
    # and would IndexError without the guard in decode_frame.
    can_id = build_can_id(priority=0, command=0x00, response=False, hash_value=0)
    out = decode_frame(can_id, bytes.fromhex("0000000005"))
    assert "malformed frame" in out


def test_decode_header_fields():
    can_id = build_can_id(priority=1, command=0x11, response=True, hash_value=0xABCD)
    out = decode_frame(can_id, bytes(8))
    header = out.splitlines()[0]
    assert "Prio: 0x1" in header
    assert "Cmd: 0x11" in header
    assert "Resp: 0x1" in header
    assert "Hash: 0xABCD" in header
    assert "DLC: [8]" in header
