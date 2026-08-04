"""
systemd entrypoint for the S88 driver: runs the S88Bus scan loop,
publishes bit changes as Marklin CAN "S88 Event" frames onto can0, and
sends a one-byte pulse to a local activity socket on every scan so the
LED service (M3) can drive the S88 activity LED without re-implementing
S88 polling itself.

Run via: python -m pitraincontroller.s88.service
(wired up as pitraincontroller-s88.service in systemd/)
"""

from __future__ import annotations

import logging
import os
import socket
import time

import can

from pitraincontroller.common.config import PINS, CanConfig, S88Config, S88_ACTIVITY_SOCKET
from pitraincontroller.common.gpio import GpioBus
from pitraincontroller.common.marklin_can import derive_hash_placeholder, encode_s88_event
from pitraincontroller.s88.driver import S88Bus

logging.basicConfig(
    level=os.environ.get("PITC_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("pitraincontroller.s88")


def _activity_client_socket() -> socket.socket:
    """A plain (unbound) client socket for sending activity pulses to
    whatever is listening at S88_ACTIVITY_SOCKET (the LED service, once
    M3 exists). Binding/creating that socket is the listener's job, not
    ours -- if nothing's listening yet, sendto() just fails harmlessly."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.setblocking(False)
    return sock


def _pulse_activity(sock: socket.socket) -> None:
    try:
        sock.sendto(b"\x01", S88_ACTIVITY_SOCKET)
    except OSError:
        pass  # no listener yet -- not fatal, just means no LED blink


def main() -> None:
    s88_config = S88Config()
    can_config = CanConfig()

    bus = can.Bus(channel=can_config.interface, interface="socketcan")
    activity_sock = _activity_client_socket()

    with GpioBus() as gpio:
        s88 = S88Bus(gpio, PINS, s88_config)
        log.info(
            "S88 driver starting: %d modules x %d bits = %d contacts, poll every %.0fms",
            s88_config.module_count,
            s88_config.bits_per_module,
            s88_config.total_bits,
            s88_config.poll_interval_s * 1000,
        )

        last_change_time = [0.0] * s88_config.total_bits

        def on_change(bit_index: int, old: int, new: int) -> None:
            now = time.monotonic()
            previous = last_change_time[bit_index]
            elapsed_ms = (now - previous) * 1000 if previous else 0.0
            last_change_time[bit_index] = now

            contact_id = bit_index + 1  # S88 contacts are conventionally 1-based
            frame = encode_s88_event(
                device_uid=can_config.device_uid,
                contact_id=contact_id,
                state_old=old,
                state_new=new,
                # Spec doesn't pin the tick unit down precisely; 10ms/tick
                # is the widely-used community convention.
                time_ticks=min(int(elapsed_ms / 10), 0xFFFF),
                hash_value=derive_hash_placeholder(can_config.device_uid),
            )
            try:
                bus.send(frame)
            except can.CanError:
                log.exception("failed to send S88 event frame for contact %d", contact_id)
            log.info("S88 contact %d: %d -> %d", contact_id, old, new)

        try:
            while True:
                s88.scan(on_change=on_change)
                _pulse_activity(activity_sock)
                time.sleep(s88_config.poll_interval_s)
        except KeyboardInterrupt:
            pass
        finally:
            bus.shutdown()


if __name__ == "__main__":
    main()
