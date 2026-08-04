"""
Thin wrapper around `lgpio` for claiming a fixed set of GPIO lines and
reading/writing them. `lgpio` (the actively-maintained successor to
`pigpio`, same author) is used rather than `gpiozero`/`libgpiod` directly
because its `gpio_write`/`gpio_read` calls are simple, low-overhead, and
well-suited to the S88 bit-bang loop's timing.

On a Pi 3B+, the 40-pin header's GPIOs live on `/dev/gpiochip0`. If this
ever runs on hardware where that's not true (e.g. a Pi 5's RP1), override
via `PITC_GPIOCHIP`.
"""

from __future__ import annotations

import os

import lgpio


class GpioBus:
    def __init__(self, chip: int | None = None) -> None:
        self._chip_num = chip if chip is not None else int(os.environ.get("PITC_GPIOCHIP", "0"))
        self._handle = lgpio.gpiochip_open(self._chip_num)
        self._claimed_outputs: set[int] = set()
        self._claimed_inputs: set[int] = set()

    def claim_output(self, gpio: int, initial: int = 0) -> None:
        lgpio.gpio_claim_output(self._handle, gpio, initial)
        self._claimed_outputs.add(gpio)

    def claim_input(self, gpio: int) -> None:
        lgpio.gpio_claim_input(self._handle, gpio)
        self._claimed_inputs.add(gpio)

    def write(self, gpio: int, level: int) -> None:
        lgpio.gpio_write(self._handle, gpio, level)

    def read(self, gpio: int) -> int:
        return lgpio.gpio_read(self._handle, gpio)

    def close(self) -> None:
        for gpio in self._claimed_outputs | self._claimed_inputs:
            try:
                lgpio.gpio_free(self._handle, gpio)
            except lgpio.error:
                pass
        lgpio.gpiochip_close(self._handle)

    def __enter__(self) -> "GpioBus":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
