"""
Off-delay filter for S88 contacts: a contact that has gone on stays on until
it has been off continuously for `off_delay_s`. Pure logic, no I/O.

Why: a wheel crossing an isolated rail section on dirty or intermittent track
produces on/off blips a fraction of a second apart, and a single-scan pulse
can be too short for a client to notice. This turns those into one clear
occupancy. The cost is that "free" is reported `off_delay_s` late.
"""

from __future__ import annotations

# (bit_index, old_state, new_state), the same shape S88Bus.scan reports
Change = tuple[int, int, int]


class OffDelayFilter:
    def __init__(self, size: int, off_delay_s: float) -> None:
        self._delay = off_delay_s
        self._stable = [0] * size
        self._last_on = [0.0] * size

    def update(self, bits: list[int], now: float) -> list[Change]:
        """Feed one raw scan taken at `now`; returns the changes to report."""
        changes: list[Change] = []
        for i, raw in enumerate(bits):
            if raw:
                self._last_on[i] = now
                if not self._stable[i]:
                    self._stable[i] = 1
                    changes.append((i, 0, 1))
            elif self._stable[i] and now - self._last_on[i] >= self._delay:
                self._stable[i] = 0
                changes.append((i, 1, 0))
        return changes
