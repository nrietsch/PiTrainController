# Running Rocrail alongside this gateway

Rocrail can run locally on the same Pi, at the same time as the
`pitraincontroller-gateway` and `pitraincontroller-s88` services, with no
conflict — SocketCAN lets any number of processes bind to `can0`
simultaneously, so Rocrail talking to `can0` directly and the gateway
relaying `can0` ↔ UDP for remote apps are independent consumers of the
same interface.

> This document hasn't been walked through end-to-end on real hardware
> yet (no boards fabricated so far — see the project README). Rocrail's
> own wiki (linked below) is the authoritative source if anything here
> turns out stale; treat this as a starting point, not gospel.

## Install

```bash
sudo apt update
sudo apt install -y rocrail
```

(Raspberry Pi OS Trixie Desktop is assumed per the project's OS choice —
Rocrail's GUI needs a display. If you ever run this headless instead,
Rocrail also supports a client/server split — `rocrail` the server plus
`roweb`/a remote `Rocview` client — but that's out of scope here.)

## Configure Rocrail to use `can0` directly

Rocrail has a native SocketCAN controller (its own docs and community
write-ups call this the **MBUS** controller/plugin), which binds
straight to a CAN network interface — no gateway hop needed for a local
Rocrail instance. Reference:
[Rocrail wiki: SocketCAN](https://www.rocrail.online/doku.php?id=cbus:socketcan-en).

In Rocrail's controller setup (`Properties → Interface`, or by hand in
`rocrail.ini`):

1. Choose the **MBUS** (or "CAN"/SocketCAN-labeled, depending on Rocrail
   version) controller type.
2. Point it at the `can0` device.
3. Leave bitrate configuration to this project's
   `pitraincontroller-can0.service` (already brings `can0` up at
   Marklin's 250 kbit/s) rather than having Rocrail also try to set it —
   confirm in Rocrail's interface settings that it's not attempting to
   re-configure the interface itself, which could race with the systemd
   unit at boot.

Once configured, Rocrail should see the same live CAN traffic as
`pitraincontroller-s88` (S88 feedback) and any real Gleisbox/CS2 traffic
on the bus, with no need to route through the UDP gateway locally.

## Alternative: point Rocrail at the UDP gateway instead

If you'd rather Rocrail (local or remote) talk over the network instead
of binding `can0` directly — e.g. testing the gateway itself, or running
Rocrail on a different machine — configure Rocrail's **CS2** controller
type (network/UDP, not MBUS) against this Pi's IP address, port 15731.
This exercises `pitraincontroller-gateway` instead of bypassing it.

Both a local Rocrail-via-`can0` and a remote Rocrail-via-gateway can be
active at the same time; they're just two more processes sharing the
same underlying CAN traffic through different paths.

## Verify

- With Rocrail running and connected (either mode), confirm it shows
  live sensor state changes when you trigger an S88 contact — this
  exercises the full path from `pitraincontroller-s88` (bit-bang read →
  CAN S88 Event frame) through to Rocrail's own occupancy display.
- Confirm operating a turnout/loco from Rocrail produces the expected
  traffic on `candump can0` and (if using the network mode) reaches the
  real Gleisbox.
- If both a local MBUS-mode Rocrail and the `pitraincontroller-gateway`
  service are running together, confirm neither logs unexpected
  errors/warnings and that traffic on `can0` looks the same as with
  either one running alone (i.e. confirm the "share the interface"
  assumption holds in practice, not just in theory).
