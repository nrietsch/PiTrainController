"""
Pure LED state-machine logic (boot/heartbeat/fault pattern selection),
kept free of any GPIO/socket I/O so it can be unit-tested without
hardware. See leds/service.py for the process that drives real pins from
this.
"""

from __future__ import annotations

from pitraincontroller.common.config import LedConfig


class HeartbeatState:
    BOOT = "boot"
    RUNNING = "running"
    FAULT = "fault"


def heartbeat_led_level(state: str, elapsed_in_state: float, config: LedConfig) -> int:
    """Returns 0/1 for LED4 given the current heartbeat state and how long
    it's been in that state."""
    if state == HeartbeatState.BOOT:
        return 1  # steady on during the boot window
    if state == HeartbeatState.FAULT:
        phase = elapsed_in_state % config.fault_blink_period_s
        return 1 if phase < config.fault_blink_period_s / 2 else 0
    # RUNNING: brief periodic blip
    phase = elapsed_in_state % config.heartbeat_period_s
    return 1 if phase < config.heartbeat_on_s else 0


def next_heartbeat_state(
    *,
    elapsed_since_start: float,
    can_ok: bool,
    s88_seen_recently: bool,
    config: LedConfig,
) -> str:
    """Decides which of BOOT/RUNNING/FAULT should be active right now."""
    if elapsed_since_start < config.boot_duration_s:
        return HeartbeatState.BOOT
    if not can_ok or not s88_seen_recently:
        return HeartbeatState.FAULT
    return HeartbeatState.RUNNING
