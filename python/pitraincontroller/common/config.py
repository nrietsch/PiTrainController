"""
Central configuration: GPIO pin assignments and tunables shared across the
S88, LED, and CAN gateway services.

Pin numbers are BCM GPIO numbering, cross-checked against both the
project brief and the PCB Design v4.0 board manual (docs/reference/) --
the two agree on every pin listed here.

Everything is overridable via environment variables so the same code
works unmodified across board revisions/test rigs; systemd unit
`Environment=`/`EnvironmentFile=` directives are the intended way to set
these on a real install (see docs/INSTALL.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value is not None else default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value is not None else default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Pins:
    # CAN controller (MCP25625) -- handled by the mcp251x kernel driver via
    # the device tree overlay, listed here for documentation/LED-service use
    # only; nothing in userspace drives these GPIOs directly.
    can_irq: int = field(default_factory=lambda: _env_int("PITC_GPIO_CAN_IRQ", 25))
    can_reset: int = field(default_factory=lambda: _env_int("PITC_GPIO_CAN_RESET", 27))

    # S88 bit-bang bus
    s88_clock: int = field(default_factory=lambda: _env_int("PITC_GPIO_S88_CLOCK", 22))
    s88_load: int = field(default_factory=lambda: _env_int("PITC_GPIO_S88_LOAD", 23))
    s88_reset: int = field(default_factory=lambda: _env_int("PITC_GPIO_S88_RESET", 24))
    s88_data: int = field(default_factory=lambda: _env_int("PITC_GPIO_S88_DATA", 17))

    # Status LEDs
    led_can: int = field(default_factory=lambda: _env_int("PITC_GPIO_LED_CAN", 5))
    led_s88: int = field(default_factory=lambda: _env_int("PITC_GPIO_LED_S88", 12))
    led_heartbeat: int = field(default_factory=lambda: _env_int("PITC_GPIO_LED_HEARTBEAT", 6))


@dataclass(frozen=True)
class S88Config:
    """
    S88 bus electrical/timing parameters.

    Polarity defaults reflect the S88 daughterboard as currently designed
    (74HC165 shift registers, confirmed via schematic):
      - LOAD is active-LOW: asserting it LOW triggers the 74HC165s'
        SH/LD# parallel-load; releasing it HIGH puts them in shift mode.
      - CLOCK is active-HIGH: a rising edge shifts the next bit (per the
        74HC165 datasheet), so we sample DATA *before* each clock pulse.
      - RESET is a single active-HIGH pulse issued once per full scan,
        before LOAD. The official Marklin CAN protocol spec describes
        classic S88 modules as edge-latching -- a momentary sensor trigger
        stays "set" until the bus is read/reset -- which is what RESET
        addresses even on modules built from plain shift registers.

    The S88 daughterboard hardware is still being finalized (see
    docs/reference/hardware-manual-v4.md) -- these are best-known-good
    defaults, not yet confirmed against a built board. Flip the relevant
    `*_active_high` flag if real hardware disagrees; nothing else in the
    driver needs to change.
    """

    module_count: int = field(default_factory=lambda: _env_int("PITC_S88_MODULE_COUNT", 5))
    bits_per_module: int = field(default_factory=lambda: _env_int("PITC_S88_BITS_PER_MODULE", 16))

    load_active_high: bool = field(
        default_factory=lambda: _env_str("PITC_S88_LOAD_ACTIVE_HIGH", "0") == "1"
    )
    reset_active_high: bool = field(
        default_factory=lambda: _env_str("PITC_S88_RESET_ACTIVE_HIGH", "1") == "1"
    )

    # Half-period of the bit-bang loop. opendcc.de's documented S88 timing
    # requires a clock cycle >= ~30us (>=15us high/low each); this is a
    # MINIMUM, not a maximum -- the protocol is deliberately slow/tolerant,
    # so running an order of magnitude slower than spec is safe and gives
    # generous margin against Python/OS scheduling jitter. Tighten this
    # once real hardware is available and scan-rate matters more than
    # margin.
    half_period_s: float = field(default_factory=lambda: _env_float("PITC_S88_HALF_PERIOD_S", 150e-6))

    # Pulse width for RESET and the LOAD-asserted phase. Also generous
    # relative to the sub-microsecond setup/hold times real shift
    # registers need.
    pulse_width_s: float = field(default_factory=lambda: _env_float("PITC_S88_PULSE_WIDTH_S", 50e-6))

    # Poll cycle interval (time between full bus scans).
    poll_interval_s: float = field(default_factory=lambda: _env_float("PITC_S88_POLL_INTERVAL_S", 0.05))

    @property
    def total_bits(self) -> int:
        return self.module_count * self.bits_per_module


@dataclass(frozen=True)
class CanConfig:
    interface: str = field(default_factory=lambda: _env_str("PITC_CAN_INTERFACE", "can0"))
    bitrate: int = field(default_factory=lambda: _env_int("PITC_CAN_BITRATE", 250_000))

    # Marklin CAN protocol "Geraetekennung" (16-bit device UID). Real CS2/
    # CS3-aware devices are assigned this by the master at system startup
    # (System command 1, sub-command 7) -- that handshake lives in the
    # gateway service (M4), which is responsible for keeping this value
    # current. Until that's wired up, this static fallback is used, which
    # is fine for bench testing against a single fixed listener but is not
    # spec-correct for a real multi-device CAN-S88 bus.
    device_uid: int = field(default_factory=lambda: _env_int("PITC_CAN_DEVICE_UID", 0x4711))


@dataclass(frozen=True)
class LedConfig:
    """Timing for the LED4 boot/heartbeat/fault state machine and the
    LED1/LED3 activity-blink behavior (brief's LED spec, section 4/95-98)."""

    boot_duration_s: float = field(default_factory=lambda: _env_float("PITC_LED_BOOT_DURATION_S", 60.0))

    heartbeat_period_s: float = field(default_factory=lambda: _env_float("PITC_LED_HEARTBEAT_PERIOD_S", 2.0))
    heartbeat_on_s: float = field(default_factory=lambda: _env_float("PITC_LED_HEARTBEAT_ON_S", 0.1))

    # Fault pattern is deliberately much faster than the heartbeat so the
    # two are unambiguous at a glance.
    fault_blink_period_s: float = field(default_factory=lambda: _env_float("PITC_LED_FAULT_BLINK_PERIOD_S", 0.3))

    # How long an activity LED (CAN/S88) stays lit after the most recent
    # event, so brief/fast traffic still reads as a visible blink rather
    # than an imperceptible flicker.
    activity_hold_s: float = field(default_factory=lambda: _env_float("PITC_LED_ACTIVITY_HOLD_S", 0.08))

    # If no S88 activity pulse arrives for this long (after the boot
    # window), treat it as "S88 chain not returning valid data" for fault
    # purposes -- comfortably longer than the S88 driver's default
    # poll_interval_s (50ms) to avoid false positives from normal jitter.
    s88_fault_timeout_s: float = field(default_factory=lambda: _env_float("PITC_LED_S88_FAULT_TIMEOUT_S", 2.0))

    tick_interval_s: float = field(default_factory=lambda: _env_float("PITC_LED_TICK_INTERVAL_S", 0.05))


# S88 activity pulses, published so the LED service (M3) can drive the S88
# activity LED without needing to duplicate S88 polling logic.
S88_ACTIVITY_SOCKET = os.environ.get("PITC_S88_ACTIVITY_SOCKET", "/run/pitraincontroller/s88-activity.sock")

PINS = Pins()
