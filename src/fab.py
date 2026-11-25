"""DRC, power-track widening, Gerber/Excellon output and previews for the Deck board."""
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in ("build", "gerber", "stl", "kicad", "docs"):
    _os.makedirs(_os.path.join(ROOT, _d), exist_ok=True)

import pickle, math, os, csv, itertools
import numpy as np
from shapely.geometry import Point, LineString, box
from shapely.strtree import STRtree
from shapely.ops import unary_union
import geom as G
import board as B
from HersheyFonts import HersheyFonts

OUTD = ROOT + "/gerber"
os.makedirs(OUTD, exist_ok=True)
TW, CLR, VIA_D, VIA_DRILL, HOLE_CLR, EDGE_CLR = 0.30, 0.20, 0.60, 0.30, 0.30, 0.45
pinmap, assign = B.build()
R = pickle.load(open(ROOT + "/build/routed.pkl", "rb"))
assert not R["failed"]
OUT = B.outline()
KEEP = B.keepouts()
holes = [Point(x, y).buffer(d / 2, 48) for (x, y, d) in B.npth] + list(B.cutouts)
holes_u = unary_union(holes)
LAY = {"F": [0], "B": [1], "*": [0, 1]}

# ---- segments
segs = []   # [net, layer, (x1,y1), (x2,y2), width]
for (net, l, pts) in R["tracks"]:
    for a, b in zip(pts[:-1], pts[1:]):
        segs.append([net, l, a, b, TW])


def feats(layer):
    """All copper on a layer as (net, geom, tag)."""
    out = []
    for k, p in enumerate(B.pads):
        if layer in LAY[p["layer"]]:
            out.append((p["net"] or f"__nc{k}", B.pad_poly(p), f"pad {p['ref']}.{p['pin']}"))
    for (net, x, y) in R["vias"]:
        out.append((net, Point(x, y).buffer(VIA_D / 2, 24), f"via {x:.2f},{y:.2f}"))
    for s in segs:
        if s[1] == layer:
            out.append((s[0], LineString([s[2], s[3]]).buffer(s[4] / 2, 12), f"trk {s[2]}-{s[3]}"))
    return out


# ---- widen the LED supply tracks where there is room
for target in (0.60, 0.45):
    for layer in (0, 1):
        fs = feats(layer)
        geoms = [f[1] for f in fs]
        tree = STRtree(geoms)
        for s in segs:
            if s[1] != layer or s[0] not in ("5V", "GND") or s[4] >= target:
                continue
            ls = LineString([s[2], s[3]])
            cand = ls.buffer(target / 2, 12)
            ok = OUT.buffer(-(EDGE_CLR)).contains(cand) and cand.distance(holes_u) >= HOLE_CLR + 0.02
            if ok and layer == 1 and cand.intersects(KEEP):
                ok = False
            if ok:
                for i in tree.query(cand.buffer(CLR + 0.03)):
                    if fs[i][0] != s[0] and geoms[i].distance(cand) < CLR + 0.02:
                        ok = False
                        break
            if ok:
                s[4] = target

# widening used a snapshot per pass; shrink back any widened pair that ended up too close
for _ in range(10):
    changed = False
    for layer in (0, 1):
        ss = [s for s in segs if s[1] == layer]
        gs = [LineString([s[2], s[3]]).buffer(s[4] / 2, 12) for s in ss]
        tree = STRtree(gs)
        for i, s in enumerate(ss):
            if s[4] <= TW:
                continue
            for j in tree.query(gs[i].buffer(CLR + 0.03)):
                if ss[j][0] != s[0] and gs[j].distance(gs[i]) < CLR + 0.01:
                    s[4] = TW
                    changed = True
                    break
    if not changed:
        break

# ---- DRC
errors = []
for layer in (0, 1):
    fs = feats(layer)
    geoms = [f[1] for f in fs]
    tree = STRtree(geoms)
    for i, (net, g, tag) in enumerate(fs):
        for j in tree.query(g.buffer(CLR)):
            if j <= i or fs[j][0] == net:
                continue
            d = g.distance(geoms[j])
            if d < CLR - 0.005:
                errors.append(f"L{layer} clearance {d:.3f} {tag} [{net}] vs {fs[j][2]} [{fs[j][0]}]")
        if not tag.startswith("pad") or True:
            d = g.distance(holes_u)
            # plated pads own their drills; only unplated holes and cutouts are in holes_u
            if d < (0.24 if tag.startswith('pad LED') else HOLE_CLR - 0.06):
                errors.append(f"L{layer} hole clearance {d:.3f} {tag}")
        if not OUT.buffer(-0.3).contains(g):
            errors.append(f"L{layer} edge clearance {tag}")
        if layer == 1 and tag.startswith(("trk", "via")) and g.intersects(KEEP):
            errors.append(f"keepout {tag}")
# via spacing
vp = [Point(x, y) for (_, x, y) in R["vias"]]
for a, b in itertools.combinations(range(len(vp)), 2):
    if vp[a].distance(vp[b]) < 0.8:
        errors.append(f"vias too close {R['vias'][a]} {R['vias'][b]}")
drills_pth = [(p["cx"], p["cy"], p["drill"]) for p in B.pads if p["drill"]]
for (_, x, y) in R["vias"]:
    for (hx, hy, hd) in drills_pth:
        if math.hypot(x - hx, y - hy) < hd / 2 + VIA_DRILL / 2 + 0.4:
            errors.append(f"via near drill {x},{y}")

# connectivity per net with union-find across layers
netfe = {}
for layer in (0, 1):
    for (net, g, tag) in feats(layer):
        netfe.setdefault(net, []).append((layer, g, tag))
open_nets = []
for net, fl in netfe.items():
    if net.startswith("__nc"):
        continue
    n = len(fl)
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for a in range(n):
        for b in range(a + 1, n):
            la, ga, ta = fl[a]
            lb, gb, tb = fl[b]
            through = ta == tb and (ta.startswith("via") or ta.startswith("pad"))
            if (la == lb and ga.intersects(gb) and ga.intersection(gb).area > 1e-4) or (la != lb and through):
                par[find(a)] = find(b)
    roots = {find(a) for a in range(n)}
    if len(roots) > 1:
        open_nets.append((net, len(roots)))
npads = {}
for p in B.pads:
    if p["net"]:
        npads[p["net"]] = npads.get(p["net"], 0) + 1
print("DRC clearance/edge/hole errors:", len(errors))
for e in errors[:40]:
    print("  ", e)
print("open nets:", open_nets)
print("nets:", len(npads), "pads:", len(B.pads), "segments:", len(segs), "vias:", len(R["vias"]))
wid = {}
for s in segs:
    if s[0] in ("5V", "GND"):
        L = math.dist(s[2], s[3])
        wid[s[4]] = wid.get(s[4], 0) + L
print("power track length by width:", {k: round(v) for k, v in wid.items()})

# ---- silk
hf = HersheyFonts()
hf.load_default_font("futural")


def text_lines(x, y, h, s, mirror):
    hf.normalize_rendering(h)
    ls = list(hf.lines_for_text(s))
    if not ls:
        return []
    xs = [p[0] for l in ls for p in l]
    ys = [p[1] for l in ls for p in l]
    cx = (min(xs) + max(xs)) / 2
    y0 = min(ys)
    out = []
    for (a, b) in ls:
        ax, ay, bx, by = a[0] - cx, a[1] - y0, b[0] - cx, b[1] - y0
        if mirror:
            ax, bx = -ax, -bx
        out.append((x + ax, y + ay, x + bx, y + by))
    return out


mask_open = {0: [], 1: []}
for p in B.pads:
    for l in LAY[p["layer"]]:
        mask_open[l].append(B.pad_poly(p).buffer(0.05))
silk_lines = {0: [], 1: []}
for side, l in (("F", 0), ("B", 1)):
    avoid = unary_union(mask_open[l] + [h.buffer(0.1) for h in holes]).buffer(0.2)
    for it in B.silk[side]:
        ls = [it[1:5]] if it[0] == "line" else text_lines(*it[1:])
        for (x1, y1, x2, y2) in ls:
            g = LineString([(x1, y1), (x2, y2)])
            if g.length > 0 and not g.intersects(avoid) and OUT.buffer(-0.5).contains(g):
                silk_lines[l].append((x1, y1, x2, y2))


# ---- Gerber writer
class Gerber:
    def __init__(self, func):
        self.h = ["%TF.GenerationSoftware,PriceWhisperer,deck-fab,1.0*%", f"%TF.FileFunction,{func}*%",
                  "%TF.SameCoordinates,Original*%", "%FSLAX46Y46*%", "%MOMM*%", "%LPD*%", "G01*"]
        self.ap = {}
        self.body = []
        self.cur = None

    def _ap(self, spec):
        if spec not in self.ap:
            self.ap[spec] = 10 + len(self.ap)
        d = self.ap[spec]
        if d != self.cur:
            self.body.append(f"D{d}*")
            self.cur = d

    @staticmethod
    def c(v):
        return str(int(round(v * 1e6)))

    def flash(self, spec, x, y):
        self._ap(spec)
        self.body.append(f"X{self.c(x)}Y{self.c(y)}D03*")

    def line(self, w, pts):
        self._ap(f"C,{w:.3f}")
        self.body.append(f"X{self.c(pts[0][0])}Y{self.c(pts[0][1])}D02*")
        for (x, y) in pts[1:]:
            self.body.append(f"X{self.c(x)}Y{self.c(y)}D01*")

    def pad(self, p, grow=0.0):
        w, h = p["w"] + grow, p["h"] + grow
        if p["kind"] == "rect":
            spec = f"R,{w:.3f}X{h:.3f}"
        elif p["kind"] == "circle":
            spec = f"C,{w:.3f}"
        else:
            spec = f"O,{w:.3f}X{h:.3f}"
        self.flash(spec, p["cx"], p["cy"])

    def save(self, name):
        aps = [f"%ADD{d}{spec}*%" for spec, d in sorted(self.ap.items(), key=lambda kv: kv[1])]
        open(os.path.join(OUTD, name), "w").write("\n".join(self.h + aps + self.body + ["M02*"]) + "\n")


PRE = "pw-deck"
for l, (cu, mask, silkf, side, n) in enumerate([("Copper,L1,Top", "Soldermask,Top", "Legend,Top", "F", 1),
                                               ("Copper,L2,Bot", "Soldermask,Bot", "Legend,Bot", "B", 2)]):
    g = Gerber(cu)
    for p in B.pads:
        if l in LAY[p["layer"]]:
            g.pad(p)
    for (_, x, y) in R["vias"]:
        g.flash(f"C,{VIA_D:.3f}", x, y)
    for s in segs:
        if s[1] == l:
            g.line(s[4], [s[2], s[3]])
    g.save(f"{PRE}-{side}_Cu.g{'tl' if l == 0 else 'bl'}")
    m = Gerber(mask)
    for p in B.pads:
        if l in LAY[p["layer"]]:
            m.pad(p, 0.1)
    for (x, y, d) in B.npth:
        m.flash(f"C,{d + 0.2:.3f}", x, y)
    m.save(f"{PRE}-{side}_Mask.g{'ts' if l == 0 else 'bs'}")
    s_ = Gerber(silkf)
    for (x1, y1, x2, y2) in silk_lines[l]:
        s_.line(0.15, [(x1, y1), (x2, y2)])
    s_.save(f"{PRE}-{side}_Silkscreen.g{'to' if l == 0 else 'bo'}")
e = Gerber("Profile,NP")
e.line(0.1, list(OUT.exterior.coords))
for c in B.cutouts:
    e.line(0.1, list(c.exterior.coords))
e.save(f"{PRE}-Edge_Cuts.gm1")


def excellon(name, plated, tools, slots=()):
    L = ["M48", f"; {'PLATED' if plated else 'NON-PLATED'} holes, PriceWhisperer Deck rev A", "FMAT,2", "METRIC,TZ"]
    ds = sorted({round(d, 3) for (_, _, d) in tools} | {round(s[4], 3) for s in slots})
    for n, d in enumerate(ds):
        L.append(f"T{n + 1}C{d:.3f}")
    L += ["%", "G90", "G05"]
    for n, d in enumerate(ds):
        L.append(f"T{n + 1}")
        for (x, y, dd) in tools:
            if round(dd, 3) == d:
                L.append(f"X{x:.3f}Y{y:.3f}")
        for (x1, y1, x2, y2, dd) in slots:
            if round(dd, 3) == d:
                L.append(f"X{x1:.3f}Y{y1:.3f}G85X{x2:.3f}Y{y2:.3f}")
    L += ["T0", "M30"]
    open(os.path.join(OUTD, name), "w").write("\n".join(L) + "\n")


pth = [(x, y, VIA_DRILL) for (_, x, y) in R["vias"]] + [(p["cx"], p["cy"], p["drill"]) for p in B.pads if p["drill"]]
slots = []
for p in B.pads:
    if p["slot"]:
        sl, sw = p["slot"]
        slots.append((p["cx"] - (sl - sw) / 2, p["cy"], p["cx"] + (sl - sw) / 2, p["cy"], sw))
excellon(f"{PRE}-PTH.drl", True, pth, slots)
excellon(f"{PRE}-NPTH.drl", False, list(B.npth))

# ---- BOM and pin map
with open(ROOT + "/gerber/pw-deck-BOM.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Ref", "Value", "Footprint", "Side", "X mm", "Y mm"])
    for (ref, val, fp, x, y, side) in B.parts:
        w.writerow([ref, val, fp, "top" if side == "F" else "bottom", f"{x:.3f}", f"{y:.3f}"])
pickle.dump(dict(segs=segs, vias=R["vias"], silk=silk_lines, assign=assign, led_order=B.LED_ORDER,
                 errors=errors, open_nets=open_nets), open(ROOT + "/build/fab.pkl", "wb"))

# ---- preview
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP
fig, axs = plt.subplots(1, 2, figsize=(15, 10.2), facecolor="#0e1420")
for l, ax in enumerate(axs):
    ax.set_facecolor("#0e1420")
    ax.add_patch(MP(np.array(OUT.exterior.coords), closed=True, fc="#123524", ec="#d9c48a", lw=1.2))
    col = "#e0453f" if l == 0 else "#3f8fe0"
    for s in segs:
        if s[1] == l:
            ax.plot([s[2][0], s[3][0]], [s[2][1], s[3][1]], color=col, lw=s[4] * 4.6, solid_capstyle="round")
    for p in B.pads:
        if l in LAY[p["layer"]]:
            ax.add_patch(MP(np.array(B.pad_poly(p).exterior.coords), closed=True, fc="#e9c46a", ec="none"))
        if p["drill"]:
            ax.add_patch(plt.Circle((p["cx"], p["cy"]), p["drill"] / 2, fc="#0e1420", ec="none"))
    for (_, x, y) in R["vias"]:
        ax.add_patch(plt.Circle((x, y), VIA_D / 2, fc="#c9d1d9", ec="none"))
        ax.add_patch(plt.Circle((x, y), VIA_DRILL / 2, fc="#0e1420", ec="none"))
    for h in holes:
        ax.add_patch(MP(np.array(h.exterior.coords), closed=True, fc="#0e1420", ec="#6b7280", lw=0.4))
    for (x1, y1, x2, y2) in silk_lines[l]:
        ax.plot([x1, x2], [y1, y2], color="#f4f4f5", lw=0.5)
    ax.set_aspect("equal")
    ax.set_xlim(G.PCB_X0 - 2, G.PCB_X1 + 2)
    ax.set_ylim(G.PCB_Y0 - 2, G.PCB_Y1 + 2)
    ax.axis("off")
    ax.set_title("Top copper + silk (switch side)" if l == 0 else "Bottom copper + silk (seen through the board)", color="#e6ecf7", fontsize=13)
plt.tight_layout()
plt.savefig(ROOT + "/docs/pcb-preview.png", dpi=150, facecolor=fig.get_facecolor())
print("written", sorted(os.listdir(OUTD)))
