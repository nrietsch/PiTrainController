> Text-extracted from `Model_Train_Controller_Manual.docx` (source of truth
> is the original .docx/schematics — this is a plain-text copy for
> in-repo reference; tables have lost their grid formatting in the
> conversion but the pin/row order is preserved). This is the current
> canonical hardware reference, superseding `project-brief.md` for
> anything the two disagree on (they don't, for the Pi-facing GPIO pin
> map — both list identical pins). The S88 daughterboard/module (J8,
> RJ1, RJ2) is explicitly called out as still being revised separately.

# Model Train Controller
Raspberry Pi Controller Board — User Manual
Board revision: PCB Design v4.0
1. Overview
This board is a Raspberry Pi add-on (“HAT”) that bridges a Märklin Gleisbox to a Raspberry Pi, giving the Pi direct access to two separate model railway buses:
The Märklin CAN bus (track control, locomotive commands, accessory control), carried on the same cable as the Gleisbox's power feed.
The S88 feedback bus (occupancy/contact sensor reporting), read through up to five S88 modules chained off this board.
The board also supplies power to the Raspberry Pi itself, so a single Gleisbox connection is enough to run the whole system — no separate Pi power supply is needed (see Section 3).
2. How It Works
Power and the CAN bus both arrive on a single 4-pin connector from the Gleisbox (J2). A bridge rectifier and a 6A buck regulator (IC2) turn this into a clean 5V rail that runs the whole board. A CAN controller (IC1, MCP25625) talks to the Gleisbox's CAN bus over SPI, and its RESET/interrupt lines are wired directly to the Pi. The S88 bus is driven directly by the Pi's GPIO pins (bit-banged, no dedicated S88 controller chip on this board) and is broken out to a main connector (J5) and a duplicate debug/tap connector (J4) for probing the bus without disconnecting the live chain. Four status LEDs give a quick visual read of what the board is doing without needing a laptop attached.
3. Power Design
3.1 Power Path
Gleisbox (raw AC/DC + CAN, via J2) → BR1 bridge rectifier → IC2 (LM73606, 6A buck regulator) → VCC_5V_SYS (main 5V rail).
From VCC_5V_SYS, two things happen in parallel:
PS1 (LM1117-3.3 LDO) steps a portion down to 3.3V (VCC_3V3_LOCAL) to run the CAN controller (IC1) and its local logic.
IC3 (LM74610, an “ideal diode” controller) drives Q1 (a MOSFET) as a low-loss electronic diode between VCC_5V_SYS and a separate net called PI_5V, which feeds the Raspberry Pi's 5V pins directly through the GPIO header (pins 2 and 4).
3.2 No Direct Power for the Pi — Important
This board does not give the Raspberry Pi its own power jack, USB port, or any independent power input. The Pi is powered exclusively through its 40-pin GPIO header, fed from this board's regulator via the ideal-diode circuit described above.
This is a deliberate design choice: it means the whole system (Pi + controller board + S88 modules) runs from the single Gleisbox connection, with no second power supply to manage. The ideal-diode stage (IC3 + Q1) exists specifically to protect this shared 5V rail — it allows current to flow from the board to the Pi, but blocks it from flowing back the other way.
Do not plug the Raspberry Pi's own power adapter (USB-C or micro-USB) into the Pi while it is seated on this board. Powering the Pi from two sources at once bypasses the protection this board was designed around and can damage the regulator, the ideal-diode circuit, or the Pi itself. Power the whole assembly only through the Gleisbox connection (J2).
4. LED Indicators
Four LEDs on the board report status. Three are software-controlled by the Raspberry Pi; one is a passive hardware indicator that works even before the Pi has booted.
LED
Color
Driven By
Meaning
LED1
Blue
GPIO5 (physical pin 29)
CAN bus traffic indicator — software-controlled by the Pi.
LED2
Green
Passive (VCC_5V_SYS via R9, no GPIO)
Gleisbox / board power present. Lights whenever the 5V rail is healthy, independent of whether the Pi has booted.
LED3
Orange
GPIO12 (physical pin 32)
S88 bus traffic indicator — software-controlled by the Pi.
LED4
Red
GPIO6 (physical pin 31)
System heartbeat / fault indicator. Planned behavior: steady on during the ~1 minute startup/boot window, then a periodic blink once running; a fault blink pattern if a problem is detected.
5. Connector Pinouts
5.1 J1 — Raspberry Pi GPIO Header (40-pin)
Standard Raspberry Pi HAT header. All 8 ground pins and both 5V pins are used; pins not listed below carry Pi signals that this board does not use.
Pin
Signal
GPIO
Function on this board
1
3.3V
—
Pi's own 3.3V rail, brought out but not used elsewhere on this board.
2, 4
PI_5V
—
5V supply to the Pi from this board (see Section 3). Do not back-feed.
6, 9, 14, 20, 25, 30, 34, 39
GND
—
Ground.
11
S88 DATA (in)
GPIO17
S88 shift-register data input, level-shifted from 5V to ≈ 3V by a 10k/15k divider (R10/R11) before reaching the Pi.
13
CAN RESET
GPIO27
Drives IC1's (MCP25625) hardware reset line.
15
S88 CLOCK (out)
GPIO22
Clocks the S88 shift-register chain.
16
S88 LOAD (out)
GPIO23
Latches/loads the S88 shift-register chain.
18
S88 RESET (out)
GPIO24
Resets the S88 shift-register chain.
19
SPI MOSI
GPIO10
SPI data to IC1 (CAN controller).
21
SPI MISO
GPIO9
SPI data from IC1.
22
CAN INT
GPIO25
Interrupt line from IC1 (new CAN message / event).
23
SPI SCK
GPIO11
SPI clock to IC1.
24
SPI CS
GPIO8 (CE0)
SPI chip-select for IC1.
29
LED1 (CAN)
GPIO5
Drives LED1 through R3.
31
LED4 (Heartbeat)
GPIO6
Drives LED4 through R8.
32
LED3 (S88)
GPIO12
Drives LED3 through R7.
5.2 J2 — Gleisbox Input
4-pin connector carrying both raw power and the Märklin CAN bus from the Gleisbox on a single cable.
Pin
Signal
Notes
1
AC / DC in
Raw power feed from the Gleisbox, into the bridge rectifier (BR1).
2
CAN-H
Märklin CAN bus, high line — to IC1.
3
CAN-L
Märklin CAN bus, low line — to IC1 and the termination jumper (J7).
4
AC / DC return
Return leg of the raw power feed, into BR1.
5.3 J5 — S88 Bus (Main)
Main connection point for the S88 feedback module chain.
Pin
Signal
Notes
1
DATA
Shift-register data, returns to the Pi via GPIO17 (see J1, pin 11).
2
GND
Ground.
3
CLOCK
Driven by the Pi (GPIO22).
4
LOAD
Driven by the Pi (GPIO23).
5
RESET
Driven by the Pi (GPIO24).
6
VS88
S88 module supply rail.
5.4 J4 — S88 Bus (Debug / Tap)
Wired in parallel with J5 (identical DATA/GND/CLOCK/LOAD/RESET/VS88 signals). Intended as a probe or debug tap on the live S88 bus without needing to unplug the main chain. This is the connector position formerly labeled J3; the part was changed to a Samtec SSQ-106-03-G-S for mechanical clearance from the adjacent RJ45 jack (RJ1).
5.5 J7 — CAN Bus Termination Jumper
3-pin, 0.1" jumper header controlling whether this board provides 120Ω CAN bus termination.
Jumper Position
Effect
Shorting pins 1–2
Termination ON — connects a 120Ω resistor (R1) across CAN-H / CAN-L. Use this if this board is at a physical end of the CAN bus.
Cap parked on pins 2–3 (or removed)
Termination OFF — use if another node already terminates the bus, or if this board sits in the middle of the chain.
5.6 J8 / RJ1 / RJ2 — S88 Daughterboard Interconnect
These carry the S88 chain-forward signals (Data/Load/Clock/Reset/GND/VDD) to and from the separate S88 daughterboard assembly. That subsystem is being revised separately and is out of scope for this manual.
6. Bill of Materials
Reflects the current board revision, including the 3.3V decoupling capacitor (C16) added near IC2 and the J4 connector swap noted above.
Reference(s)
Part / Value
Qty
BR1
W04G-E4 (bridge rectifier)
1
C1, C2
22pF, 1206
2
C3, C4, C5
0.1µF, 1206
3
C6, C8
MAL214699104E3, 100µF/50V electrolytic
2
C7
EEE-TG1E221P, 220µF/25V polymer
1
C9
0.47µF, 1210 (IC2 CBOOT bootstrap cap)
1
C10, C12
F971E106MNC, 10µF/25V tantalum
2
C11
2.2µF, 1206
1
C13, C15
MSASE168SB5105KTNA01
2
C14
22nF, 0805
1
C16
10µF, 1210, X7R (IC2 PVIN bulk decoupling)
1
F1
MF-LSMF330/24X-2 (resettable fuse)
1
IC1
MCP25625-E/SS (CAN controller + transceiver)
1
IC2
LM73606RNPR (6A buck regulator)
1
IC3
LM74610QDGKRQ1 (ideal diode controller)
1
J1
1992 (Pi 2x20 GPIO header)
1
J2
Gleisbox input connector
1
J4
Samtec SSQ-106-03-G-S (S88 debug/tap header)
1
J5
S88 bus connector
1
J7
M20-9770346 (3-pin CAN term. jumper)
1
L1
XAL4030-472MEC, 4.7µH inductor
1
LED1
Blue — KB_EELP41.12-P1R2-36-3X4X-5-R18
1
LED2
Green — KT_EELP41.12-S2U1-25-2X4X-5-R18
1
LED3
Orange — VFHA1116P-4C82C-TR
1
LED4
Red — VFHR1116P-4C82A-TR
1
PS1
LM1117IMPX-3.3/NOPB (3.3V LDO)
1
Q1
IRLML6344TRPBF (MOSFET, ideal-diode switch)
1
R1, R3
120Ω, 1206
2
R2
4.7kΩ, 1206
1
R4
1.8kΩ
1
R5, R6
3.3Ω
2
R7
470Ω, 1206 (LED3)
1
R8, R9
220Ω, 1206 (LED4, LED2)
2
R10
10kΩ, 1206 (S88 DATA divider)
1
R11
15kΩ, 1206 (S88 DATA divider)
1
R12
10Ω, 0402
1
R13
100kΩ, 1206
1
R14
24.9kΩ
1
R15, R16
100kΩ
2
RJ1
RJE561881410 (shielded RJ45 jacks)
1
Y1
LFXTAL058383, crystal (IC1 oscillator)
1