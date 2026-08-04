# PiTrainController — Modern Märklin CS2/CS3 Bridge for Raspberry Pi

A ground-up rewrite of a Raspberry Pi HAT's host software: bridges a
Raspberry Pi 3B+ to a Märklin model railway (CAN bus for track/loco/
accessory control, S88 bus for sensor feedback), and exposes it as a
CS2/CS3-compatible network device so tools like Rocrail, the Märklin CS2
App, or mobile control apps can drive the layout through it — while
Rocrail can also run locally on the same Pi at the same time.

This replaces an [older 2016-era project](http://www.ifoedit.com/RaspiCS2SoftEn.html)
(archived for reference at [`docs/reference/legacy-picans88-2016/`](docs/reference/legacy-picans88-2016/))
built against a discontinued OS (Raspbian) and a raw-register GPIO/SPI
library. The hardware is a new board (PCB Design v4.0); this is new
software from scratch, informed by the old code's behavior but not
derived from it.

## Hardware

- Raspberry Pi 3B+ + a custom HAT (PCB Design v4.0) with an on-board
  **MCP25625** CAN controller/transceiver (SPI0), four GPIO pins for a
  bit-banged S88 feedback bus, and its own power path off the Gleisbox
  connection (bridge rectifier + buck regulator + ideal-diode feed to
  the Pi — no separate Pi power supply needed or supported).
- Full pinout, connector reference, and power design:
  [`docs/reference/hardware-manual-v4.md`](docs/reference/hardware-manual-v4.md)
  (current canonical hardware doc) and
  [`docs/reference/project-brief.md`](docs/reference/project-brief.md)
  (original planning brief — GPIO pin map agrees with the manual).
- The S88 module/daughterboard hardware (classic 74HC165 shift registers,
  routed via RJ45/CAT5 for cabling convenience) is still under active
  development and not yet finalized or fabricated.

## Design

- **OS**: Raspberry Pi OS Trixie (Debian 13), 64-bit, Desktop edition.
- **CAN**: mainline `mcp251x` SocketCAN driver via a custom device tree
  overlay (`overlays/pitraincontroller-mcp25625.dts`) — `can0` is a
  normal kernel network interface any number of processes can share
  (this is how the CS2/CS3 gateway and a locally-running Rocrail both
  work at once, without arbitration).
- **S88**: Python service bit-banging the RESET/LOAD/CLOCK/DATA GPIOs,
  publishing sensor changes as S88-over-CAN feedback frames onto `can0`.
- **CS2/CS3 emulation**: Python gateway relaying `can0` ↔ UDP broadcast
  15731 per the official Märklin CAN protocol spec.
- **LEDs**: Python service implementing the manual's boot/heartbeat/fault
  and activity-blink behavior.

Full architecture and milestone breakdown: see the project plan (or ask —
it's summarized in each milestone's docs as it lands).

## Status

| Milestone | What | Status |
|---|---|---|
| M1 | Device tree overlay + `can0` bring-up | Written — needs verification once boards exist |
| M2 | S88 bit-bang driver | Written, core logic unit-tested — polarity assumptions flagged in [`docs/S88.md`](docs/S88.md) |
| M3 | LED status service | Written, state machine unit-tested |
| M4 | CAN/CS2-CS3 UDP gateway | Written, framing/dedup logic unit-tested — known gaps in [`docs/CS2-GATEWAY.md`](docs/CS2-GATEWAY.md) |
| M5 | Rocrail integration docs | Written — see [`docs/ROCRAIL.md`](docs/ROCRAIL.md) |
| M6 | systemd units + installer + full install guide | Written — `scripts/install.sh` |

All six milestones have code and docs in the repo. No boards have been
fabricated yet (still finalizing the S88 module design), so **none of
this has run end-to-end on real hardware** — what's been verified so
far is: device tree overlay syntax by careful manual review (no `dtc`
available off-Pi), and every piece of pure logic (S88 scan/diff, LED
state machine, Marklin CAN frame encoding, CS2 LAN wire framing, echo
dedup) by unit test with fake/mocked I/O. GPIO timing, real CAN bus
behavior, and the S88 daughterboard's actual signal polarity all still
need real hardware to confirm.

## Getting started

See [`docs/INSTALL.md`](docs/INSTALL.md) for the full install guide, or
just run `sudo scripts/install.sh` on the Pi once boards exist.

## Repository layout

```
overlays/     device tree overlay source
config/       config.txt snippets
systemd/      systemd unit files
scripts/      install/verification shell scripts
python/       the Python services (S88 driver, LED service, CS2/CS3 gateway)
docs/         install guide + reference material (brief, hardware manual, legacy code)
```
