Project Brief: Model Train Controller — Host Software
Paste this into Claude Code as the opening prompt for this project.
What this is
I have a custom Raspberry Pi HAT (a PCB that plugs directly onto the Pi's 40-pin GPIO header) that bridges a Raspberry Pi to a Märklin model railway system. The hardware is finished and verified; I need host-side software on the Pi to talk to it. This brief describes the board so you have full context before we write any code.
The board connects to two buses:
Märklin CAN bus — carries track/locomotive/accessory control traffic, shared with the Gleisbox's power feed. Handled by an on-board CAN controller chip (MCP25625) over SPI.
S88 bus — a shift-register-based feedback bus that reports sensor/contact states from up to five chained S88 modules. There is no dedicated controller chip for this; the Pi bit-bangs the protocol directly over four GPIO pins.
The board also powers the Pi itself (through the GPIO header, not through the Pi's own USB power port), and has four status LEDs, three of which are meant to be driven by software.
Exact pin map (Raspberry Pi BCM GPIO numbering)
Function
GPIO
Header pin
Direction (from Pi's POV)
Notes
SPI0 MOSI → MCP25625
GPIO10
19
out
Standard SPI0
SPI0 MISO ← MCP25625
GPIO9
21
in
Standard SPI0
SPI0 SCLK → MCP25625
GPIO11
23
out
Standard SPI0
SPI0 CE0 → MCP25625
GPIO8
24
out
Chip select
MCP25625 IRQ
GPIO25
22
in
Active-low interrupt from the CAN controller
MCP25625 RESET
GPIO27
13
out
Active-low hardware reset
S88 CLOCK
GPIO22
15
out
Shifts the S88 chain
S88 LOAD
GPIO23
16
out
Latches sensor states into the shift registers
S88 RESET
GPIO24
18
out
Resets the S88 shift-register chain
S88 DATA
GPIO17
11
in
Serial data back from the chain (level-shifted 5V→~3V by an on-board resistor divider, safe for the Pi)
LED1 (blue) — CAN activity
GPIO5
29
out
Drive high/blink on CAN traffic
LED3 (orange) — S88 activity
GPIO12
32
out
Drive high/blink on S88 poll activity
LED4 (red) — heartbeat/fault
GPIO6
31
out
See behavior spec below
LED2 (green) — power present
—
—
n/a
Passive hardware indicator, not software controlled
CAN controller (IC1): MCP25625
This is a Microchip MCP2515-family CAN controller + transceiver combo, connected on SPI0 CE0, with IRQ on GPIO25 and RESET on GPIO27. Standard Linux has a mainline mcp251x driver that exposes this as a normal SocketCAN interface (can0) via a device tree overlay — that's almost certainly the right approach rather than writing a raw SPI driver from scratch. First implementation task: get a mcp251x-based device tree overlay loading correctly against this exact pin map (SPI0.0, IRQ = GPIO25) and confirm can0 comes up with ip link. Once that works, all CAN traffic is just standard SocketCAN (socket(PF_CAN, ...)) from userspace — no need to hand-roll register-level SPI framing.
The Märklin CAN protocol (locomotive control, accessory control, S88-over-CAN feedback in some configurations, etc.) is a separate, well-documented protocol layered on top of standard CAN frames — that's the next layer to implement once can0 is confirmed working.
S88 bus (bit-banged)
No controller chip — this is direct GPIO bit-banging of the classic S88 shift register protocol (each module is built around chained parallel-load shift registers, e.g. 74HC165-style):
Pulse RESET to clear the chain.
Pulse LOAD to latch all connected modules' current sensor states into their shift registers simultaneously.
Pulse CLOCK repeatedly, reading one bit off DATA after each pulse, to shift the latched states out one at a time, module by module.
Up to 5 modules can be chained; total bit count = 16 × number of modules chained (16 sensor inputs per module is the common S88 module size, but this should be confirmed against the actual S88 modules in use before hardcoding it).
Timing needs to follow the standard S88 bus timing spec (it's a slow, tolerant protocol — historically driven by a 6050/6051 style S88 decoder at low kHz clock rates). Please look up the canonical S88 timing/protocol spec rather than guessing, since getting the pulse widths/order wrong is a common source of flaky sensor reads.
LED behavior to implement
LED1 (GPIO5): blink or pulse on CAN bus activity (TX or RX).
LED3 (GPIO12): blink or pulse on each S88 poll cycle.
LED4 (GPIO6): heartbeat — steady on for the first ~60 seconds after the service starts (covers boot/init), then switch to a periodic heartbeat blink once the system is confirmed running normally. If a fault condition is detected (CAN controller not responding, S88 chain not returning valid data, etc.), switch to a distinct fault blink pattern instead of the heartbeat pattern. Exact patterns are flexible — the important part is: steady-during- boot, heartbeat-when-healthy, different-pattern-on-fault.
LED2 needs no software — it's wired directly across the board's 5V rail and lights whenever power is present, independent of the Pi.
Power context (for awareness, not a software task)
The Pi is powered entirely through this HAT's GPIO header (no separate Pi power supply is used or expected) via a protected 5V feed. Not directly relevant to the software, but worth knowing in case power-loss/brownout handling comes up — there's no separate "Pi about to lose power independently of the board" case to worry about, since both fail together.
Suggested first milestones
Device tree overlay + mcp251x bring-up → confirm can0 interface exists and can send/receive raw CAN frames (loop back or against a real Gleisbox).
S88 bit-bang driver: implement CLOCK/LOAD/RESET/DATA cycle, confirm you can read back a known sensor pattern from at least one connected S88 module.
LED control service: heartbeat/boot/fault states on GPIO6, activity blink on GPIO5 and GPIO12, tied into whatever event loop the CAN and S88 pieces end up using.
Märklin CAN protocol layer on top of the working can0 interface (locomotive control, accessory/turnout control, etc., per the Märklin CAN protocol spec).
Let's start with milestone 1.