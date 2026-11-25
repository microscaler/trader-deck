"""Write the routed board as a KiCad PCB so KiCad's own DRC can check it."""
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in ("build", "gerber", "stl", "kicad", "docs"):
    _os.makedirs(_os.path.join(ROOT, _d), exist_ok=True)

import pickle, json, os
import geom as G
import board as B
pinmap, assign = B.build()
F = pickle.load(open(ROOT + "/build/fab.pkl", "rb"))
OUTD = ROOT + "/kicad"
os.makedirs(OUTD, exist_ok=True)
nets = sorted({p["net"] for p in B.pads if p["net"]})
nid = {n: i + 1 for i, n in enumerate(nets)}
f = lambda v: f"{v:.4f}".rstrip("0").rstrip(".")
Y = lambda y: f(-y)
L = ['(kicad_pcb (version 20221018) (generator "pwdeck")', ' (general (thickness 1.6))', ' (paper "A4")',
     ' (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (34 "B.Paste" user) (35 "F.Paste" user) (36 "B.SilkS" user) (37 "F.SilkS" user)'
     ' (38 "B.Mask" user) (39 "F.Mask" user) (44 "Edge.Cuts" user) (46 "B.CrtYd" user) (47 "F.CrtYd" user) (48 "B.Fab" user) (49 "F.Fab" user))',
     ' (setup (pad_to_mask_clearance 0.05))', ' (net 0 "")']
for n in nets:
    L.append(f' (net {nid[n]} "{n}")')
refs = {}
for p in B.pads:
    refs.setdefault(p["ref"], []).append(p)
val = {r: v for (r, v, fp, x, y, s) in B.parts}
for ref, ps in refs.items():
    side = "F" if ref in ("ENC1", "J1") else "B"
    L.append(f' (footprint "pwdeck:{ref}" (layer "{side}.Cu") (at 0 0)')
    L.append(f'  (fp_text reference "{ref}" (at {f(ps[0]["cx"])} {Y(ps[0]["cy"])}) (layer "{side}.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))')
    L.append(f'  (fp_text value "{val.get(ref, ref)[:40]}" (at {f(ps[0]["cx"])} {Y(ps[0]["cy"] - 1)}) (layer "{side}.Fab") hide (effects (font (size 0.8 0.8) (thickness 0.12))))')
    for p in ps:
        net = f' (net {nid[p["net"]]} "{p["net"]}")' if p["net"] else ""
        shape = {"rect": "rect", "circle": "circle", "oval": "oval"}[p["kind"]]
        if p["drill"] or p["slot"]:
            dr = f'(drill oval {f(p["slot"][0])} {f(p["slot"][1])})' if p["slot"] else f'(drill {f(p["drill"])})'
            L.append(f'  (pad "{p["pin"]}" thru_hole {shape} (at {f(p["cx"])} {Y(p["cy"])}) (size {f(p["w"])} {f(p["h"])}) {dr} (layers "*.Cu" "*.Mask"){net})')
        else:
            L.append(f'  (pad "{p["pin"]}" smd {shape} (at {f(p["cx"])} {Y(p["cy"])}) (size {f(p["w"])} {f(p["h"])}) (layers "B.Cu" "B.Mask" "B.Paste"){net})')
    L.append(" )")
L.append(' (footprint "pwdeck:holes" (layer "F.Cu") (at 0 0) (attr exclude_from_pos_files exclude_from_bom)')
L.append('  (fp_text reference "H1" (at 0 0) (layer "F.Fab") hide (effects (font (size 0.8 0.8) (thickness 0.12))))')
L.append('  (fp_text value "holes" (at 0 1) (layer "F.Fab") hide (effects (font (size 0.8 0.8) (thickness 0.12))))')
for (x, y, d) in B.npth:
    L.append(f'  (pad "" np_thru_hole circle (at {f(x)} {Y(y)}) (size {f(d)} {f(d)}) (drill {f(d)}) (layers "*.Cu" "*.Mask"))')
L.append(" )")
for poly in [B.outline()] + list(B.cutouts):
    c = list(poly.exterior.coords)
    for a, b in zip(c[:-1], c[1:]):
        L.append(f' (gr_line (start {f(a[0])} {Y(a[1])}) (end {f(b[0])} {Y(b[1])}) (stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))')
for (net, l, a, b, w) in F["segs"]:
    L.append(f' (segment (start {f(a[0])} {Y(a[1])}) (end {f(b[0])} {Y(b[1])}) (width {f(w)}) (layer "{"F.Cu" if l == 0 else "B.Cu"}") (net {nid[net]}))')
for (net, x, y) in F["vias"]:
    L.append(f' (via (at {f(x)} {Y(y)}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net {nid[net]}))')
L.append(")")
open(f"{OUTD}/pw-deck.kicad_pcb", "w").write("\n".join(L) + "\n")
pro = {"board": {"design_settings": {"rules": {"min_clearance": 0.2, "min_copper_edge_clearance": 0.25, "min_hole_clearance": 0.25,
       "min_hole_to_hole": 0.25, "min_through_hole_diameter": 0.3, "min_track_width": 0.2, "min_via_annular_width": 0.13, "min_via_diameter": 0.5}}},
       "net_settings": {"classes": [{"name": "Default", "clearance": 0.2, "track_width": 0.3, "via_diameter": 0.6, "via_drill": 0.3,
                                     "bus_width": 12, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
                                     "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "wire_width": 6}]},
       "meta": {"filename": "pw-deck.kicad_pro", "version": 1}}
json.dump(pro, open(f"{OUTD}/pw-deck.kicad_pro", "w"), indent=1)
print(len(L), "lines")
