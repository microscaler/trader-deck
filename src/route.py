"""Grid maze router (2 layers) for the Deck board. Writes routed.pkl."""
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in ("build", "gerber", "stl", "kicad", "docs"):
    _os.makedirs(_os.path.join(ROOT, _d), exist_ok=True)

import sys, time, heapq, pickle, math
import numpy as np
import shapely
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
import geom as G
import board as B

GRID = 0.25
TW = 0.30            # track width
CLR = 0.20           # copper to copper
EPS = 0.04
VIA_D, VIA_DRILL = 0.60, 0.30
HOLE_CLR = 0.30      # copper to unplated hole / cutout edge
EDGE_CLR = 0.45
R_T = CLR + TW / 2 + EPS
R_V = CLR + VIA_D / 2 + EPS

pinmap, assign = B.build()
OUT = B.outline()
KEEP = B.keepouts()
X0, Y0 = G.PCB_X0, G.PCB_Y0
NI = int(round((G.PCB_X1 - X0) / GRID)) + 1
NJ = int(round((G.PCB_Y1 - Y0) / GRID)) + 1
XS = X0 + np.arange(NI) * GRID
YS = Y0 + np.arange(NJ) * GRID

nets = sorted({p["net"] for p in B.pads if p["net"]})
NID = {n: i + 1 for i, n in enumerate(nets)}

occT = [np.zeros((NI, NJ), np.int16) for _ in range(2)]
occV = [np.zeros((NI, NJ), np.int16) for _ in range(2)]
viahard = np.zeros((NI, NJ), bool)


def cells(poly):
    """Grid nodes inside poly -> (ii, jj) arrays."""
    minx, miny, maxx, maxy = poly.bounds
    i0 = max(0, int(math.floor((minx - X0) / GRID)))
    i1 = min(NI - 1, int(math.ceil((maxx - X0) / GRID)))
    j0 = max(0, int(math.floor((miny - Y0) / GRID)))
    j1 = min(NJ - 1, int(math.ceil((maxy - Y0) / GRID)))
    if i1 < i0 or j1 < j0:
        return np.zeros(0, int), np.zeros(0, int)
    xx, yy = np.meshgrid(XS[i0:i1 + 1], YS[j0:j1 + 1], indexing="ij")
    shapely.prepare(poly)
    m = shapely.contains_xy(poly, xx, yy)
    ii, jj = np.nonzero(m)
    return ii + i0, jj + j0


def stamp(arr, poly, nid):
    ii, jj = cells(poly)
    if len(ii) == 0:
        return
    a = arr[ii, jj]
    if nid == -1:
        arr[ii, jj] = -1
        return
    new = np.where(a == 0, nid, np.where(a == nid, nid, np.where(a == -1, -1, -2)))
    arr[ii, jj] = new


LAYERS = {"F": [0], "B": [1], "*": [0, 1]}

# ---- hard obstacles
whole = box(X0 - 1, Y0 - 1, G.PCB_X1 + 1, G.PCB_Y1 + 1)
for l in range(2):
    stamp(occT[l], whole.difference(OUT.buffer(-(EDGE_CLR + TW / 2))), -1)
    stamp(occV[l], whole.difference(OUT.buffer(-(EDGE_CLR + VIA_D / 2))), -1)
holes_geom = [Point(x, y).buffer(d / 2, 32) for (x, y, d) in B.npth] + list(B.cutouts)
for hg in holes_geom:
    for l in range(2):
        stamp(occT[l], hg.buffer(HOLE_CLR + TW / 2 + EPS), -1)
        stamp(occV[l], hg.buffer(HOLE_CLR + VIA_D / 2 + EPS), -1)
stamp(occT[1], KEEP.buffer(TW / 2), -1)
for l in range(2):
    stamp(occV[l], KEEP.buffer(VIA_D / 2), -1)

# ---- pads
padpoly = [B.pad_poly(p) for p in B.pads]
for p, poly in zip(B.pads, padpoly):
    nid = NID.get(p["net"], -1) if p["net"] else -1
    for l in LAYERS[p["layer"]]:
        stamp(occT[l], poly.buffer(R_T), nid)
        stamp(occV[l], poly.buffer(R_V), nid)
        stamp(occV[l], poly.buffer(VIA_D / 2 + 0.15), -1)     # no via in or touching a pad


def pad_cells(k):
    p, poly = B.pads[k], padpoly[k]
    inner = poly.buffer(-0.08)
    ii, jj = cells(inner if not inner.is_empty else poly)
    out = []
    for l in LAYERS[p["layer"]]:
        out += [(l, int(i), int(j)) for i, j in zip(ii, jj)]
    return out


tracks = []   # (net, layer, [(x,y),...])
vias = []     # (net, x, y)
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
PREF_COST = 1.0
OFF_COST = 1.7
VIA_COST = 14.0
TURN_COST = 0.6


def astar(nid, sources, targets, tb):
    okT = [((occT[l] == 0) | (occT[l] == nid)).tobytes() for l in range(2)]
    okv = ((occV[0] == 0) | (occV[0] == nid)) & ((occV[1] == 0) | (occV[1] == nid)) & ~viahard
    okV = okv.tobytes()
    tset = set(targets)
    ti0, ti1, tj0, tj1 = tb
    best = {}
    heap = []
    came = {}
    for (l, i, j) in sources:
        s = (l, i, j, 4)
        best[s] = 0.0
        h = max(ti0 - i, 0, i - ti1) + max(tj0 - j, 0, j - tj1)
        heapq.heappush(heap, (h, 0.0, l, i, j, 4))
    pop, push = heapq.heappop, heapq.heappush
    while heap:
        f, g, l, i, j, d = pop(heap)
        s = (l, i, j, d)
        if best.get(s, 1e18) < g:
            continue
        if (l, i, j) in tset:
            path = [(l, i, j)]
            while s in came:
                s = came[s]
                if (s[0], s[1], s[2]) != path[-1]:
                    path.append((s[0], s[1], s[2]))
            return path[::-1]
        ok = okT[l]
        for nd in range(4):
            di, dj = DIRS[nd]
            a, b = i + di, j + dj
            if a < 0 or b < 0 or a >= NI or b >= NJ or not ok[a * NJ + b]:
                continue
            horiz = nd < 2
            step = PREF_COST if (horiz == (l == 1)) else OFF_COST
            ng = g + step + (TURN_COST if (d != 4 and d != nd) else 0.0)
            ns = (l, a, b, nd)
            if ng < best.get(ns, 1e18):
                best[ns] = ng
                came[ns] = s
                h = max(ti0 - a, 0, a - ti1) + max(tj0 - b, 0, b - tj1)
                push(heap, (ng + h, ng, l, a, b, nd))
        if okV[i * NJ + j]:
            ns = (1 - l, i, j, 4)
            ng = g + VIA_COST
            if ng < best.get(ns, 1e18):
                best[ns] = ng
                came[ns] = s
                h = max(ti0 - i, 0, i - ti1) + max(tj0 - j, 0, j - tj1)
                push(heap, (ng + h, ng, 1 - l, i, j, 4))
    return None


def commit(net, path):
    nid = NID[net]
    run = [path[0]]
    for k in range(1, len(path) + 1):
        if k < len(path) and path[k][0] == run[-1][0]:
            run.append(path[k])
            continue
        if len(run) > 1:
            l = run[0][0]
            pts = [(float(XS[i]), float(YS[j])) for (_, i, j) in run]
            simp = [pts[0]]
            for q in range(1, len(pts) - 1):
                (ax, ay), (bx, by), (cx, cy) = simp[-1], pts[q], pts[q + 1]
                if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9:
                    simp.append(pts[q])
            simp.append(pts[-1])
            tracks.append((net, l, simp))
            ls = LineString(simp)
            stamp(occT[l], ls.buffer(TW / 2 + R_T), nid)
            stamp(occV[l], ls.buffer(TW / 2 + R_V), nid)
        if k < len(path):
            (_, i, j) = path[k]
            x, y = float(XS[i]), float(YS[j])
            vias.append((net, x, y))
            pt = Point(x, y)
            for l in range(2):
                stamp(occT[l], pt.buffer(VIA_D / 2 + R_T), nid)
                stamp(occV[l], pt.buffer(VIA_D / 2 + R_V), nid)
            ii, jj = cells(pt.buffer(1.0))
            viahard[ii, jj] = True
            run = [path[k]]


def route_net(net, first=None):
    idx = [k for k, p in enumerate(B.pads) if p["net"] == net]
    if len(idx) < 2:
        return True
    if first and first in [B.pads[k]["ref"] for k in idx]:
        start = [k for k in idx if B.pads[k]["ref"] == first][0]
    else:
        start = idx[0]
    tree = list(pad_cells(start))
    done = [start]
    todo = [k for k in idx if k != start]
    ok = True
    while todo:
        # nearest unconnected pad to any connected pad
        def dist(k):
            return min(abs(B.pads[k]["cx"] - B.pads[d]["cx"]) + abs(B.pads[k]["cy"] - B.pads[d]["cy"]) for d in done)
        k = min(todo, key=dist)
        todo.remove(k)
        tg = pad_cells(k)
        ti = [c[1] for c in tg]
        tj = [c[2] for c in tg]
        path = astar(NID[net], tree, tg, (min(ti), max(ti), min(tj), max(tj)))
        if path is None:
            print("   FAILED", net, B.pads[k]["ref"], B.pads[k]["pin"], flush=True)
            ok = False
            continue
        commit(net, path)
        tree += path + tg
        done.append(k)
    return ok


def reset():
    global occT, occV, viahard, tracks, vias
    occT = [a.copy() for a in occT0]
    occV = [a.copy() for a in occV0]
    viahard = np.zeros((NI, NJ), bool)
    tracks = []
    vias = []


occT0 = [a.copy() for a in occT]
occV0 = [a.copy() for a in occV]


def main():
    t0 = time.time()
    local = [n for n in nets if n.startswith("N_")]
    data = sorted([n for n in nets if n.startswith("LD")], key=lambda s: int(s[2:]))
    matrix = [f"COL{c}" for c in range(4)] + [f"ROW{r}" for r in range(4)]
    misc = ["ENC_A", "ENC_B", "OLED_RES", "OLED_CS", "OLED_SCK", "OLED_MOSI", "OLED_DC", "3V3"]
    order = local + ["5V", "GND"] + data + matrix + misc
    assert set(order) == set(nets), set(nets) ^ set(order)
    for attempt in range(12):
        reset()
        failed = []
        for n in order:
            if not route_net(n, first="U1"):
                failed.append(n)
        print(f"attempt {attempt}: failed {failed} tracks {len(tracks)} vias {len(vias)} {time.time() - t0:.0f}s", flush=True)
        if not failed:
            break
        order = failed + [n for n in order if n not in failed]
    pickle.dump(dict(tracks=tracks, vias=vias, failed=failed, order=order), open(ROOT + "/build/routed.pkl", "wb"))


if __name__ == "__main__":
    main()
