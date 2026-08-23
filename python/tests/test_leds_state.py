from __future__ import annotations

from pitraincontroller.common.config import LedConfig
from pitraincontroller.leds.state import (
    HeartbeatState,
    heartbeat_led_level,
    next_heartbeat_state,
)


def _config(**overrides) -> LedConfig:
    defaults = dict(
        boot_duration_s=60.0,
        heartbeat_period_s=2.0,
        heartbeat_on_s=0.1,
        fault_blink_period_s=0.3,
        activity_hold_s=0.08,
        s88_fault_timeout_s=2.0,
        tick_interval_s=0.05,
    )
    defaults.update(overrides)
    return LedConfig(**defaults)


def test_next_state_is_boot_within_boot_window():
    config = _config(boot_duration_s=60.0)
    state = next_heartbeat_state(
        elapsed_since_start=10.0, can_ok=True, s88_seen_recently=True, config=config
    )
    assert state == HeartbeatState.BOOT


def test_next_state_is_running_when_healthy_after_boot():
    config = _config(boot_duration_s=60.0)
    state = next_heartbeat_state(
        elapsed_since_start=61.0, can_ok=True, s88_seen_recently=True, config=config
    )
    assert state == HeartbeatState.RUNNING


def test_next_state_is_fault_when_can_down_after_boot():
    config = _config(boot_duration_s=60.0)
    state = next_heartbeat_state(
        elapsed_since_start=61.0, can_ok=False, s88_seen_recently=True, config=config
    )
    assert state == HeartbeatState.FAULT


def test_next_state_is_fault_when_no_recent_s88_after_boot():
    config = _config(boot_duration_s=60.0)
    state = next_heartbeat_state(
        elapsed_since_start=61.0, can_ok=True, s88_seen_recently=False, config=config
    )
    assert state == HeartbeatState.FAULT


def test_boot_level_is_steady_on():
    config = _config()
    assert heartbeat_led_level(HeartbeatState.BOOT, 0.0, config) == 1
    assert heartbeat_led_level(HeartbeatState.BOOT, 59.9, config) == 1


def test_running_level_blips_on_then_off():
    config = _config(heartbeat_period_s=2.0, heartbeat_on_s=0.1)
    assert heartbeat_led_level(HeartbeatState.RUNNING, 0.0, config) == 1
    assert heartbeat_led_level(HeartbeatState.RUNNING, 0.05, config) == 1
    assert heartbeat_led_level(HeartbeatState.RUNNING, 0.1, config) == 0
    assert heartbeat_led_level(HeartbeatState.RUNNING, 1.9, config) == 0
    # Wraps around to the next period.
    assert heartbeat_led_level(HeartbeatState.RUNNING, 2.05, config) == 1


def test_fault_level_blinks_50_50():
    config = _config(fault_blink_period_s=0.3)
    assert heartbeat_led_level(HeartbeatState.FAULT, 0.0, config) == 1
    assert heartbeat_led_level(HeartbeatState.FAULT, 0.1, config) == 1
    assert heartbeat_led_level(HeartbeatState.FAULT, 0.2, config) == 0
