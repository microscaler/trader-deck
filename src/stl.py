"""Printable case parts for the PriceWhisperer Deck. z = 0 is the underside of the case."""
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in ("build", "gerber", "stl", "kicad", "docs"):
    _os.makedirs(_os.path.join(ROOT, _d), exist_ok=True)

import math, os, json
import numpy as np
import trimesh
from trimesh.creation import extrude_polygon, cylinder, box as tbox
from shapely.geometry import Point, box, Polygon
from shapely.ops import unary_union
import geom as G
import board as B

OUT = ROOT + "/stl"
B.build()
Z_FLOOR, Z_PCB_B = 2.0, 8.5
Z_PCB_T = Z_PCB_B + G.PCB_T            # 10.1
Z_PLATE_B, Z_PLATE_T = Z_PCB_T + 3.5, Z_PCB_T + 5.0     # 13.6 / 15.1
Z_DECK_B, Z_DECK_T = Z_PCB_T + 8.5, Z_PCB_T + 10.5      # 18.6 / 20.6
IX0, IX1, IY0, IY1 = G.PCB_X0 - 0.5, G.PCB_X1 + 0.5, G.PCB_Y0 - 0.5, G.PCB_Y1 + 0.5
WALL = 2.4
OX0, OX1, OY0, OY1 = IX0 - WALL, IX1 + WALL, IY0 - WALL, IY1 + WALL
STEP_Y = 38.3                          # walls rise behind this line for the raised deck
SEG = 48


def rrect(x0, y0, x1, y1, r):
    return box(x0 + r, y0 + r, x1 - r, y1 - r).buffer(r, 12)


def ext(poly, z0, z1):
    m = extrude_polygon(poly, z1 - z0)
    m.apply_translation([0, 0, z0])
    return m


def cyl(x, y, d, z0, z1):
    m = cylinder(radius=d / 2, height=z1 - z0, sections=SEG)
    m.apply_translation([x, y, (z0 + z1) / 2])
    return m


def bx(x0, x1, y0, y1, z0, z1):
    m = tbox(extents=[x1 - x0, y1 - y0, z1 - z0])
    m.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return m


def U(ms):
    return trimesh.boolean.union(ms, engine="manifold")


def D(a, bs):
    return trimesh.boolean.difference([a] + list(bs), engine="manifold")


def along_x(profile_yz, x0, x1):
    """Extrude a (y, z) profile along x."""
    m = extrude_polygon(profile_yz, x1 - x0)
    T = np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)
    m.apply_transform(T)
    return m


# ------------------------------------------------------------------ bottom shell
def bottom_shell():
    outer = ext(rrect(OX0, OY0, OX1, OY1, 4.9), 0, Z_DECK_T)
    cavity = ext(rrect(IX0, IY0, IX1, IY1, 2.5), Z_FLOOR, Z_DECK_T + 1)
    lowcut = bx(OX0 - 1, OX1 + 1, OY0 - 1, STEP_Y, Z_PLATE_T, Z_DECK_T + 1)
    shell = D(outer, [cavity, lowcut])
    add = []
    # ledge the PCB edge rests on, open at the back where the controller hangs
    ring = rrect(IX0, IY0, IX1, IY1, 2.5).difference(rrect(IX0 + 1.5, IY0 + 1.5, IX1 - 1.5, IY1 - 1.5, 1.2))
    ring = ring.difference(box(-13, 60, 13, IY1 + 1))
    for g in (ring.geoms if hasattr(ring, "geoms") else [ring]):
        add.append(ext(g, Z_FLOOR - 0.01, Z_PCB_B))
    holes = []
    for (x, y) in G.POSTS_PLATE_SCREW + G.POSTS_PLATE_SUPPORT:
        add.append(cyl(x, y, 7.0, Z_FLOOR - 0.01, Z_PCB_B))
        add.append(cyl(x, y, 3.9, Z_PCB_B - 0.01, Z_PLATE_B))
        if (x, y) in G.POSTS_PLATE_SCREW:
            holes.append(cyl(x, y, 1.7, Z_PLATE_B - 9, Z_PLATE_B + 1))
    for (x, y) in G.POSTS_DECK:
        add.append(cyl(x, y, 7.0, Z_FLOOR - 0.01, Z_PCB_B))
        add.append(cyl(x, y, 3.9, Z_PCB_B - 0.01, Z_DECK_B))
        holes.append(cyl(x, y, 1.7, Z_DECK_B - 9, Z_DECK_B + 1))
    # extra pillars under the key field, placed clear of everything soldered to the bottom
    avoid = [B.pad_poly(p).buffer(0.3) for p in B.pads if p["layer"] in ("B", "*")]
    avoid += [Point(x, y).buffer(d / 2) for (x, y, d) in B.npth] + list(B.cutouts)
    for (name, r, c) in G.KEYS:
        kx, ky = G.key_xy(name, r, c)
        avoid.append(box(kx - 8.6, ky + 0.2, kx + 7.4, ky + 7.6))     # hot-swap socket body
        avoid.append(box(kx - 3.9, ky - 6.6, kx + 3.9, ky - 2.8))     # LED body and leads
    av = unary_union(avoid)
    pillars = []
    for (tx, ty) in [(-19.05, 19.05), (0, 19.05), (19.05, 19.05), (-19.05, 0), (0, 0), (19.05, 0),
                     (-19.05, -22.0), (0, -22.0), (19.05, -22.0), (-19.05, -44.0), (4.0, -44.0), (0, 45.0), (-25, 45), (20, 45)]:
        best = None
        for dx in np.arange(-4, 4.01, 0.5):
            for dy in np.arange(-4, 4.01, 0.5):
                p = Point(tx + dx, ty + dy)
                if p.distance(av) >= 2.5 and IX0 + 3 < p.x < IX1 - 3 and IY0 + 3 < p.y < IY1 - 3:
                    d = dx * dx + dy * dy
                    if best is None or d < best[0]:
                        best = (d, p.x, p.y)
        if best:
            pillars.append((best[1], best[2]))
            add.append(cyl(best[1], best[2], 3.4, Z_FLOOR - 0.01, Z_PCB_B))
    shell = U([shell] + add)
    # USB-C opening in the back wall, centred on the controller's connector
    usb_z = Z_PCB_B - 1.0 - 1.6
    holes.append(bx(G.MCU[0] - 6.7, G.MCU[0] + 6.7, IY1 - 0.5, OY1 + 1, usb_z - 3.7, usb_z + 3.7))
    for (x, y) in [(OX0 + 11, OY0 + 11), (OX1 - 11, OY0 + 11), (OX0 + 11, OY1 - 11), (OX1 - 11, OY1 - 11)]:
        holes.append(cyl(x, y, 11.6, -1, 0.8))      # recess for 11.2 mm 3M Bumpon SJ5003 feet
    return D(shell, holes), pillars


# ------------------------------------------------------------------ switch plate with guard hinge ears
YA = -22.6                 # hinge axis y
ZA = 21.8                  # hinge axis height above the plate top
EARS = [(6.0, 11.0), (31.0, 36.0)]
KNUCKLES = [(0.7, 5.7), (11.3, 15.3), (26.7, 30.7), (36.3, 41.4)]
GX0, GX1 = 0.7, 41.4       # guard outer x
GYF = -45.5                # guard outer front
G_IN_TOP = 24.5            # inside height above plate


def plate():
    poly = rrect(IX0 + 0.25, IY0 + 0.25, IX1 - 0.25, 39.7, 2.2).union(box(IX0 + 0.25, 30, IX1 - 0.25, 39.7))
    cuts = []
    for (name, r, c) in G.KEYS:
        kx, ky = G.key_xy(name, r, c)
        cuts.append(box(kx - 7.05, ky - 7.05, kx + 7.05, ky + 7.05))
        if name == "FLATTEN":          # plate-mount 2u stabiliser
            for s in (-11.938, 11.938):
                cuts.append(box(kx + s - 3.475, ky - 6.87, kx + s + 3.475, ky + 5.63))
    for (x, y) in G.POSTS_PLATE_SCREW:
        cuts.append(Point(x, y).buffer(1.2, 24))
    poly = poly.difference(unary_union(cuts))
    m = ext(poly, Z_PLATE_B, Z_PLATE_T)
    prof = box(YA - 2.4, -0.01, YA + 2.0, ZA).union(Point(YA, ZA).buffer(2.4, 32).intersection(box(YA - 3, ZA - 3, YA + 2.0, ZA + 3)))
    prof = prof.union(Polygon([(YA + 2.0, -0.01), (YA + 3.6, -0.01), (YA + 2.0, 8.0)]))
    prof = prof.difference(Point(YA, ZA).buffer(1.05, 32))
    ears = []
    for (x0, x1) in EARS:
        e = along_x(prof, x0, x1)
        e.apply_translation([0, 0, Z_PLATE_T])
        ears.append(e)
    return U([m] + ears)


def guard(angle_deg=0.0):
    """Flip cover for FLATTEN, in assembly position. angle 0 = closed."""
    zt0, zt1 = G_IN_TOP, G_IN_TOP + 1.6
    top = along_x(Polygon([(GYF, zt0), (YA + 3.0, zt0), (YA + 3.0, zt0 + 0.4), (YA + 1.8, zt1), (GYF, zt1)]), GX0, GX1)
    parts = [top,
             bx(GX0, GX1, GYF, GYF + 1.2, 0.6, zt0 + 0.01),
             bx(GX0, GX0 + 1.2, GYF, -23.0, 0.6, zt0 + 0.01),
             bx(GX1 - 1.2, GX1, GYF, -23.0, 0.6, zt0 + 0.01)]
    kprof = Point(YA, ZA).buffer(2.4, 32).union(box(YA - 2.4, ZA, YA + 2.4, zt0 + 0.01))
    for (x0, x1) in KNUCKLES:
        parts.append(along_x(kprof, x0, x1))
    g = U(parts)
    pin = cylinder(radius=1.05, height=GX1 - GX0 + 2, sections=32)
    pin.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    pin.apply_translation([(GX0 + GX1) / 2, YA, ZA])
    g = D(g, [pin])
    if angle_deg:
        # opening swings the front edge up and back about the hinge axis
        g.apply_transform(trimesh.transformations.rotation_matrix(math.radians(angle_deg), [-1, 0, 0], [0, YA, ZA]))
    g.apply_translation([0, 0, Z_PLATE_T])
    return g


# ------------------------------------------------------------------ deck (raised cover over display and dial)
WIN = (-5.15, 56.0, 53.6, 15.2)     # window centre x, y, width, height
MOD = (-44.4, 26.1, 44.75, 67.25)   # display module PCB footprint under the deck (70.5 x 22.5)


def deck():
    poly = rrect(IX0 + 0.25, 38.5, IX1 - 0.25, IY1 - 0.25, 2.2).union(box(IX0 + 0.25, 38.5, IX1 - 0.25, 50))
    m = ext(poly, Z_DECK_B, Z_DECK_T)
    add = [bx(IX0 + 0.25, IX1 - 0.25, 38.5, 39.9, Z_PLATE_T + 0.1, Z_DECK_B + 0.01),            # front lip, sits on the plate
           bx(IX0 + 3.0, IX1 - 3.0, IY1 - 1.45, IY1 - 0.25, Z_PCB_T + 0.3, Z_DECK_B + 0.01),     # back skirt
           bx(-40.0, 22.0, MOD[3] + 0.2, MOD[3] + 1.4, Z_DECK_B - 2.6, Z_DECK_B + 0.01),         # display locating ribs
           bx(-36.0, 22.0, MOD[2] - 1.4, MOD[2] - 0.2, Z_DECK_B - 2.6, Z_DECK_B + 0.01)]
    m = U([m] + add)
    cuts = [bx(WIN[0] - WIN[2] / 2, WIN[0] + WIN[2] / 2, WIN[1] - WIN[3] / 2, WIN[1] + WIN[3] / 2, Z_DECK_B - 1, Z_DECK_T + 1),
            cyl(G.ENC[0], G.ENC[1], 21.3, Z_DECK_B - 1, Z_DECK_T + 1)]
    for (x, y) in G.POSTS_DECK:
        cuts.append(cyl(x, y, 2.4, Z_DECK_B - 1, Z_DECK_T + 1))
        cuts.append(cyl(x, y, 4.4, Z_DECK_T - 1.2, Z_DECK_T + 1))
    return D(m, cuts)


def dial_disc():
    m = U([cyl(G.ENC[0], G.ENC[1], 21.0, Z_DECK_B - 0.5, Z_DECK_T), cyl(G.ENC[0], G.ENC[1], 23.0, Z_DECK_B - 1.0, Z_DECK_B)])
    return D(m, [cyl(G.ENC[0], G.ENC[1], 7.6, Z_DECK_B - 2, Z_DECK_T + 1)])


def knob():
    z0 = Z_DECK_T + 1.0
    body = cyl(G.ENC[0], G.ENC[1], 15.0, z0, z0 + 14.0)
    bore = Point(0, 0).buffer(3.12, 32).intersection(box(-4, -4, 4, 1.62))     # 6 mm D-shaft, flat 4.5
    bm = ext(bore, z0 - 1, z0 + 11.0)
    bm.apply_translation([G.ENC[0], G.ENC[1], 0])
    return D(body, [bm, cyl(G.ENC[0], G.ENC[1], 10.0, z0 - 1, z0 + 2.0)])


def riser():
    """Optional glue-on rear foot: tilts the deck about 4 degrees."""
    prof = Polygon([(0, 0), (14, 0), (14, 8.03), (0, 7.0)])
    return along_x(prof, -40, 40)


def pcb():
    poly = B.outline()
    cut = unary_union([Point(x, y).buffer(d / 2, 24) for (x, y, d) in B.npth] + list(B.cutouts))
    return ext(poly.difference(cut), Z_PCB_B, Z_PCB_T)


def flip_for_print(m):
    m = m.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    return m


def settle(m):
    m = m.copy()
    b = m.bounds
    m.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])
    return m


if __name__ == "__main__":
    shell, pillars = bottom_shell()
    P, DK, GD, DD, KN, RS, PC = plate(), deck(), guard(0), dial_disc(), knob(), riser(), pcb()
    GO = guard(102)
    asm = dict(bottom_shell=shell, switch_plate=P, deck=DK, flatten_guard=GD, dial_disc=DD, dial_knob=KN)
    prints = dict(bottom_shell=settle(shell), switch_plate=settle(P), deck=settle(flip_for_print(DK)),
                  flatten_guard=settle(flip_for_print(GD)), dial_disc=settle(DD), dial_knob=settle(flip_for_print(KN)),
                  rear_riser_optional=settle(flip_for_print(RS)))
    rep = {}
    for k, m in prints.items():
        m.export(os.path.join(OUT, f"pw-deck-{k}.stl"))
        e = m.extents
        rep[k] = dict(watertight=bool(m.is_watertight), volume_cm3=round(float(m.volume) / 1000, 1),
                      size_mm=[round(float(v), 1) for v in e], faces=int(len(m.faces)))
        print(f"{k:22s} watertight={m.is_watertight} vol={m.volume / 1000:6.1f} cm3 size={np.round(e, 1)} faces={len(m.faces)}")

    # keycap stand-ins for interference checks and the preview
    caps = []
    for (name, r, c) in G.KEYS:
        kx, ky = G.key_xy(name, r, c)
        w = 37.1 if name == "FLATTEN" else 18.1
        caps.append((name, bx(kx - w / 2, kx + w / 2, ky - 9.05, ky + 9.05, Z_PLATE_T + 6.5, Z_PLATE_T + 20.0)))

    def clash(a, b):
        try:
            v = trimesh.boolean.intersection([a, b], engine="manifold")
            return float(v.volume) if len(v.faces) else 0.0
        except Exception as ex:
            return -1.0
    checks = [("shell/pcb", shell, PC), ("shell/plate", shell, P), ("shell/deck", shell, DK), ("plate/deck", P, DK),
              ("plate/guard closed", P, GD), ("plate/guard open", P, GO), ("deck/disc", DK, DD), ("deck/pcb", DK, PC),
              ("plate/pcb", P, PC), ("guard open/shell", GO, shell), ("knob/disc", KN, DD)]
    for nm, a, b in checks:
        print(f"clash {nm:22s} {clash(a, b):8.3f} mm3")
    for nm, c in caps:
        v1, v2 = clash(GD, c), clash(GO, c)
        if v1 > 0.001 or v2 > 0.001:
            print("clash guard/keycap", nm, round(v1, 2), round(v2, 2))
        v3 = clash(P, c)
        if v3 > 0.001:
            print("clash plate(ears)/keycap", nm, round(v3, 2))
    # sweep the guard through its travel against shell, plate and neighbouring caps
    worst = 0
    for a in range(0, 103, 6):
        g = guard(a)
        for nm, o in [("shell", shell), ("plate", P)] + caps:
            v = clash(g, o)
            if v > 0.01:
                worst = max(worst, v)
                print(f"sweep {a:3d} deg clash with {nm}: {v:.2f} mm3")
    print("sweep worst", worst, "pillars", [(round(x, 1), round(y, 1)) for x, y in pillars])
    json.dump(rep, open(ROOT + "/build/stl_report.json", "w"), indent=1)

    # ---- assembly preview (painter's algorithm, two poses)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    def render(ax, items, az=-32, el=38):
        a, e = math.radians(az), math.radians(el)
        Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        Rx = np.array([[1, 0, 0], [0, math.sin(e), math.cos(e)], [0, -math.cos(e), math.sin(e)]])
        M = Rx @ Rz
        light = np.array([-0.35, -0.45, 0.82])
        polys, cols, depth = [], [], []
        for m, col in items:
            m = m.subdivide_to_size(3.0)
            v = m.vertices @ M.T
            tri = v[m.faces]
            n = m.face_normals
            nv = n @ M.T
            vis = nv[:, 2] > 0
            sh = np.clip(n @ light, 0, 1) * 0.75 + 0.25
            c = np.array(matplotlib.colors.to_rgb(col))
            for t, s, ok in zip(tri, sh, vis):
                if ok:
                    polys.append(t[:, :2])
                    cols.append(np.clip(c * s, 0, 1))
                    depth.append(t[:, 2].mean())
        o = np.argsort(depth)
        ax.add_collection(PolyCollection([polys[i] for i in o], facecolors=[cols[i] for i in o], edgecolors="none", antialiaseds=False))
        allp = np.concatenate(polys)
        ax.set_xlim(allp[:, 0].min() - 4, allp[:, 0].max() + 4)
        ax.set_ylim(allp[:, 1].min() - 4, allp[:, 1].max() + 4)
        ax.set_aspect("equal")
        ax.axis("off")
    capcol = {"BUY MKT": "#1d7a5c", "BUY ASK": "#1d7a5c", "SELL BID": "#8f3335", "SELL MKT": "#8f3335", "FLATTEN": "#d98a1c"}
    fig, axs = plt.subplots(1, 2, figsize=(16, 9), facecolor="#0c111c")
    base = [(shell, "#59657a"), (P, "#2a303c"), (DK, "#59657a"), (DD, "#bfe3ff"), (KN, "#c9d0db")]
    capm = [(c, capcol.get(nm, "#333b4d")) for nm, c in caps]
    render(axs[0], base + capm + [(GD, "#e2574c")])
    axs[0].set_title("Assembled, guard closed (keycaps shown as blocks)", color="#e6ecf7", fontsize=13)
    render(axs[1], [(shell, "#59657a"), (PC, "#1f6b45"), (P, "#2a303c"), (DK, "#59657a"), (DD, "#bfe3ff"), (GO, "#e2574c")], az=-140, el=34)
    axs[1].set_title("From the back, no keycaps, guard open", color="#e6ecf7", fontsize=13)
    plt.tight_layout()
    plt.savefig(ROOT + "/docs/case-preview.png", dpi=110, facecolor=fig.get_facecolor())
