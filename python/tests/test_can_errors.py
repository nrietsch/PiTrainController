from __future__ import annotations

from pitraincontroller.common.can_errors import describe_error_frame


def test_controller_tx_passive():
    out = describe_error_frame(0x04, bytes([0, 0x20, 0, 0, 0, 0, 0, 0]))
    assert "controller problem" in out
    assert "TX passive" in out


def test_controller_tx_warning():
    out = describe_error_frame(0x04, bytes([0, 0x08, 0, 0, 0, 0, 0, 0]))
    assert "TX warning" in out


def test_bus_off():
    assert "BUS-OFF" in describe_error_frame(0x40, bytes(8))


def test_unknown_class():
    assert "unknown class 0x400" in describe_error_frame(0x400, bytes(8))
