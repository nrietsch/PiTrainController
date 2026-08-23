"""
Human-readable decoding of Marklin CAN frames, for interactive monitoring
-- e.g. watching the bus while operating a loco from an MS2 to read off a
newly-registered MFX locomotive's Loc-ID, the workflow described in the
2016 predecessor project's docs (ifoedit.com/RaspiCS2En.html#RocrailConfig).

Ported from that predecessor's `DecodeFrameData()` in
docs/reference/legacy-picans88-2016/PiCanS88/CAN2LAN.cpp (lines
528-754). Byte layout for every command below matches that C
implementation, with two deliberate deviations from it, both noted
inline where they occur: an unrecognized-DLC case returns a description
instead of silently printing garbage, and the Command 0x21 (Config Data
Stream) CRC field is decoded correctly instead of reproducing a
copy/paste bug in the original printf call.

Decode-only, no I/O -- see gateway/monitor.py for the CLI that reads
real frames off a SocketCAN interface and prints what this module
returns.
"""

from __future__ import annotations

from pitraincontroller.common.marklin_can import parse_can_id


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "big")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "big")


def _decode_system(data: bytes, response: bool) -> str:
    if len(data) < 5:
        return "truncated frame"
    target_uid = _u32(data, 0)
    sub_cmd = data[4]

    if sub_cmd == 0x00:
        detail = f"System Stop - Zielgeraet-UID: [{target_uid:08X}]"
    elif sub_cmd == 0x01:
        detail = f"System Go - Zielgeraet-UID: [{target_uid:08X}]"
    elif sub_cmd == 0x02:
        detail = f"System Halt - Zielgeraet-UID: [{target_uid:08X}]"
    elif sub_cmd == 0x03:
        detail = f"Lok Nothalt - Loc-ID: [{target_uid:08X}]"
    elif sub_cmd == 0x04:
        detail = f"Lok Zyklus Stop - Loc-ID: [{target_uid:08X}]"
    elif sub_cmd == 0x05:
        detail = f"Lok Datenprotokoll - Loc-ID: [{target_uid:08X}], Gleisprotokoll: [{data[5]:02X}]"
    elif sub_cmd == 0x06:
        detail = f"Schaltzeit Zubehoerdecoder festlegen - Zielgeraet-UID: [{target_uid:08X}], Zeit: [{_u16(data, 5):04X}]"
    elif sub_cmd == 0x07:
        detail = f"Fast Read fuer MFX SID - Absender-UID: [{target_uid:08X}], MFX-SID: [{_u16(data, 5):04X}]"
    elif sub_cmd == 0x08:
        flags = data[5]
        protocols = [name for bit, name in ((0x01, "MM2"), (0x02, "MFX"), (0x04, "DCC")) if flags & bit]
        suffix = f" ({', '.join(protocols)})" if protocols else ""
        detail = f"Gleisprotokoll Frei Schalten - Ziel-UID: [{target_uid:08X}], Param: [{flags:02X}]{suffix}"
    elif sub_cmd == 0x09:
        detail = f"MFX set Neuanmeldezaehler - Zielgeraet-UID: [{target_uid:08X}], Neu-Zaehler: [{_u16(data, 5):04X}]"
    elif sub_cmd == 0x0A:
        detail = f"System Ueberlast - Absender-UID: [{target_uid:08X}], Kanalnr: [{data[5]:02X}]"
    elif sub_cmd == 0x0B:
        detail = _decode_system_status(data, target_uid, response)
    elif sub_cmd == 0x0C:
        detail = _decode_geraetekennung(data, target_uid)
    elif sub_cmd == 0x80:
        detail = f"System Reset - Zielgeraet-UID: [{target_uid:08X}], ResetZiel: [{data[5]:02X}]"
    else:
        detail = "unknown Systemcommand"
    return f"SubCmd 0x{sub_cmd:02X}: {detail}"


def _decode_system_status(data: bytes, target_uid: int, response: bool) -> str:
    dlc = len(data)
    if not response and dlc == 6:
        return f"System Status Anfrage - Zielgeraet-UID: [{target_uid:08X}], Kanalnr: [{data[5]:02X}]"
    if not response and dlc == 8:
        return f"System Status Antwort - Absender-UID: [{target_uid:08X}], Kanalnr: [{data[5]:02X}], Konfigurationswert: [{_u16(data, 6):04X}]"
    if response and dlc == 7:
        return f"System Status Antwort - Zielgeraet-UID: [{target_uid:08X}], Kanalnr: [{data[5]:02X}], True/False: [{data[6]:02X}]"
    if response and dlc == 8:
        return f"System Status Antwort - Absender-UID: [{target_uid:08X}], Kanalnr: [{data[5]:02X}], Messwert: [{_u16(data, 6):04X}]"
    if response and dlc == 6:
        return f"System Status Antwort - Zielgeraet-UID: [{target_uid:08X}], Kanalnr existiert nicht!"
    return "unrecognized DLC"


def _decode_geraetekennung(data: bytes, target_uid: int) -> str:
    dlc = len(data)
    if dlc == 5:
        return f"Geraetekennung - Zielgeraet-UID: [{target_uid:08X}]"
    if dlc == 7:
        return f"Geraetekennung - Zielgeraet-UID: [{target_uid:08X}], SystemKenner: [{_u16(data, 5):04X}]"
    return "unrecognized DLC"


def _decode_lok_discovery(data: bytes, response: bool) -> str:
    dlc = len(data)
    if not response and dlc == 1:
        return f"Protokollkennung: [{data[0]:02X}]"
    if dlc == 5:
        return f"MFX-UID / Loc-ID: [{_u32(data, 0):08X}], Range / Protokollkennung: [{data[4]:02X}]"
    if response and dlc == 6:
        return f"MFX-UID / Loc-ID: [{_u32(data, 0):08X}], Range: [{data[4]:02X}], ASK-Verhaeltnis: [{data[5]:02X}]"
    return "unrecognized DLC"


def _decode_mfx_bind(data: bytes) -> str:
    return f"MFX-UID: [{_u32(data, 0):08X}], MFX-SID: [{_u16(data, 4):04X}]"


def _decode_mfx_verify(data: bytes) -> str:
    dlc = len(data)
    if dlc == 6:
        return f"MFX-UID: [{_u32(data, 0):08X}], MFX-SID: [{_u16(data, 4):04X}]"
    if dlc == 7:
        return f"MFX-UID: [{_u32(data, 0):08X}], MFX-SID: [{_u16(data, 4):04X}], ASK-Verhaeltnis: [{data[6]:02X}]"
    return "unrecognized DLC"


def _decode_lok_velocity(data: bytes) -> str:
    dlc = len(data)
    if dlc == 4:
        return f"Loc-ID: [{_u32(data, 0):08X}]"
    if dlc == 6:
        return f"Loc-ID: [{_u32(data, 0):08X}], Geschwindigkeit: [{_u16(data, 4):04X}]"
    return "unrecognized DLC"


def _decode_lok_direction(data: bytes) -> str:
    dlc = len(data)
    if dlc == 4:
        return f"Loc-ID: [{_u32(data, 0):08X}]"
    if dlc == 5:
        return f"Loc-ID: [{_u32(data, 0):08X}], Richtung: [{data[4]:02X}]"
    return "unrecognized DLC"


def _decode_lok_function(data: bytes) -> str:
    """Command 0x06 -- this is the frame that carries a newly-assigned
    MFX locomotive's address in its Loc-ID field (see module docstring)."""
    dlc = len(data)
    if dlc == 5:
        return f"Loc-ID: [{_u32(data, 0):08X}], Funktion: [{data[4]:02X}]"
    if dlc == 6:
        return f"Loc-ID: [{_u32(data, 0):08X}], Funktion: [{data[4]:02X}], Wert: [{data[5]:02X}]"
    if dlc == 8:
        return f"Loc-ID: [{_u32(data, 0):08X}], Funktion: [{data[4]:02X}], Wert: [{data[5]:02X}], Funktionswert: [{_u16(data, 6):04X}]"
    return "unrecognized DLC"


def _decode_read_config(data: bytes) -> str:
    dlc = len(data)
    if dlc == 6:
        return f"Loc-ID: [{_u32(data, 0):08X}], CV Index/Nummer: [{_u16(data, 4):04X}]"
    if dlc == 7:
        return f"Loc-ID: [{_u32(data, 0):08X}], CV Index/Nummer: [{_u16(data, 4):04X}], Anzahl/Wert: [{data[6]:02X}]"
    return "unrecognized DLC"


def _decode_write_config(data: bytes) -> str:
    if len(data) == 8:
        return f"Loc-ID: [{_u32(data, 0):08X}], CV Index/Nummer: [{_u16(data, 4):04X}], Wert: [{data[6]:02X}], Ctrl/Rslt: [{data[7]:02X}]"
    return "unrecognized DLC"


def _decode_accessory_switch(data: bytes) -> str:
    dlc = len(data)
    if dlc == 6:
        return f"Loc-ID: [{_u32(data, 0):08X}], Stellung: [{data[4]:02X}], Strom: [{data[5]:02X}]"
    if dlc == 8:
        return f"Loc-ID: [{_u32(data, 0):08X}], Stellung: [{data[4]:02X}], Strom: [{data[5]:02X}], Schaltzeit/Sonderwert: [{_u16(data, 6):04X}]"
    return "unrecognized DLC"


def _decode_s88_polling(data: bytes) -> str:
    dlc = len(data)
    if dlc == 5:
        return f"Geraet-UID: [{_u32(data, 0):08X}], Modulanzahl: [{data[4]:02X}]"
    if dlc == 7:
        return f"Geraet-UID: [{_u32(data, 0):08X}], Modulanzahl: [{data[4]:02X}], Zustand: [{_u16(data, 5):04X}]"
    return "unrecognized DLC"


def _decode_s88_event(data: bytes) -> str:
    """Counterpart to `encode_s88_event` in marklin_can.py."""
    dlc = len(data)
    if dlc == 4:
        return f"Geraetekennung: [{_u16(data, 0):04X}], Kontaktkennung: [{_u16(data, 2):04X}]"
    if dlc == 5:
        return f"Geraetekennung: [{_u16(data, 0):04X}], Kontaktkennung: [{_u16(data, 2):04X}], Parameter: [{data[4]:02X}]"
    if dlc == 8:
        return (
            f"Geraetekennung: [{_u16(data, 0):04X}], Kontaktkennung: [{_u16(data, 2):04X}], "
            f"Zustand alt: [{data[4]:02X}], Zustand neu: [{data[5]:02X}], Zeit: [{_u16(data, 6):04X}]"
        )
    return "unrecognized DLC"


_PING_DEVICE_TYPES = {
    (0x00, 0x00): "Gleis Format Prozessor 60213,60214 / Booster 60173, 60174",
    (0x00, 0x10): "Gleisbox 60112 und 60113",
    (0x00, 0x20): "Connect 6021 Art-Nr.60128",
    (0x00, 0x30): "MS 2 60653, Txxxxx",
    (0xFF, 0xE0): "Wireless Devices",
    (0xFF, 0xFF): "CS2-GUI (Master)",
}


def _decode_ping(data: bytes) -> str:
    dlc = len(data)
    if dlc == 0:
        return "Ping request"
    if dlc == 8:
        device_hi, device_lo = data[6], data[7]
        detail = (
            f"Absender-UID: [{_u32(data, 0):08X}], SW-Version: [{_u16(data, 4):04X}], "
            f"Geraetekennung: [{device_hi:02X}{device_lo:02X}]"
        )
        if device_hi == 0x00 and device_lo == 0x33:
            detail += f" (MS 2 60653, SW Version: {data[4]}.{data[5]})"
        else:
            name = _PING_DEVICE_TYPES.get((device_hi, device_lo))
            if name:
                detail += f" ({name})"
        return detail
    return "unrecognized DLC"


def _decode_status_config(data: bytes, response: bool) -> str:
    dlc = len(data)
    if not response and dlc == 5:
        return f"Zielgeraet-UID: [{_u32(data, 0):08X}], Index: [{data[4]:02X}]"
    if response and dlc == 8:
        return "Antwort mit Stream, Packet # ist in Hash"
    if response and dlc == 6:
        return f"Geraete-UID: [{_u32(data, 0):08X}], Index: [{data[4]:02X}], Paketanzahl: [{data[5]:02X}]"
    return "unrecognized DLC"


def _decode_config_data_stream(data: bytes) -> str:
    """The original C code's printf here had only 2 format specifiers for
    3 arguments (the CRC value it actually printed was the low 16 bits of
    the length field, not the distinct 2 bytes following it, which were
    computed but silently dropped) -- a copy/paste bug, not a spec
    detail. This decodes length + the real trailing CRC bytes instead of
    reproducing that bug."""
    dlc = len(data)
    if dlc in (6, 7):
        length = _u32(data, 0)
        crc = f"{_u16(data, 4):04X}" if dlc == 6 else f"{data[4]:02X}{data[5]:02X}{data[6]:02X}"
        return f"Datei/Streamlaenge in Bytes: [{length:08X}], CRC: [{crc}]"
    return "unrecognized DLC"


def _decode_automatic(data: bytes) -> str:
    dlc = len(data)
    if dlc == 6:
        return (
            f"Geraetekenner: [{_u16(data, 0):04X}], Automatik Funktion: [{_u16(data, 2):04X}], "
            f"Stellung/Status: [{data[4]:02X}], Parameter: [{data[5]:02X}]"
        )
    if dlc == 8:
        return f"Geraetekenner: [{_u16(data, 0):04X}], Automatik Funktion: [{_u16(data, 2):04X}], Loc-ID: [{_u32(data, 4):08X}]"
    return "unrecognized DLC"


_COMMAND_NAMES = {
    0x00: "System Cmd",
    0x01: "Lok Discovery",
    0x02: "MFX Bind",
    0x03: "MFX Verify",
    0x04: "Lok Geschwindigkeit",
    0x05: "Lok Richtung",
    0x06: "Lok Funktion",
    0x07: "Read Config",
    0x08: "Write Config",
    0x0B: "Zubehoer Schalten",
    0x10: "S88 Polling",
    0x11: "S88 Event",
    0x18: "Teilnehmer Ping",
    0x1D: "Statusdaten Konfiguration",
    0x20: "Anfordern Config Data",
    0x21: "Config Data Stream",
    0x30: "Automatik schalten",
}


def decode_frame(can_id: int, data: bytes) -> str:
    """
    Returns a two-line human-readable decode of one Marklin CAN frame,
    matching the style of the 2016 predecessor's verbose (-v) monitor
    output -- see module docstring for the source this was ported from.
    """
    priority, command, response, hash_value = parse_can_id(can_id)
    header = (
        f"CANID 0x{can_id:08X} Prio: 0x{priority:X} Cmd: 0x{command:02X} "
        f"Resp: 0x{int(response):X} Hash: 0x{hash_value:04X} DLC: [{len(data)}]"
    )

    name = _COMMAND_NAMES.get(command)
    if name is None:
        return f"{header}\nCommand: unknown (0x{command:02X})"

    try:
        if command == 0x00:
            detail = _decode_system(data, response)
        elif command == 0x01:
            detail = _decode_lok_discovery(data, response)
        elif command == 0x02:
            detail = _decode_mfx_bind(data)
        elif command == 0x03:
            detail = _decode_mfx_verify(data)
        elif command == 0x04:
            detail = _decode_lok_velocity(data)
        elif command == 0x05:
            detail = _decode_lok_direction(data)
        elif command == 0x06:
            detail = _decode_lok_function(data)
        elif command == 0x07:
            detail = _decode_read_config(data)
        elif command == 0x08:
            detail = _decode_write_config(data)
        elif command == 0x0B:
            detail = _decode_accessory_switch(data)
        elif command == 0x10:
            detail = _decode_s88_polling(data)
        elif command == 0x11:
            detail = _decode_s88_event(data)
        elif command == 0x18:
            detail = _decode_ping(data)
        elif command == 0x1D:
            detail = _decode_status_config(data, response)
        elif command == 0x20:
            detail = _decode_request_config_data()
        elif command == 0x21:
            detail = _decode_config_data_stream(data)
        elif command == 0x30:
            detail = _decode_automatic(data)
        else:
            detail = "unhandled"
    except IndexError:
        detail = "malformed frame (too short for this command)"

    return f"{header}\nCommand: {name}: {detail}"


def _decode_request_config_data() -> str:
    return "Anfordern Config Data fuer CS2"
