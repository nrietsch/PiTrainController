# PiTrainController — Modern Märklin CS2/CS3 Bridge for Raspberry Pi

A ground-up rewrite of a Raspberry Pi HAT's host software: bridges a
Raspberry Pi 3B+ to a Märklin model railway (CAN bus for track/loco/
accessory control, S88 bus for sensor feedback), and exposes it as a
CS2/CS3-compatible network device so tools like
[Rocrail](https://www.rocrail-wiki.net/doku.php?id=start),
[TrainControl](https://github.com/bob123456678/TrainControl), the Märklin
CS2 App, or mobile control apps can drive the layout through it — while
Rocrail can also run locally on the same Pi at the same time.

This replaces an [older 2016-era project](http://www.ifoedit.com/RaspiCS2SoftEn.html)
(archived for reference at [`docs/reference/legacy-picans88-2016/`](docs/reference/legacy-picans88-2016/))
built against a discontinued OS (Raspbian) and a raw-register GPIO/SPI
library. The hardware is a new board (currently PCB Design v4.3); this is
new software from scratch, informed by the old code's behavior but not
derived from it.

[![Support PiTrainController on Buy Me a Coffee](docs/assets/buy-me-a-coffee.svg)](https://buymeacoffee.com/traincontroller)

## Hardware

- Raspberry Pi 3B+ + a custom HAT (PCB Design v4.3) with an on-board
  **MCP25625** CAN controller/transceiver (SPI0), four GPIO pins for a
  bit-banged S88 feedback bus, and its own power path off the Gleisbox
  connection (no separate Pi power supply needed or supported).
- Boards aren't on sale yet: v4.3 is still being tested.
- **S88 feedback works with commercial modules**: plug one into the
  6-pin S88 header with a standard ribbon cable, or into the RJ45 jack
  with an s88-N cable. No daughterboard is needed.
- Pinout and connector reference:
  [`docs/reference/hardware-manual-v4.md`](docs/reference/hardware-manual-v4.md)
  and
  [`docs/reference/project-brief.md`](docs/reference/project-brief.md)
  (original planning brief — GPIO pin map agrees with the manual).
- A home-built S88 daughterboard (classic 74HC165 shift registers, routed
  via RJ45/CAT5 for cabling convenience) is still under development and
  not yet fabricated. It's optional.

## Design

- **OS**: Raspberry Pi OS Trixie (Debian 13), 64-bit, Desktop edition.
- **CAN**: mainline `mcp251x` SocketCAN driver via a custom device tree
  overlay (`overlays/pitraincontroller-mcp25625.dts`) — `can0` is a
  normal kernel network interface any number of processes can share
  (this is how the CS2/CS3 gateway and a locally-running Rocrail both
  work at once, without arbitration).
- **S88**: Python service bit-banging the RESET/LOAD/CLOCK/DATA GPIOs,
  publishing sensor changes as S88-over-CAN feedback frames onto `can0`.
- **CS2/CS3 emulation**: Python gateway relaying `can0` ↔ UDP, receiving
  from clients on port 15731 and broadcasting CAN traffic to them on
  15730, like a real CS2/CS3.
- **LEDs**: Python service implementing the manual's boot/heartbeat/fault
  and activity-blink behavior.

Full architecture and milestone breakdown: see the project plan (or ask —
it's summarized in each milestone's docs as it lands).

## Status

| Milestone | What | Status |
|---|---|---|
| M1 | Device tree overlay + `can0` bring-up | Verified on real hardware (a PCB v4.0 board with the VDDA fix, see below) |
| M2 | S88 bit-bang driver | Verified against a commercial S88 module (Viessmann-type, CD4014-based); events reach TrainControl and Rocrail — see [`docs/S88.md`](docs/S88.md) |
| M3 | LED status service | Written, state machine unit-tested |
| M4 | CAN/CS2 gateway + CS2-style web config server | Verified with TrainControl 3.0.6 in CS2 mode (connect, drive a loco, S88 contacts, locos and track diagram synced from the Rocrail plan) — see [`docs/CS2-GATEWAY.md`](docs/CS2-GATEWAY.md) |
| M5 | Rocrail integration docs | Rocrail sees S88 contacts; see [`docs/ROCRAIL.md`](docs/ROCRAIL.md) |
| M6 | systemd units + installer + full install guide | Written — `scripts/install.sh` |

All six milestones have code and docs in the repo, and a v4.0 board has
been built and brought up on real hardware. Things to know:

- **Tested on v4.0, designed for v4.3**: the results above come from a
  v4.0 board. The v4.3 layout uses the same Pi pins, so the software
  needs no changes, but it hasn't been run on a v4.3 board yet.
- **PCB v4.0 errata**: the MCP25625's transceiver supply pin (VDDA,
  pin 27) is wired to 3.3V but needs 5V, so v4.0 boards need pin 27
  moved to the 5V rail — see
  [`docs/reference/hardware-manual-v4.md`](docs/reference/hardware-manual-v4.md).
  v4.3 has this corrected.
- **A CS2, with an experimental CS3 mode**: the Pi answers as a CS2 (UDP
  15731/15730 plus a small HTTP config server on port 80). The CS3's JSON
  lists (locos, switches) are available behind `PITC_WEB_STATION=cs3`;
  TrainControl 3.0.6 detects the Pi as a CS3 and imports locomotives
  through them. There are no routes or icons, and other CS3 clients
  (including Märklin's own app) are untested. Locomotive/accessory lists start empty unless generated from a
  Rocrail plan; see [`docs/CS2-GATEWAY.md`](docs/CS2-GATEWAY.md).
- **Not yet verified**: the v4.3 board, the S88 daughterboard (still being designed), long-running stability, and
  CS2-compatible clients other than TrainControl and Rocrail.

## Getting started

See [`docs/INSTALL.md`](docs/INSTALL.md) for the full install guide, or
just run `sudo scripts/install.sh` on the Pi once boards exist.

## Running the tests

The pure-logic unit tests (`python/tests/`) run on any machine with
Python 3.11+ — no Pi, `lgpio`, or real CAN interface needed. Install
just `pytest` and `python-can` (skip the full editable install, since
`lgpio` is Pi/liblgpio-only and isn't needed to run these):

```bash
cd python
pip install pytest python-can
pytest
```

## Repository layout

```
overlays/     device tree overlay source
config/       config.txt snippets
systemd/      systemd unit files
scripts/      install/verification shell scripts
python/       the Python services (S88 driver, LED service, CS2/CS3 gateway)
docs/         install guide + reference material (brief, hardware manual, legacy code)
```

## Support PiTrainController

The PiTrainController software is free, with no ads or locked features. I develop it in my spare time, so if
you enjoy using it, please consider buying me a coffee.

[![Support PiTrainController on Buy Me a Coffee](docs/assets/buy-me-a-coffee.svg)](https://buymeacoffee.com/traincontroller)
