# PiTrainController install guide

> No boards have been fabricated yet (the S88 daughterboard is still
> being finalized — see the project README). Every step below is
> written and internally tested where possible (protocol/logic unit
> tests — see each milestone doc), but the end-to-end install hasn't
> been run on a real Pi yet. Expect to find and fix real-hardware
> surprises together once boards exist; that's expected, not a sign
> something here is wrong.

## Prerequisites

- Raspberry Pi 3B+ with the PiTrainController HAT (PCB Design v4.0 or
  compatible — see [`docs/reference/hardware-manual-v4.md`](reference/hardware-manual-v4.md)
  for the full pinout/power design) attached.
- Raspberry Pi OS **Trixie** (Debian 13), 64-bit, **Desktop** edition
  (needed for Rocrail's GUI if you install it — see below).
- A monitor/SSH access to run commands below.
- The board is powered from the Gleisbox connection alone (J2) and feeds
  the Pi's 5V rail through the GPIO header via an ideal-diode circuit —
  **do not** also plug a USB/micro-USB power adapter into the Pi while
  it's seated on this board (hardware manual, Section 3.2).
- If this board sits at a physical end of the CAN bus, jumper J7 pins
  1–2 to enable the on-board 120Ω termination; leave it open/parked on
  2–3 if another node already terminates the bus.

## 1. Flash and boot Raspberry Pi OS Trixie

Use Raspberry Pi Imager to write **Raspberry Pi OS (64-bit)** — the
current Trixie-based release — to your SD card/SSD. In the Imager's
advanced options (gear icon / Ctrl+Shift+X), it's worth pre-configuring
hostname, SSH, and Wi-Fi if you're going headless for initial setup.

Boot the Pi and get a shell (SSH or console).

## 2. Update the system and install build tools

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y device-tree-compiler can-utils git python3-pip
```

- `device-tree-compiler` provides `dtc`, needed to compile the overlay.
- `can-utils` provides `candump`/`cansend`/`ip -details link` diagnostics.

## 3. Get this repository onto the Pi

```bash
git clone  https://github.com/nrietsch/PiTrainController.git ~/pitraincontroller
cd ~/pitraincontroller
chmod +x scripts/*
```

(Or copy the working tree over some other way — e.g. `scp` — if you're
developing off-Pi and don't want to push to a remote yet.)

## 4. Run the installer

```bash
sudo scripts/install.sh
```

This sets up, in order:

1. The device tree overlay (compiles `overlays/pitraincontroller-mcp25625.dts`,
   installs it, and appends the needed `config.txt` lines — see
   `scripts/install_overlay.sh` if you'd rather do this step by hand).
2. The `pitraincontroller-can0.service` systemd unit (brings `can0` up
   at Marklin's 250 kbit/s on every boot).
3. The Python package and its dependencies (`python-can`, `lgpio`),
   installed editable so repo changes take effect without reinstalling.
4. The S88 driver and LED services (always installed — these are the
   board's core function).
5. Shows an LED reference screen, then **a checklist menu** (via
   `whiptail`, same tool `raspi-config` uses — falls back to plain
   yes/no prompts if it's unavailable) to choose which optional pieces
   to install:
   - The **CS2/CS3 LAN gateway** (lets Rocrail, the Marklin CS2 App, or
     other network clients control the layout through this Pi — see
     [`docs/CS2-GATEWAY.md`](CS2-GATEWAY.md)).
   - **Rocrail**, downloaded and extracted automatically (it's not an
     apt package — see [`docs/ROCRAIL.md`](ROCRAIL.md)), though a final
     manual step is needed from a real desktop session to finish setup;
     the installer tells you the exact command to run at the end.

Reboot for the overlay to take effect:

```bash
sudo reboot
```

## 5. Verify `can0` and start the services

```bash
scripts/verify_can0.sh
```

Expect a `dmesg` line like:

```
mcp251x spi0.0 can0: MCP25625 successfully initialized.
```

and `ip link show can0` reporting the interface exists.

Start everything (the installer already `enable`d these, so this also
happens automatically on future boots):

```bash
sudo systemctl start pitraincontroller-can0 pitraincontroller-s88 pitraincontroller-leds
sudo systemctl start pitraincontroller-gateway   # if you installed it
```

Check they're actually running and not crash-looping:

```bash
systemctl status pitraincontroller-can0 pitraincontroller-s88 pitraincontroller-leds pitraincontroller-gateway
journalctl -u pitraincontroller-s88 -u pitraincontroller-leds -u pitraincontroller-gateway -f
```

### Confirm real CAN traffic

With the Gleisbox connected and powered:

```bash
candump can0
```

You should see live CAN frames as you operate anything on an existing
controller, and S88 Event frames (command byte `0x11` in the CAN ID)
from `pitraincontroller-s88` as sensors change state.

### Confirm the LEDs


- **LED1 (blue, CAN)**: blinks on any `can0` traffic.
- **LED2 (green, )**: .
- **LED3 (orange, S88)**: blinks on every S88 poll cycle (roughly every
  50ms by default — should look close to steady-flickering when
  `pitraincontroller-s88` is healthy).
- **LED4 (red, heartbeat)**: steady on for the first minute after
  `pitraincontroller-leds` starts, then switches to a slow periodic
  blip. If it switches to a fast blink instead, that's the fault
  pattern — check `journalctl -u pitraincontroller-leds` for why
  (`can0` down, or no S88 activity seen recently).
  
### If you installed Rocrail or the gateway

See [`docs/ROCRAIL.md`](ROCRAIL.md) and [`docs/CS2-GATEWAY.md`](CS2-GATEWAY.md)
for configuration and verification specific to each.

## Troubleshooting

- **No `mcp251x`/`can0` lines in `dmesg` at all**: the overlay likely
  didn't load. Check `dmesg | grep -i 'fdt\|overlay'`, and double-check
  `/boot/firmware/config.txt` has both `dtparam=spi=on` and
  `dtoverlay=pitraincontroller-mcp25625` (not commented out, correctly
  spelled).
- **`can0` exists but `candump` shows nothing** even with the bus
  active: check wiring/termination (see J7 above), and confirm the
  bitrate is exactly `250000`.
- **`ip link show can0` reports `bus-off` or climbing error counters**:
  usually bus wiring/termination (double-check J7) or a bitrate
  mismatch. `ip -details -statistics link show can0` shows TX/RX error
  counters that help narrow this down.
- **Reset line concerns**: the overlay drives GPIO27 high (inactive) via
  a `gpio-hog` at boot, independent of the mcp251x driver (which only
  does an SPI soft-reset and has no GPIO reset support of its own). If
  the chip fails to initialize only on cold boot but recovers after a
  warm reboot, that's worth revisiting first.
- **S88 readings look wrong/garbled**: the S88 daughterboard hardware
  isn't finalized yet, and the driver's RESET/LOAD polarity assumptions
  are documented as unconfirmed in [`docs/S88.md`](S88.md) — that's the
  first thing to check once real modules exist. `PITC_S88_LOAD_ACTIVE_HIGH`
  / `PITC_S88_RESET_ACTIVE_HIGH` environment variables flip each without
  code changes.
- **A `pitraincontroller-*` service is crash-looping**:
  `journalctl -u <service-name> -n 50` for the actual traceback; the
  most likely early culprits are `lgpio` not having permission to open
  `/dev/gpiochip0` (services run as root by default specifically to
  avoid this) or `can0` not existing yet (services `Requires=`/`After=`
  `pitraincontroller-can0.service`, but if that unit itself failed,
  everything downstream will too — check it first).
