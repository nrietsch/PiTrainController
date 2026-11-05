# PiTrainController HAT: connectors and indicators

What you need to wire up and run the board. Connector names differ between
board revisions, so check yours. v4.3 is the current design. The software
has been tested on v4.0 and uses the same Pi pins on both.

| Connector | v4.3 | v4.0 |
|---|---|---|
| Gleisbox (power + CAN) | J4 | J2 |
| S88 main header | J6 | J5 |
| S88 tap header, in parallel with the main one | J5 | J4 |
| S88 RJ45 jack (s88-N) | RJ1 | RJ1 |
| CAN termination | always on | jumper J7 |

## Power

The board runs from the Gleisbox connection alone and powers the Pi through
its 40-pin GPIO header (pins 2 and 4).

**Do not plug the Pi's own power adapter into the Pi while it is on this
board.** Powering the Pi from two sources can damage the board or the Pi.

v4.0 boards need a fix before CAN will work: the MCP25625's VDDA (pin 27) is
wired to 3.3V and must be moved to 5V. v4.3 has this corrected.

## Status LEDs

| LED | Colour on v4.0 | Driven by | Meaning |
|---|---|---|---|
| CAN | Blue | GPIO5 | CAN bus traffic |
| Power | Green | 5V rail, no GPIO | Board power is present, even before the Pi boots |
| S88 | Orange | GPIO12 | S88 bus traffic |
| Heartbeat | Red | GPIO6 | Steady during startup, then a periodic blink, with a different blink for a fault |

## Pi header

Pins not listed here aren't used by the software.

| Pin | GPIO | Function |
|---|---|---|
| 2, 4 | | 5V supply to the Pi from the board |
| 6, 9, 14, 20, 25, 30, 34, 39 | | Ground |
| 11 | GPIO17 | S88 DATA in |
| 13 | GPIO27 | CAN controller reset |
| 15 | GPIO22 | S88 CLOCK out |
| 16 | GPIO23 | S88 LOAD out |
| 18 | GPIO24 | S88 RESET out |
| 19 | GPIO10 | SPI MOSI to the CAN controller |
| 21 | GPIO9 | SPI MISO from the CAN controller |
| 22 | GPIO25 | CAN interrupt |
| 23 | GPIO11 | SPI clock |
| 24 | GPIO8 (CE0) | SPI chip select |
| 29 | GPIO5 | CAN LED |
| 31 | GPIO6 | Heartbeat LED |
| 32 | GPIO12 | S88 LED |

## Gleisbox connector

| Pin | Signal |
|---|---|
| 1 | Power in |
| 2 | CAN-H |
| 3 | CAN-L |
| 4 | Power return (ground) |

## S88 main and tap headers

Up to five S88 modules can be chained.

| Pin | Signal | Notes |
|---|---|---|
| 1 | DATA | Back to the Pi on GPIO17 |
| 2 | GND | |
| 3 | CLOCK | From the Pi on GPIO22 |
| 4 | LOAD | From the Pi on GPIO23 |
| 5 | RESET | From the Pi on GPIO24 |
| 6 | VS88 | S88 module supply |

## S88 RJ45 jack (s88-N)

| Pin | Signal |
|---|---|
| 1 | VS88 |
| 2 | DATA |
| 3 | GND |
| 4 | CLOCK |
| 5 | GND |
| 6 | LOAD |
| 7 | RESET |
| 8 | Not connected |

## CAN termination

v4.3 always has 120Ω across CAN-H and CAN-L. On v4.0, jumper J7 pins 1-2 turns
it on, which is what you want at a physical end of the bus. Park the jumper on
pins 2-3 if another node already terminates the bus or the board sits mid-chain.
