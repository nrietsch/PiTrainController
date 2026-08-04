# CS2/CS3 LAN gateway notes

Implementation: [`python/pitraincontroller/gateway/protocol.py`](../python/pitraincontroller/gateway/protocol.py)
(pure framing logic, unit-tested) and
[`python/pitraincontroller/gateway/service.py`](../python/pitraincontroller/gateway/service.py)
(the actual relay).

## What it does

A byte-transparent relay between `can0` (SocketCAN) and UDP broadcast
port 15731, using the same 13-byte-per-frame framing real Marklin
CAN2LAN gateways (the CS2, CS3, and Gleisbox 60113) use: 4-byte
big-endian CAN ID, 1-byte DLC, 8-byte data (zero-padded if DLC<8).
Anything on either side is forwarded as-is to the other — this process
does not decode or interpret specific Marklin command types.

Because it's a pure relay, it does **not** need to understand the
protocol's device-UID assignment handshake or hash-collision-avoidance
algorithm (see the caveat in `common/marklin_can.py`) — those only
matter for something *originating* traffic under its own protocol
identity (like the S88 service), not for something that only forwards
frames that arrived from elsewhere.

## Loopback handling

Sending a UDP broadcast from this same host can be delivered straight
back to this process's own listening socket (self-echo). Left
unhandled, a CAN→UDP relay would loop right back around as a UDP→CAN
relay and re-inject a duplicate frame onto the real bus. `EchoDedup` in
`service.py` guards against this: every frame just sent CAN→UDP is
remembered (id, data) for a short window (`PITC_GATEWAY_ECHO_DEDUP_WINDOW_S`,
default 200ms); an incoming UDP frame matching one of those is treated
as our own echo and dropped rather than re-sent to `can0`.

This is a heuristic, not a protocol-level solution — two independent
real devices emitting an identical `(id, data)` pair within the dedup
window would also get one of them dropped. Fine for a bridge; would need
revisiting for anything relying on strict delivery guarantees.

## Known gaps

- **Device-UID assignment handshake** (System command 1, sub-command 7
  in the official spec): real CS2/CS3-protocol devices are assigned a
  16-bit UID by the master at system startup. The gateway doesn't
  participate in this because it doesn't need to — it only relays
  frames, it doesn't originate them under its own identity.
- **Hash-collision-avoidance algorithm**: same reasoning — not needed
  for pure relay, but *is* needed by anything (like the S88 service)
  that originates its own CAN traffic. Currently a placeholder there
  (`derive_hash_placeholder` in `common/marklin_can.py`) — fine for
  bench testing against a single fixed listener, not yet spec-correct
  for a live multi-device bus. Worth implementing properly here once
  real hardware exists to test against, since the gateway is the
  natural place for all Marklin protocol-level logic to live.
- **Not yet verified against real hardware/traffic.** The framing
  itself is verified by unit test against the spec-documented byte
  layout; the actual relay loop, SocketCAN sharing behavior, and UDP
  broadcast delivery on a real LAN all still need a real Pi + Gleisbox +
  Rocrail/CS2 App to confirm end-to-end.
