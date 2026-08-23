from __future__ import annotations

from pitraincontroller.gateway import service as gateway_service


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_echo_dedup_flags_recent_matching_frame(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(gateway_service.time, "monotonic", clock)

    dedup = gateway_service.EchoDedup(window_s=0.2)
    dedup.note_sent(0x123, b"\x01\x02")

    assert dedup.is_recent_echo(0x123, b"\x01\x02") is True


def test_echo_dedup_ignores_non_matching_frame():
    dedup = gateway_service.EchoDedup(window_s=0.2)
    dedup.note_sent(0x123, b"\x01\x02")

    assert dedup.is_recent_echo(0x123, b"\x03\x04") is False
    assert dedup.is_recent_echo(0x456, b"\x01\x02") is False


def test_echo_dedup_expires_after_window(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(gateway_service.time, "monotonic", clock)

    dedup = gateway_service.EchoDedup(window_s=0.2)
    dedup.note_sent(0x123, b"\x01\x02")

    clock.now += 0.25
    assert dedup.is_recent_echo(0x123, b"\x01\x02") is False


def test_echo_dedup_prunes_old_entries(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(gateway_service.time, "monotonic", clock)

    dedup = gateway_service.EchoDedup(window_s=0.2)
    dedup.note_sent(0x111, b"\x01")
    clock.now += 0.25
    dedup.note_sent(0x222, b"\x02")

    assert len(dedup._recent) == 1
    assert dedup._recent[0][1] == 0x222
