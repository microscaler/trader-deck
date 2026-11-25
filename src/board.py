"""Board definition: pads, holes, cutouts, nets. All coordinates top view, y up, mm."""
from shapely.geometry import Point, box, Polygon
from shapely import affinity
import geom as G

pads = []      # dict(ref, pin, net, layer 'F'|'B'|'*', kind, cx, cy, w, h, drill, slot)
npth = []      # (x, y, dia)
cutouts = []   # shapely polygons milled out of the board
silk = {"F": [], "B": []}   # ('line', x1,y1,x2,y2) / ('text', x, y, h, str, mirror)
parts = []     # (ref, value, footprint, x, y, side)


def pad(ref, pin, net, layer, kind, cx, cy, w, h=None, drill=None, slot=None):
    pads.append(dict(ref=ref, pin=pin, net=net, layer=layer, kind=kind, cx=cx, cy=cy,
                     w=w, h=h if h is not None else w, drill=drill, slot=slot))


def pad_poly(p):
    if p["kind"] == "rect":
        return box(p["cx"] - p["w"] / 2, p["cy"] - p["h"] / 2, p["cx"] + p["w"] / 2, p["cy"] + p["h"] / 2)
    if p["kind"] == "circle":
        return Point(p["cx"], p["cy"]).buffer(p["w"] / 2, 24)
    if p["kind"] == "oval":
        w, h = p["w"], p["h"]
        r = min(w, h) / 2
        from shapely.geometry import LineString
        if w >= h:
            ls = LineString([(p["cx"] - w / 2 + r, p["cy"]), (p["cx"] + w / 2 - r, p["cy"])])
        else:
            ls = LineString([(p["cx"], p["cy"] - h / 2 + r), (p["cx"], p["cy"] + h / 2 - r)])
        return ls.buffer(r, 24)
    raise ValueError(p["kind"])


def rrect(cx, cy, w, h, r):
    return box(cx - w / 2 + r, cy - h / 2 + r, cx + w / 2 - r, cy + h / 2 - r).buffer(r, 16)


LED_ORDER = []   # (ref, x, y) in chain order


def led(ref, x, y, din, dout):
    """SK6812MINI-E reverse mount on the bottom, shining up through a milled window."""
    cutouts.append(rrect(x, y, 3.6, 3.1, 0.5))
    pad(ref, "1", "5V", "B", "rect", x + 2.85, y - 0.7, 1.6, 0.825)      # VDD
    pad(ref, "2", dout, "B", "rect", x + 2.85, y + 0.7, 1.6, 0.825)      # DOUT
    pad(ref, "3", "GND", "B", "rect", x - 2.85, y + 0.7, 1.6, 0.825)     # VSS
    pad(ref, "4", din, "B", "rect", x - 2.85, y - 0.7, 1.6, 0.825)       # DIN
    parts.append((ref, "SK6812MINI-E", "reverse-mount RGB LED", x, y, "B"))
    # pin-1 (VDD) marker on bottom silk
    silk["B"].append(("line", x + 4.0, y - 1.5, x + 4.6, y - 1.5))
    silk["B"].append(("line", x + 4.6, y - 1.5, x + 4.6, y - 0.9))


def diode_v(ref, x, y, anode_net, cathode_net):
    """SOD-123 on the bottom, vertical, cathode at +y."""
    pad(ref, "A", anode_net, "B", "rect", x, y - 1.65, 1.2, 0.9)
    pad(ref, "K", cathode_net, "B", "rect", x, y + 1.65, 1.2, 0.9)
    parts.append((ref, "1N4148W", "SOD-123", x, y, "B"))
    for sx in (-0.85, 0.85):
        silk["B"].append(("line", x + sx, y - 0.9, x + sx, y + 0.9))
    silk["B"].append(("line", x - 0.85, y + 0.75, x + 0.85, y + 0.75))   # cathode bar


def diode_h(ref, x, y, anode_net, cathode_net):
    """SOD-123 on the bottom, horizontal, cathode at +x."""
    pad(ref, "A", anode_net, "B", "rect", x - 1.65, y, 0.9, 1.2)
    pad(ref, "K", cathode_net, "B", "rect", x + 1.65, y, 0.9, 1.2)
    parts.append((ref, "1N4148W", "SOD-123", x, y, "B"))
    for sy in (-0.85, 0.85):
        silk["B"].append(("line", x - 0.9, y + sy, x + 0.9, y + sy))
    silk["B"].append(("line", x + 0.75, y - 0.85, x + 0.75, y + 0.85))


def cap(ref, x, y, vertical, n1, n2):
    if vertical:
        pad(ref, "1", n1, "B", "rect", x, y + 0.95, 1.3, 1.0)
        pad(ref, "2", n2, "B", "rect", x, y - 0.95, 1.3, 1.0)
    else:
        pad(ref, "1", n1, "B", "rect", x - 0.95, y, 1.0, 1.3)
        pad(ref, "2", n2, "B", "rect", x + 0.95, y, 1.0, 1.3)
    parts.append((ref, "10uF 10V X5R", "0805", x, y, "B"))


def switch(idx, name, r, c, x, y, din, dout):
    ref = f"SW{idx + 1}"
    npth.extend([(x, y, 4.0), (x - 5.08, y, 1.75), (x + 5.08, y, 1.75),
                 (x - 3.81, y + 2.54, 3.05), (x + 2.54, y + 5.08, 3.05)])
    a = f"N_SW{idx + 1}"
    pad(ref, "1", a, "B", "rect", x - 7.085, y + 2.54, 2.55, 2.5)
    pad(ref, "2", f"COL{c}", "B", "rect", x + 5.842, y + 5.08, 2.55, 2.5)
    parts.append((ref, f"MX hot-swap socket ({name})", "Kailh CPG151101S11", x, y, "B"))
    diode_v(f"D{idx + 1}", x - 7.6, y + 6.9, a, f"ROW{r}")
    led(f"LED{idx + 1}", x, y - 4.7, din, dout)
    # top silk: 14 mm switch outline corners and the key name
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = x + sx * 7.0, y + sy * 7.0
            silk["F"].append(("line", cx, cy, cx - sx * 2.0, cy))
            silk["F"].append(("line", cx, cy, cx, cy - sy * 2.0))
    silk["F"].append(("text", x, y - 8.4, 1.1, name, False))
    silk["B"].append(("text", x + 1.0, y + 8.6, 0.9, f"{ref} R{r}C{c}", True))


def build():
    # ---- LED chain order: ring, then serpentine through the keys
    chain = [("LEDR1", G.ENC[0], G.ENC[1] + G.RING_R), ("LEDR2", G.ENC[0], G.ENC[1] - G.RING_R)]
    keyinfo = []
    for i, (name, r, c) in enumerate(G.KEYS):
        x, y = G.key_xy(name, r, c)
        keyinfo.append((i, name, r, c, x, y))
    byrow = {r: [k for k in keyinfo if k[2] == r] for r in range(4)}
    serp = sorted(byrow[0], key=lambda k: -k[4]) + sorted(byrow[1], key=lambda k: k[4]) + \
        sorted(byrow[2], key=lambda k: -k[4]) + sorted(byrow[3], key=lambda k: k[4])
    order = {k[0]: n + 2 for n, k in enumerate(serp)}       # chain position of each key LED
    nled = 2 + len(serp)

    def dnet(pos):
        return f"LD{pos}" if pos < nled else None

    led("LEDR1", chain[0][1], chain[0][2], dnet(0), dnet(1))
    led("LEDR2", chain[1][1], chain[1][2], dnet(1), dnet(2))
    LED_ORDER.extend(["LEDR1", "LEDR2"] + [f"LED{k[0] + 1}" for k in serp])
    for (i, name, r, c, x, y) in keyinfo:
        p = order[i]
        switch(i, name, r, c, x, y, dnet(p), dnet(p + 1))

    # ---- encoder EC11 with push switch (matrix position R3 C2)
    ex, ey = G.ENC
    pad("ENC1", "A", "ENC_A", "*", "circle", ex - 7.5, ey + 2.5, 2.0, drill=1.0)
    pad("ENC1", "C", "GND", "*", "circle", ex - 7.5, ey, 2.0, drill=1.0)
    pad("ENC1", "B", "ENC_B", "*", "circle", ex - 7.5, ey - 2.5, 2.0, drill=1.0)
    pad("ENC1", "S1", "COL2", "*", "circle", ex + 7.0, ey - 2.5, 2.0, drill=1.0)
    pad("ENC1", "S2", "N_ENCSW", "*", "circle", ex + 7.0, ey + 2.5, 2.0, drill=1.0)
    for sy in (-5.6, 5.6):
        pad("ENC1", "MP", None, "*", "rect", ex, ey + sy, 3.8, 2.5, slot=(2.8, 1.5))
    parts.append(("ENC1", "EC11E push encoder, 20 mm D-shaft", "Alps EC11E", ex, ey, "F"))
    diode_h("D16", 40.2, 62.0, "N_ENCSW", "ROW3")
    for (x1, y1, x2, y2) in [(-6, -6, 6, -6), (6, -6, 6, 6), (6, 6, -6, 6), (-6, 6, -6, -6)]:
        silk["F"].append(("line", ex + x1, ey + y1 * 0.72, ex + x2, ey + y2 * 0.72))

    # ---- RP2040-Zero on the bottom side, USB toward +y. Top view is the mirror of the module's top view.
    mx, my = G.MCU
    right = ["GP0", "GP1", "GP2", "GP3", "GP4", "GP5", "GP6", "GP7", "GP8"]          # module right column, USB end first
    left = ["5V", "GND", "3V3", "GP29", "GP28", "GP27", "GP26", "GP15", "GP14"]     # module left column, USB end first
    bottom = ["GP9", "GP10", "GP11", "GP12", "GP13"]                                # module x = +5.08 .. -5.08
    assign = {
        "5V": "5V", "GND": "GND", "3V3": "3V3",
        "GP0": "OLED_RES", "GP1": "OLED_CS", "GP2": "OLED_SCK", "GP3": "OLED_MOSI", "GP4": "OLED_DC",
        "GP5": "COL0", "GP6": "COL1", "GP7": "ROW0", "GP8": "ROW1",
        "GP9": "ROW2", "GP10": "ROW3", "GP11": "COL2", "GP12": "COL3",
        "GP28": "LD0", "GP27": "ENC_A", "GP26": "ENC_B",
    }
    pinmap = {}
    for n, name in enumerate(right):      # mirrored: appears on the LEFT in top view
        x, y = mx - 7.62, my + 10.16 - 2.54 * n
        pad("U1", name, assign.get(name), "*", "oval", x, y, 2.4, 1.6, drill=1.0)
        pinmap[name] = (x, y)
        silk["B"].append(("text", x - 3.2, y - 0.45, 0.9, name.replace("GP", ""), True))
    for n, name in enumerate(left):       # appears on the RIGHT in top view
        x, y = mx + 7.62, my + 10.16 - 2.54 * n
        pad("U1", name, assign.get(name), "*", "oval", x, y, 2.4, 1.6, drill=1.0)
        pinmap[name] = (x, y)
        silk["B"].append(("text", x + 3.4, y - 0.45, 0.9, name.replace("GP", ""), True))
    for n, name in enumerate(bottom):
        x, y = mx - 5.08 + 2.54 * n, my - 10.16
        pad("U1", name, assign.get(name), "*", "oval", x, y, 1.6, 2.4, drill=1.0)
        pinmap[name] = (x, y)
    parts.append(("U1", "Waveshare RP2040-Zero (castellated, soldered flat on the bottom)", "RP2040-Zero", mx, my, "B"))
    for (x1, y1, x2, y2) in [(-9, -11.75, 9, -11.75), (9, -11.75, 9, 11.75), (-9, 11.75, -9, -11.75)]:
        silk["B"].append(("line", mx + x1, my + y1, mx + x2, my + y2))
    silk["B"].append(("text", mx, my - 3.0, 1.2, "RP2040-ZERO", True))
    silk["B"].append(("text", mx, my - 5.2, 1.0, "USB THIS END ^", True))

    # ---- display wire header (2.08in SH1122 SPI module is mounted in the deck and wired here)
    hx, hy = G.OLED_HDR
    for n, (lab, net) in enumerate([("GND", "GND"), ("VCC", "3V3"), ("SCL", "OLED_SCK"), ("SDA", "OLED_MOSI"),
                                    ("RES", "OLED_RES"), ("DC", "OLED_DC"), ("CS", "OLED_CS")]):
        y = hy + (3 - n) * 2.54
        pad("J1", lab, net, "*", "rect" if n == 0 else "circle", hx, y, 1.7, drill=1.0)
        silk["F"].append(("text", hx + 3.3, y - 0.45, 0.9, lab, False))
    parts.append(("J1", "1x7 2.54 mm header or wires to OLED", "PinHeader 1x07", hx, hy, "F"))
    silk["F"].append(("text", hx + 9.5, hy + 10.2, 1.0, "OLED SH1122 SPI", False))

    # ---- bulk capacitors on the LED supply
    cap("C1", 15.5, 67.6, False, "GND", "5V")
    cap("C2", -41.3, -27.5, True, "5V", "GND")

    # ---- mounting posts pass through the board
    for (x, y) in G.POSTS_PLATE_SCREW + G.POSTS_PLATE_SUPPORT + G.POSTS_DECK:
        npth.append((x, y, G.POST_HOLE))

    silk["F"].append(("text", 0, 44.0, 1.6, "PRICEWHISPERER DECK", False))
    silk["F"].append(("text", 0, 41.6, 1.0, "REV A  -  MX HOT-SWAP 4X4  -  RP2040-ZERO UNDERNEATH", False))
    return pinmap, assign


def outline():
    return rrect((G.PCB_X0 + G.PCB_X1) / 2, (G.PCB_Y0 + G.PCB_Y1) / 2,
                 G.PCB_X1 - G.PCB_X0, G.PCB_Y1 - G.PCB_Y0, G.PCB_R)


def keepouts():
    """Regions with no bottom copper and no vias: under the module body (it has bare pads underneath)."""
    mx, my = G.MCU
    return box(mx - 5.7, my - 8.3, mx + 5.7, G.PCB_Y1)
