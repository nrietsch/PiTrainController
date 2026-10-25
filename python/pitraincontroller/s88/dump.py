"""
Bring-up tool: continuously scans the S88 bus and prints the raw bit vector,
so "dead bus" (constant 0s or 1s) can be told apart from "live bus, nothing
triggered" -- the service only logs *changes*, so both look identical there.

The S88 service owns the GPIO lines, so stop it first:
    sudo systemctl stop pitraincontroller-s88

Run via: python3 -m pitraincontroller.s88.dump [--modules 1] [--bits-per-module 16]
         [--load-active-high 0|1] [--reset-active-high 0|1]

Contact 1 is the leftmost bit. A line is printed whenever any bit changes,
plus a status line every few seconds so you can see the scan is running.
"""

from __future__ import annotations

import argparse
import time

from pitraincontroller.common.config import PINS, S88Config
from pitraincontroller.s88.driver import S88Bus


def format_bits(bits: list[int], group: int = 8) -> str:
    chars = "".join(str(b) for b in bits)
    return " ".join(chars[i:i + group] for i in range(0, len(chars), group))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modules", type=int, default=1, help="modules on the chain (default: 1)")
    parser.add_argument("--bits-per-module", type=int, default=16, help="inputs per module (default: 16)")
    parser.add_argument("--load-active-high", choices=("0", "1"), help="override LOAD polarity")
    parser.add_argument("--reset-active-high", choices=("0", "1"), help="override RESET polarity")
    parser.add_argument("--status-every", type=float, default=5.0, help="seconds between status lines")
    args = parser.parse_args()

    overrides: dict[str, object] = {"module_count": args.modules, "bits_per_module": args.bits_per_module}
    if args.load_active_high is not None:
        overrides["load_active_high"] = args.load_active_high == "1"
    if args.reset_active_high is not None:
        overrides["reset_active_high"] = args.reset_active_high == "1"
    config = S88Config(**overrides)

    from pitraincontroller.common.gpio import GpioBus  # lgpio is Pi-only

    print(
        f"{config.total_bits} bits, LOAD active-{'high' if config.load_active_high else 'low'}, "
        f"RESET active-{'high' if config.reset_active_high else 'low'} -- Ctrl+C to stop"
    )
    start = time.monotonic()
    last_status = start
    last_bits: list[int] | None = None
    with GpioBus() as gpio:
        bus = S88Bus(gpio, PINS, config)
        try:
            while True:
                bits = bus.scan()
                now = time.monotonic()
                if bits != last_bits:
                    changed = (
                        [i + 1 for i, (a, b) in enumerate(zip(last_bits, bits)) if a != b]
                        if last_bits is not None
                        else []
                    )
                    suffix = f"   changed: contact {', '.join(map(str, changed))}" if changed else ""
                    print(f"[{now - start:7.1f}s] {format_bits(bits)}{suffix}")
                    last_bits = bits
                    last_status = now
                elif now - last_status >= args.status_every:
                    print(f"[{now - start:7.1f}s] {format_bits(bits)}   (unchanged)")
                    last_status = now
                time.sleep(config.poll_interval_s)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
