"""
Decoding of SocketCAN error frames (linux/can/error.h).

The kernel reports controller state changes (TX warning, passive,
bus-off, restart) to sockets as pseudo-frames with CAN_ERR_FLAG set.
python-can strips that flag, leaving the error class in the low bits of
`arbitration_id` with DLC 8 -- which looks like a real Marklin frame
(class 0x04 and 0x40 resemble "System" command IDs) unless the caller
checks `Message.is_error_frame` first.
"""

from __future__ import annotations

_ERROR_CLASSES = (
    (0x001, "TX timeout"),
    (0x002, "lost arbitration"),
    (0x004, "controller problem"),
    (0x008, "protocol violation"),
    (0x010, "transceiver status"),
    (0x020, "no ACK received"),
    (0x040, "BUS-OFF"),
    (0x080, "bus error"),
    (0x100, "controller restarted"),
)

_CONTROLLER_FLAGS = (
    (0x01, "RX overflow"),
    (0x02, "TX overflow"),
    (0x04, "RX warning"),
    (0x08, "TX warning"),
    (0x10, "RX passive"),
    (0x20, "TX passive"),
    (0x40, "back to error-active"),
)


def describe_error_frame(error_class: int, data: bytes) -> str:
    names = [name for bit, name in _ERROR_CLASSES if error_class & bit]
    text = ", ".join(names) if names else f"unknown class 0x{error_class:X}"
    if error_class & 0x004 and len(data) > 1:
        flags = [name for bit, name in _CONTROLLER_FLAGS if data[1] & bit]
        if flags:
            text += f" ({', '.join(flags)})"
    return f"SocketCAN ERROR FRAME (controller state, not bus traffic): {text}"
