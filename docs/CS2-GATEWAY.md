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

That decode step is now ported: run

```bash
python3 -m pitraincontroller.gateway.monitor -i can0
```

on the Pi and it prints the same style of two-line decode for every
frame seen on `can0` (shared SocketCAN interface, so this runs fine
alongside the gateway service and/or Rocrail). To read off a new MFX
loco's address: connect an MS2, put a "new" MFX loco on the track, press
STOP then again to search/register it, then work a function key (e.g.
headlights) on the MS2 for that loco while the monitor is running —
watch for a `Command: Lok Funktion` line, whose `Loc-ID` field is the
new address, hex, per the walkthrough linked above (e.g. `Loc-ID:
[00004007]` = address `0x4007` → MFX range starts at `0x4000`, so
address **7**; enter that decimal value in Rocrail).

Implementation: pure decode logic in
[`common/marklin_decode.py`](../python/pitraincontroller/common/marklin_decode.py)
(no I/O, so it's directly testable), CLI wrapper in
[`gateway/monitor.py`](../python/pitraincontroller/gateway/monitor.py).
Ported from the byte layout in
[`CAN2LAN.cpp:528-754`](reference/legacy-picans88-2016/PiCanS88/CAN2LAN.cpp#L528-L754)
(covers System command, Lok Discovery/Bind/Verify, Lok
Geschwindigkeit/Richtung/Funktion, CV read/write, accessory switching,
S88 polling/event, ping, status config, and automatic-route commands).
Not a systemd service — it's a manual diagnostic tool, run it
interactively when you need it.

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
