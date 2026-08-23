from __future__ import annotations

from pitraincontroller.common.config import Pins, S88Config
from pitraincontroller.s88.driver import S88Bus


class FakeGpioBus:
    """Minimal stand-in for GpioBus (see common/gpio.py) -- records writes
    and replays a queued sequence of bit values on read(), so S88Bus's pure
    scan/diff logic is testable without lgpio or real hardware."""

    def __init__(self) -> None:
        self.writes: list[tuple[int, int]] = []
        self.claimed_outputs: dict[int, int] = {}
        self.claimed_inputs: set[int] = set()
        self._queued_reads: list[int] = []

    def queue_reads(self, values: list[int]) -> None:
        self._queued_reads = list(values)

    def claim_output(self, gpio: int, initial: int = 0) -> None:
        self.claimed_outputs[gpio] = initial

    def claim_input(self, gpio: int) -> None:
        self.claimed_inputs.add(gpio)

    def write(self, gpio: int, level: int) -> None:
        self.writes.append((gpio, level))

    def read(self, gpio: int) -> int:
        return self._queued_reads.pop(0)


def _bus(module_count: int = 1, bits_per_module: int = 4) -> tuple[S88Bus, FakeGpioBus]:
    pins = Pins()
    config = S88Config(module_count=module_count, bits_per_module=bits_per_module)
    gpio = FakeGpioBus()
    return S88Bus(gpio, pins, config), gpio


def test_claims_pins_on_construction():
    bus, gpio = _bus()
    assert gpio.claimed_inputs == {bus._pins.s88_data}
    assert bus._pins.s88_clock in gpio.claimed_outputs
    assert bus._pins.s88_load in gpio.claimed_outputs
    assert bus._pins.s88_reset in gpio.claimed_outputs


def test_initial_state_is_all_zero():
    bus, _ = _bus(bits_per_module=8)
    assert bus.state == [0] * 8


def test_scan_returns_bit_vector_in_order():
    bus, gpio = _bus(bits_per_module=4)
    gpio.queue_reads([0, 1, 0, 1])
    result = bus.scan()
    assert result == [0, 1, 0, 1]
    assert bus.state == [0, 1, 0, 1]


def test_scan_reports_only_changed_bits_in_index_order():
    bus, gpio = _bus(bits_per_module=4)
    gpio.queue_reads([0, 0, 0, 0])
    bus.scan()

    gpio.queue_reads([0, 1, 0, 1])
    changes = []
    bus.scan(on_change=lambda i, old, new: changes.append((i, old, new)))

    assert changes == [(1, 0, 1), (3, 0, 1)]


def test_scan_with_no_changes_reports_nothing():
    bus, gpio = _bus(bits_per_module=4)
    gpio.queue_reads([1, 0, 1, 0])
    bus.scan()

    gpio.queue_reads([1, 0, 1, 0])
    changes = []
    bus.scan(on_change=lambda i, old, new: changes.append((i, old, new)))

    assert changes == []


def test_scan_pulses_reset_and_load_before_reading():
    bus, gpio = _bus(bits_per_module=2)
    gpio.queue_reads([0, 0])
    bus.scan()

    reset_writes = [level for gpio_num, level in gpio.writes if gpio_num == bus._pins.s88_reset]
    load_writes = [level for gpio_num, level in gpio.writes if gpio_num == bus._pins.s88_load]
    # Reset defaults active-high (assert then release); load defaults
    # active-low (assert 0 then release 1) -- see S88Config docstring.
    assert reset_writes == [1, 0]
    assert load_writes == [0, 1]
