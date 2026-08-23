"""
Interactive CLI: prints a human-readable decode of every frame seen on a
SocketCAN interface (default can0), via marklin_decode.decode_frame.

Not a systemd service -- this is a manual diagnostic tool. Typical use:
reading a newly-registered MFX locomotive's Loc-ID off the bus while
operating it from an MS2 (see docs/CS2-GATEWAY.md), the same workflow
the 2016 predecessor project's `-v` flag supported. can0 is a shared
SocketCAN interface, so this can run alongside the gateway service and/or
Rocrail without conflict.

Run via: python3 -m pitraincontroller.gateway.monitor [-i can0]
"""

from __future__ import annotations

import argparse

import can

from pitraincontroller.common.marklin_decode import decode_frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--interface", default="can0", help="SocketCAN interface (default: can0)")
    args = parser.parse_args()

    bus = can.Bus(channel=args.interface, interface="socketcan")
    print(f"Listening on {args.interface} -- Ctrl+C to stop")
    try:
        while True:
            msg = bus.recv()
            if msg is None:
                continue
            print(decode_frame(msg.arbitration_id, bytes(msg.data)))
            print()
    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
