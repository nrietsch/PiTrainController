"""
systemd entrypoint for the LED status service. Drives three
software-controlled LEDs per the board manual (section 4):

    LED1 (GPIO5,  blue)   -- CAN bus activity (TX or RX)
    LED3 (GPIO12, orange) -- S88 poll activity
    LED4 (GPIO6,  red)    -- boot / heartbeat / fault

(LED2/green is a passive hardware power indicator -- not driven here.)

Activity sources are observed directly rather than relayed through the
other services, so this stays a small independent process that can't
wedge the S88/CAN paths and doesn't need its own IPC contract with them
beyond the one-way S88 activity socket:

    - CAN activity: this service opens its own raw SocketCAN socket on
      can0 purely to observe traffic timestamps. SocketCAN is a shared
      kernel interface -- any number of sockets can bind to the same
      interface at once -- so this doesn't interfere with the S88/gateway
      services or Rocrail also using can0.
    - S88 activity: listens on the Unix datagram socket the S88 service
      pulses once per scan (see common/config.S88_ACTIVITY_SOCKET). This
      service owns creating/binding that socket (the S88 service is just
      a client that sends to it, tolerating "nobody's listening yet").
    - Fault conditions: can0 missing/down, or no S88 activity pulse
      received for longer than `LedConfig.s88_fault_timeout_s` (once
      past the boot window) -- covers "CAN controller not responding"
      and "S88 chain not returning valid data" per the brief's LED spec.

Run via: python -m pitraincontroller.leds.service
(wired up as pitraincontroller-leds.service in systemd/)
"""

from __future__ import annotations

import logging
import os
import socket
import time

from pitraincontroller.common.config import PINS, CanConfig, LedConfig, S88_ACTIVITY_SOCKET
from pitraincontroller.common.gpio import GpioBus
from pitraincontroller.leds.state import HeartbeatState, heartbeat_led_level, next_heartbeat_state

logging.basicConfig(
    level=os.environ.get("PITC_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("pitraincontroller.leds")


def _open_can_activity_socket(interface: str) -> "socket.socket | None":
    try:
        sock = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        sock.bind((interface,))
        sock.setblocking(False)
        return sock
    except OSError:
        log.warning("could not open raw CAN socket on %s (interface missing?)", interface, exc_info=True)
        return None


def _open_s88_activity_socket(path: str) -> socket.socket:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(path)
    sock.setblocking(False)
    return sock


def _drain_and_check_activity(sock: "socket.socket | None", bufsize: int) -> bool:
    """Non-blocking drain of all pending datagrams; returns True if at
    least one was waiting (i.e. there was activity since the last call)."""
    if sock is None:
        return False
    saw_any = False
    while True:
        try:
            sock.recv(bufsize)
            saw_any = True
        except BlockingIOError:
            break
        except OSError:
            break
    return saw_any


def _can_interface_up(interface: str) -> bool:
    try:
        with open(f"/sys/class/net/{interface}/operstate") as f:
            return f.read().strip() == "up"
    except OSError:
        return False


def main() -> None:
    can_config = CanConfig()
    led_config = LedConfig()

    can_sock = _open_can_activity_socket(can_config.interface)
    s88_sock = _open_s88_activity_socket(S88_ACTIVITY_SOCKET)

    start_time = time.monotonic()
    last_can_activity = 0.0
    last_s88_activity = 0.0
    state = HeartbeatState.BOOT
    state_entered_at = start_time

    log.info(
        "LED service starting: boot window %.0fs, then heartbeat every %.1fs",
        led_config.boot_duration_s, led_config.heartbeat_period_s,
    )

    with GpioBus() as gpio:
        gpio.claim_output(PINS.led_can, initial=0)
        gpio.claim_output(PINS.led_s88, initial=0)
        gpio.claim_output(PINS.led_heartbeat, initial=1)  # steady on immediately at boot

        try:
            while True:
                now = time.monotonic()

                if _drain_and_check_activity(can_sock, 128):
                    last_can_activity = now
                if _drain_and_check_activity(s88_sock, 8):
                    last_s88_activity = now

                # -- Determine heartbeat/fault state --
                elapsed_since_start = now - start_time
                can_ok = can_sock is not None and _can_interface_up(can_config.interface)
                s88_seen_recently = (now - last_s88_activity) < led_config.s88_fault_timeout_s

                new_state = next_heartbeat_state(
                    elapsed_since_start=elapsed_since_start,
                    can_ok=can_ok,
                    s88_seen_recently=s88_seen_recently,
                    config=led_config,
                )

                if new_state != state:
                    if new_state == HeartbeatState.FAULT:
                        log.warning(
                            "entering FAULT state (can_ok=%s, s88_seen_recently=%s)",
                            can_ok, s88_seen_recently,
                        )
                    else:
                        log.info("heartbeat state: %s -> %s", state, new_state)
                    state = new_state
                    state_entered_at = now

                gpio.write(PINS.led_heartbeat, heartbeat_led_level(state, now - state_entered_at, led_config))
                gpio.write(PINS.led_can, 1 if (now - last_can_activity) < led_config.activity_hold_s else 0)
                gpio.write(PINS.led_s88, 1 if (now - last_s88_activity) < led_config.activity_hold_s else 0)

                time.sleep(led_config.tick_interval_s)
        except KeyboardInterrupt:
            pass
        finally:
            if can_sock is not None:
                can_sock.close()
            s88_sock.close()


if __name__ == "__main__":
    main()
