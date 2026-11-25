# PriceWhisperer Deck, rev A: case and board files

![PriceWhisperer Deck 3D concept, turning](docs/concept-turntable.gif)

## 3D concept
The original concept is in [`concept/index.html`](concept/index.html). Open it in a browser to rotate it, tap keys, arm live orders and flip the FLATTEN guard. It loads three.js from a CDN, so it needs a network connection.

![Concept still: long position, live orders armed](docs/concept.png)

The concept is the design intent, not the built geometry. The case and board below differ from it in the ways listed under "What changed from the 3D concept".

![Printable case, assembled](docs/case-preview.png)

![Board copper, top and bottom](pcb_preview.png)

Generated 2026-11-25. Nothing here has been printed, fabricated or powered. Treat it as a first prototype.

## What changed from the 3D concept
- Bottom row (ARM, CANCEL, FLATTEN) sits 6 mm below the other rows. The gap carries the guard hinge.
- FLATTEN is a 2u key shifted 2 mm right so the guard clears CANCEL.
- The display and dial sit on a raised deck, 5.5 mm above the switch plate.
- Outside size 94.4 x 122.4 mm, 20.6 mm tall at the deck, flat-bottomed. The optional rear riser tilts it about 4 degrees.

## Printed parts (already in print orientation)
| File | Size mm | Volume cm3 |
|---|---|---|
| pw-deck-bottom_shell.stl | 94.4 x 122.4 x 20.6 | 44.7 |
| pw-deck-switch_plate.stl | 89.1 x 86.0 x 25.7 | 7.8 |
| pw-deck-deck.stl | 89.1 x 32.2 x 10.2 | 5.0 |
| pw-deck-flatten_guard.stl | 40.7 x 25.9 x 25.5 | 4.4 |
| pw-deck-dial_disc.stl | 23.0 x 23.0 x 3.0 | 1.0 |
| pw-deck-dial_knob.stl | 15.0 x 15.0 x 14.0 | 2.1 |
| pw-deck-rear_riser_optional.stl | 80.0 x 14.0 x 8.0 | 8.4 |

- 0.4 mm nozzle, 0.2 mm layers. Only the bottom shell's USB opening bridges; no supports needed.
- Print dial_disc in clear or natural filament; it is the light ring under the knob.
- Guard hinge pin: a 42 mm length of 1.75 mm filament through the 2.1 mm holes.
- Screws: 8 x M2 x 8 self-tapping (5 through the plate, 3 through the deck) into 1.7 mm pilot holes.
- The switch plate is 1.5 mm with 14.1 mm cutouts. If switches are loose or tight, scale the cutouts, not the plate.
- Stack: floor 2.0, 6.5 gap, PCB 1.6, plate top 5.0 above the PCB, deck top 10.5 above the PCB.

## Board
- 2 layers, 88.6 x 116.6 mm, 1.6 mm. Track 0.30 mm (supply up to 0.60), clearance 0.20, vias 0.6/0.3 tented.
- Gerber X2 layers plus two Excellon files (PTH has two G85 slots for the encoder lugs; tell the fab if they ask).
- 17 LED windows and the outline are on Edge_Cuts.
- Everything except the encoder and wire header solders to the BOTTOM: hot-swap sockets, diodes, LEDs, 2 capacitors, controller.
- RP2040-Zero is soldered flat on the bottom, component side facing down, USB at the back edge. Put Kapton tape under it: the module has bare pads on its underside.
- Flash the module (or hold BOOT) before closing the case; its buttons face the floor.

### Controller pins
| RP2040-Zero pin | Net |
|---|---|
| GP0 | OLED_RES |
| GP1 | OLED_CS |
| GP2 | OLED_SCK |
| GP3 | OLED_MOSI |
| GP4 | OLED_DC |
| GP5 | COL0 |
| GP6 | COL1 |
| GP7 | ROW0 |
| GP8 | ROW1 |
| GP9 | ROW2 |
| GP10 | ROW3 |
| GP11 | COL2 |
| GP12 | COL3 |
| GP26 | ENC_B |
| GP27 | ENC_A |
| GP28 | LD0 |

GP13, GP14, GP15 and GP29 are free.

### Matrix (diodes: column to row, COL2ROW in QMK)
| | C0 | C1 | C2 | C3 |
|---|---|---|---|---|
| R0 | BUY MKT | BUY ASK | SELL BID | SELL MKT |
| R1 | HALF | DOUBLE | STOP BE | TRAIL |
| R2 | TICK- | TICK+ | TF- | TF+ |
| R3 | ARM | CANCEL | dial push | FLATTEN |

### LED chain (SK6812MINI-E, data from GP28)
LEDR1 > LEDR2 > LED4 > LED3 > LED2 > LED1 > LED5 > LED6 > LED7 > LED8 > LED12 > LED11 > LED10 > LED9 > LED13 > LED14 > LED15

LEDR1/LEDR2 are the dial ring. LED n sits under SW n.

### Display
2.08 in 256x64 SH1122 SPI module (70.5 x 22.5 mm board). It sticks to the underside of the deck and is wired to J1 (GND, VCC 3V3, SCL, SDA, RES, DC, CS, labelled on the board).

## Checks that were run
- Board: every net connected, no copper closer than 0.20 mm to another net, hole and edge clearances, all Gerbers parsed by a second library.
- Case: every part watertight; no overlap between shell, PCB, plate, deck, dial parts and guard, with the guard swept from closed to open.

## Check before you spend money
1. Display: the deck window assumes the glass is centred vertically on the module and sits 1 mm from the module's right-hand end. Measure yours; only the deck needs reprinting if it differs.
2. SK6812MINI-E pin order (1 VDD, 2 DOUT, 3 GND, 4 DIN) is taken from the open-source kbd footprint. Confirm against your LED's datasheet.
3. Stabiliser cutouts for FLATTEN use the common Cherry plate-mount dimensions from memory. Test-fit on a scrap print.
4. LEDs run from USB 5 V with 3.3 V data, which usually works but is outside the SK6812 spec. Cap brightness in firmware: 17 LEDs at full white exceeds 500 mA.
5. There is no schematic or KiCad project behind these Gerbers. The board was placed and routed by script, so run it through your fab's DFM viewer before ordering.
6. The guard clears keycaps up to about 20 mm above the plate (Cherry, OEM, DSA). SA profile is too tall.
