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

## Track power (Start/Stop) without an MS2/CS2

You don't need a real Märklin controller on the bus to start/stop track
power — anything that can put a frame on `can0` will do, since it's a
shared SocketCAN interface.

**From Rocrail's GUI** — the power on/off button in Rocrail's toolbar
sends the same System-Stop/System-Go frame an MS2 would, using Rocrail's
own built-in CS2/MBUS CAN controller talking to `can0` directly. No
gateway or extra setup needed.

**From the CLI**, via `cansend` (part of `can-utils`, already installed
by `scripts/install.sh`):

```bash
cansend can0 00000000#0000000000   # System Stop
cansend can0 00000000#0000000001   # System Go
```

Frame layout: Command 0x00 (System command), data = 4-byte target UID
(`00000000` = broadcast/all devices) + 1-byte sub-command (`00` = Stop,
`01` = Go). Confirmed against the original 2016 project's own decoder —
see
[`CAN2LAN.cpp:562-567`](reference/legacy-picans88-2016/PiCanS88/CAN2LAN.cpp#L562-L567).

## Reading raw traffic / MFX locomotive address discovery

The 2016 predecessor project had a `-v` verbose mode that decoded frames
into readable text (e.g. `Loc-ID: [00004007]`) to let you read off a
newly-registered MFX locomotive's address by watching the bus while
operating it from an MS2 — see
[`ifoedit.com/RaspiCS2En.html#RocrailConfig`](http://www.ifoedit.com/RaspiCS2En.html#RocrailConfig)
for the original walkthrough.

That decode step hasn't been ported to this rewrite yet. Today, `candump
can0` will show raw frames on the shared bus, but not decoded into
human-readable Loc-ID/function text — only S88 event frames are
encoded/decoded in
[`common/marklin_can.py`](../python/pitraincontroller/common/marklin_can.py);
"Lok Funktion" (command 0x06) and "Lok Discovery" (command 0x01) framing
were never carried over. Porting that decode table (byte layout is in
[`CAN2LAN.cpp:660-667`](reference/legacy-picans88-2016/PiCanS88/CAN2LAN.cpp#L660-L667)
for Lok Funktion) into a small monitor CLI is a reasonable next step if
this workflow is needed before real hardware exists to test the gateway
against.

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
