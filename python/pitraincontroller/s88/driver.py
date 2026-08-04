"""
S88 bit-bang driver: implements the classic RESET -> LOAD -> (read, CLOCK)xN
read cycle over four GPIO lines, diffs consecutive scans against the
previous state, and reports individual bit changes via a callback.

Sequence and rationale are documented in `S88Config` (common/config.py)
and docs/S88.md.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable, Optional

from pitraincontroller.common.config import Pins, S88Config

if TYPE_CHECKING:
    # Only needed for the type hint below -- kept out of the runtime import
    # path so this module (and its diff/scan logic) can be unit-tested
    # without `lgpio` installed/available, e.g. off-Pi. Any object
    # implementing claim_output/claim_input/write/read works at runtime
    # (see GpioBus for the real implementation).
    from pitraincontroller.common.gpio import GpioBus

# (bit_index, old_state, new_state) -> None
BitChangeCallback = Callable[[int, int, int], None]


class S88Bus:
    def __init__(self, gpio: GpioBus, pins: Pins, config: S88Config) -> None:
        self._gpio = gpio
        self._pins = pins
        self._config = config
        self._state = [0] * config.total_bits

        load_idle = 0 if config.load_active_high else 1
        reset_idle = 0 if config.reset_active_high else 1

        gpio.claim_output(pins.s88_clock, initial=0)
        gpio.claim_output(pins.s88_load, initial=load_idle)
        gpio.claim_output(pins.s88_reset, initial=reset_idle)
        gpio.claim_input(pins.s88_data)

    @property
    def state(self) -> list[int]:
        return list(self._state)

    def _pulse_reset(self) -> None:
        active = 1 if self._config.reset_active_high else 0
        idle = 1 - active
        self._gpio.write(self._pins.s88_reset, active)
        time.sleep(self._config.pulse_width_s)
        self._gpio.write(self._pins.s88_reset, idle)
        time.sleep(self._config.pulse_width_s)

    def _latch(self) -> None:
        active = 1 if self._config.load_active_high else 0
        idle = 1 - active
        self._gpio.write(self._pins.s88_load, active)
        time.sleep(self._config.pulse_width_s)
        self._gpio.write(self._pins.s88_load, idle)
        time.sleep(self._config.pulse_width_s)

    def _clock_pulse(self) -> None:
        self._gpio.write(self._pins.s88_clock, 1)
        time.sleep(self._config.half_period_s)
        self._gpio.write(self._pins.s88_clock, 0)
        time.sleep(self._config.half_period_s)

    def scan(self, on_change: Optional[BitChangeCallback] = None) -> list[int]:
        """
        Performs one full scan and returns the freshly-read bit vector.
        `on_change(bit_index, old, new)` is invoked once per bit whose
        value differs from the previous scan (in bit_index order).
        """
        self._pulse_reset()
        self._latch()

        new_state = [0] * self._config.total_bits
        for i in range(self._config.total_bits):
            # Read first: after LOAD releases, bit 0 (Q7 of the last chip
            # in the chain) is already valid with no clock needed yet.
            new_state[i] = self._gpio.read(self._pins.s88_data)
            self._clock_pulse()

        if on_change is not None:
            for i, (old, new) in enumerate(zip(self._state, new_state)):
                if old != new:
                    on_change(i, old, new)

        self._state = new_state
        return list(new_state)
