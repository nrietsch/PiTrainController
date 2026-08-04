"""
systemd entrypoint for the CS2/CS3 LAN gateway: relays can0 <-> UDP
broadcast 15731 using the framing in gateway/protocol.py.

This is a byte-transparent relay -- it doesn't decode/interpret specific
Marklin command semantics, which is why it doesn't need the device-UID
assignment handshake or the real hash-collision-avoidance algorithm
(both still-open items, see common/marklin_can.py's module docstring) to
work correctly as a pure bridge. Those only matter if this process needs
to originate its own protocol-level traffic under its own identity,
which the gateway itself doesn't -- it only ever forwards frames that
originated elsewhere (the S88 service, a real Gleisbox, Rocrail, a CS2
App, etc).

can0 is a shared SocketCAN interface -- Rocrail (or anything else) can
bind to it directly at the same time as this gateway relays to/from UDP;
see docs/reference/hardware-manual-v4.md and the project README for why
that's safe.

Run via: python -m pitraincontroller.gateway.service
(wired up as pitraincontroller-gateway.service in systemd/)
"""

from __future__ import annotations

import logging
import os
import socket
import time
from collections import deque

import can

from pitraincontroller.common.config import CanConfig
from pitraincontroller.gateway.protocol import UDP_PACKET_LEN, pack_udp_frame, unpack_udp_frame

logging.basicConfig(
    level=os.environ.get("PITC_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("pitraincontroller.gateway")

UDP_PORT = 15731
BROADCAST_ADDR = os.environ.get("PITC_GATEWAY_BROADCAST_ADDR", "255.255.255.255")

# UDP broadcast sent from this process can be delivered straight back to
# this process's own listening socket on the same host. Without
# filtering that out, a CAN->UDP relay would loop straight back around
# as a UDP->CAN relay and duplicate every frame onto the bus. This
# window-based dedup catches that; it's a heuristic (an unrelated device
# emitting an identical id+data pair within the window would also be
# dropped), not a protocol-level solution -- fine for a bridge, would
# need revisiting for anything relying on frame delivery guarantees.
ECHO_DEDUP_WINDOW_S = float(os.environ.get("PITC_GATEWAY_ECHO_DEDUP_WINDOW_S", "0.2"))


def _open_udp_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", port))
    sock.setblocking(False)
    return sock


class EchoDedup:
    def __init__(self, window_s: float) -> None:
        self._window_s = window_s
        self._recent: deque[tuple[float, int, bytes]] = deque()

    def note_sent(self, can_id: int, data: bytes) -> None:
        self._recent.append((time.monotonic(), can_id, data))
        self._prune()

    def is_recent_echo(self, can_id: int, data: bytes) -> bool:
        self._prune()
        return any(rid == can_id and rdata == data for _, rid, rdata in self._recent)

    def _prune(self) -> None:
        cutoff = time.monotonic() - self._window_s
        while self._recent and self._recent[0][0] < cutoff:
            self._recent.popleft()


def main() -> None:
    can_config = CanConfig()
    bus = can.Bus(channel=can_config.interface, interface="socketcan")
    udp_sock = _open_udp_socket(UDP_PORT)
    dedup = EchoDedup(ECHO_DEDUP_WINDOW_S)

    log.info(
        "CS2/CS3 gateway starting: %s <-> UDP broadcast %s:%d",
        can_config.interface, BROADCAST_ADDR, UDP_PORT,
    )

    try:
        while True:
            did_work = False

            # CAN -> UDP
            msg = bus.recv(timeout=0.0)
            if msg is not None:
                did_work = True
                data = bytes(msg.data)
                dedup.note_sent(msg.arbitration_id, data)
                try:
                    udp_sock.sendto(pack_udp_frame(msg.arbitration_id, data), (BROADCAST_ADDR, UDP_PORT))
                except OSError:
                    log.exception("failed to send UDP frame")

            # UDP -> CAN
            try:
                packet, _addr = udp_sock.recvfrom(65535)
                did_work = True
                if len(packet) != UDP_PACKET_LEN:
                    log.debug("ignoring non-CS2 UDP packet of length %d", len(packet))
                else:
                    can_id, data = unpack_udp_frame(packet)
                    if dedup.is_recent_echo(can_id, data):
                        log.debug("dropping likely self-echo: id=0x%08X", can_id)
                    else:
                        frame = can.Message(arbitration_id=can_id, is_extended_id=True, data=data, dlc=len(data))
                        try:
                            bus.send(frame)
                        except can.CanError:
                            log.exception("failed to send CAN frame from UDP")
            except BlockingIOError:
                pass
            except OSError:
                log.exception("error receiving UDP packet")

            if not did_work:
                time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()
        udp_sock.close()


if __name__ == "__main__":
    main()
