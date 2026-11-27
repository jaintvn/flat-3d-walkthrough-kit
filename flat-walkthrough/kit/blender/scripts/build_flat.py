"""Builds the Type G 2BHK flat in Blender from layout.py.

Run:  Blender -b --factory-startup -P build_flat.py -- <out.blend>
"""
import bpy, sys, os, math, random
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib, layout, lib
importlib.reload(layout); importlib.reload(lib)
from layout import *
from lib import MB, coll, bevel, soft, subsurf, get_mat

random.seed(11)
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else None
C = 0.01  # cm -> m


# =================================================================== scene setup
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 1.0
    lib.make_all()


# =================================================================== helpers (cm)
from items import Item, local_item, C
import items, furnish
importlib.reload(items); importlib.reload(furnish)


ZONE_MAT = {
    "room": "M_Wall_Paint", "passage": "M_Wall_Paint", "kitchen": "M_Wall_Paint",
    "wet": "M_Bath_WallTile", "vanity": "M_Bath_WallTile", "balcony": "M_Ext_Paint",
    "exterior": "M_Ext_Paint", "service": "M_Concrete",
}


# =================================================================== architecture
def build_walls():
    cw = coll("01_Architecture/ARCH_Walls")
    skirt = Item("ARCH_Skirting", coll("01_Architecture/ARCH_Trim"))
    for name, x0, x1, y0, y1, openings, h in W:
        ax = "x" if (x1 - x0) >= (y1 - y0) else "y"
        a0, a1 = (x0, x1) if ax == "x" else (y0, y1)
        t0, t1 = (y0, y1) if ax == "x" else (x0, x1)

        def side_kind(a, t):
            return zone_at(a, t)[1] if ax == "x" else zone_at(t, a)[1]

        brk = {a0, a1}
        for o in openings:
            brk.update([max(a0, o[0]), min(a1, o[1])])
        prevA = prevB = None
        for a in range(int(a0), int(a1) + 1):
            kA, kB = side_kind(a, t0 - 3), side_kind(a, t1 + 3)
            if prevA is not None and (kA != prevA or kB != prevB):
                brk.add(a)
            prevA, prevB = kA, kB
        brk = sorted(brk)
        it = Item(name, cw)
        intervals = []
        for p, q in zip(brk[:-1], brk[1:]):
            if q - p < 0.5:
                continue
            mid = (p + q) / 2
            op = next((o for o in openings if o[0] <= mid <= o[1]), None)
            pieces = [(0, h)] if op is None else ([(0, op[2])] if op[2] > 0 else []) + ([(op[3], h)] if op[3] < h else [])
            intervals.append((p, q, pieces, op))
        for i, (p, q, pieces, op) in enumerate(intervals):
            mid = (p + q) / 2
            kA, kB = side_kind(mid, t0 - 3), side_kind(mid, t1 + 3)
            mA, mB = ZONE_MAT[kA], ZONE_MAT[kB]
            jamb = mA if kA in ("room", "kitchen", "passage") else mB
            for z0, z1 in pieces:
                mats = {"+z": "M_WallTop", "-z": "M_Wall_Paint"}
                if op is not None and z1 <= op[2] + 0.1 and op[4] in ("window", "vent"):
                    mats["+z"] = "M_Granite_Black"  # window sill
                elif op is not None and z0 > 0:
                    mats["-z"] = jamb  # soffit over opening
                if ax == "x":
                    mats.update({"-y": mA, "+y": mB, "-x": jamb, "+x": jamb})
                else:
                    mats.update({"-x": mA, "+x": mB, "-y": jamb, "+y": jamb})
                skip = set()
                if z0 == 0:
                    skip.add("-z")
                # skip internal end faces between two full-height neighbours
                full = pieces == [(0, h)]
                endA, endB = ("-x", "+x") if ax == "x" else ("-y", "+y")
                if full and i > 0 and intervals[i - 1][2] == [(0, h)]:
                    skip.add(endA)
                if full and i < len(intervals) - 1 and intervals[i + 1][2] == [(0, h)]:
                    skip.add(endB)
                if ax == "x":
                    it.box(p, q, t0, t1, z0, z1, mats, skip)
                else:
                    it.box(t0, t1, p, q, z0, z1, mats, skip)
                # skirting (10 cm vitrified-tile skirting) on room-facing faces of floor-level pieces
                if z0 == 0:
                    for kind, t, sgn in ((kA, t0, -1), (kB, t1, 1)):
                        if kind in ("room", "passage", "kitchen"):
                            if ax == "x":
                                skirt.box(p, q, t + sgn * 1.0, t, 0, 10, "M_Floor_Marble")
                            else:
                                skirt.box(t + sgn * 1.0, t, p, q, 0, 10, "M_Floor_Marble")
        it.done()
    skirt.done()


def grid_cells(rects):
    xs = sorted({v for r in rects for v in (r[0], r[1])})
    ys = sorted({v for r in rects for v in (r[2], r[3])})
    return xs, ys


def build_floor_ceiling():
    ca = coll("01_Architecture/ARCH_Floors")
    cc = coll("01_Architecture/ARCH_Ceilings")
    foot = [(-20, 1609, -20, 572), (1075, 1820, -250, -20)]
    rects = foot + [(z[2], z[3], z[4], z[5]) for z in ZONES]
    xs, ys = grid_cells(rects)
    fl = Item("ARCH_FloorFinish", ca)
    ce = Item("ARCH_CeilingSlab", cc)

    def in_foot(x, y):
        return any(r[0] <= x <= r[1] and r[2] <= y <= r[3] for r in foot)

    FM = {"wet": "M_Bath_FloorTile", "balcony": "M_Balcony_WoodTile", "service": "M_Concrete", "passage": "M_Floor_Passage"}
    for x0, x1 in zip(xs[:-1], xs[1:]):
        for y0, y1 in zip(ys[:-1], ys[1:]):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if not in_foot(cx, cy):
                continue
            zname, kind = zone_at(cx, cy)
            if zname == "ShaftT1":
                continue
            fm = FM.get(kind, "M_Floor_Marble")
            fl.face([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], fm)
            cm = "M_Ext_Paint" if kind == "balcony" else ("M_Concrete" if kind == "service" else "M_Ceiling_White")
            ce.face([(x0, y0, H_SLAB), (x0, y1, H_SLAB), (x1, y1, H_SLAB), (x1, y0, H_SLAB)], cm)
    fl.done()
    ce.done()
    # structural slabs (below floor and above ceiling) with painted edges
    for nm, z0, z1 in (("ARCH_SlabBelow", -16, -0.2), ("ARCH_SlabAbove", H_SLAB + 0.2, H_SLAB + 16)):
        it = Item(nm, coll("01_Architecture/ARCH_Structure"))
        # the face touching the floor finish / ceiling (2 mm away) is hidden and is left out: on phone GPUs the two
        # would z-fight and the black (fully covered) slab shows through as streaks
        hidden = ("+z",) if nm == "ARCH_SlabBelow" else ("-z",)
        for (x0, x1, y0, y1) in foot:
            it.box(x0, x1, y0, y1, z0, z1, {"*": "M_Ext_Paint", "+z": "M_Concrete", "-z": "M_Ext_Paint"}, skip=hidden)
        # extend slabs as a 60 cm sunshade / chajja beyond the flat line (estimated)
        it.box(-80, 1669, 572, 632, z0, z1, "M_Ext_Paint") if nm == "ARCH_SlabAbove" else None
        it.done()
    # external duct outside Toilet 1 (drawn as "unusable area")
    it = Item("ARCH_Shaft_T1_External", coll("01_Architecture/ARCH_Structure"))
    it.box(265, 410, 572, 650, -16, H_SLAB + 16, "M_Ext_Paint")
    it.done()


def build_false_ceilings():
    cf = coll("01_Architecture/ARCH_FalseCeiling")
    led = Item("FC_CoveLED", coll("03_Lighting/LGT_Emissive"))
    board = Item("FC_Boards", cf)
    ZB, ZT = 265, 271  # band underside / top

    def band(x0, x1, y0, y1, w, sides=("n", "s", "e", "w")):
        # four boards around the perimeter, lip + LED on inner edge
        segs = []
        if "s" in sides: segs.append((x0, x1, y0, y0 + w, "s"))
        if "n" in sides: segs.append((x0, x1, y1 - w, y1, "n"))
        if "w" in sides: segs.append((x0, x0 + w, y0 + (w if "s" in sides else 0), y1 - (w if "n" in sides else 0), "w"))
        if "e" in sides: segs.append((x1 - w, x1, y0 + (w if "s" in sides else 0), y1 - (w if "n" in sides else 0), "e"))
        for bx0, bx1, by0, by1, s in segs:
            board.box(bx0, bx1, by0, by1, ZB, ZT, "M_Ceiling_White")
            # upturned lip + led strip on the inner edge
            if s == "s":
                board.box(bx0 + (w if "w" in sides else 0), bx1 - (w if "e" in sides else 0), by1 - 2, by1, ZT, ZT + 4, "M_Ceiling_White")
                led.box(bx0 + w, bx1 - w, by1 - 5, by1 - 3, ZT, ZT + 1.2, "M_LED_Strip")
            if s == "n":
                board.box(bx0 + (w if "w" in sides else 0), bx1 - (w if "e" in sides else 0), by0, by0 + 2, ZT, ZT + 4, "M_Ceiling_White")
                led.box(bx0 + w, bx1 - w, by0 + 3, by0 + 5, ZT, ZT + 1.2, "M_LED_Strip")
            if s == "w":
                board.box(bx1 - 2, bx1, by0, by1, ZT, ZT + 4, "M_Ceiling_White")
                led.box(bx1 - 5, bx1 - 3, by0, by1, ZT, ZT + 1.2, "M_LED_Strip")
            if s == "e":
                board.box(bx0, bx0 + 2, by0, by1, ZT, ZT + 4, "M_Ceiling_White")
                led.box(bx0 + 3, bx0 + 5, by0, by1, ZT, ZT + 1.2, "M_LED_Strip")

    band(1206, 1589, 0, 300, 50)               # living
    band(906, 1206, 0, 413, 50)                # dining
    band(0, 390, 0, 313, 45)                   # bed 1
    board.box(138, 390, 313, 390, ZB, ZT, "M_Ceiling_White")
    band(402, 732, 162, 552, 45)               # bed 2
    # flat drops
    board.box(546, 906, 0, 150, ZB, ZT, "M_Ceiling_White")    # foyer
    board.box(390, 534, 0, 150, ZB, ZT, "M_Ceiling_White")    # bed1 entry
    board.box(744, 894, 150, 205, 240, 246, "M_Ceiling_White")  # vanity alcove
    board.box(150, 390, 402, 552, 240, 246, "M_Ceiling_White")  # toilet 1
    board.box(744, 894, 217, 457, 240, 246, "M_Ceiling_White")  # toilet 2
    board.done()
    led.done()


DOWNLIGHTS = []


def downlight(x, y, z=265, power=18):
    DOWNLIGHTS.append((x, y, z, power))


def place_downlights():
    for x in (1240, 1555):
        for y in (30, 270):
            downlight(x, y)
    for y in (30, 383):
        for x in (935, 1180):
            downlight(x, y)
    for x, y in ((25, 25), (365, 25), (25, 290), (365, 290), (430, 190), (430, 525), (705, 190), (705, 525)):
        downlight(x, y)
    for x in (600, 726, 852):
        downlight(x, 75)
    downlight(468, 75)
    downlight(819, 178, 240, 10)
    downlight(200, 477, 240, 30)
    downlight(345, 477, 240, 26)
    downlight(819, 300, 240, 30)
    downlight(819, 420, 240, 24)
    for x in (1300, 1480):
        downlight(x, 430, 285, 22)
    it = Item("LGT_DownlightTrims", coll("03_Lighting/LGT_Fixtures"))
    for x, y, z, p in DOWNLIGHTS:
        it.cyl(x, y, z - 0.6, z, 5.5, "M_Ceiling_White", seg=20)
        it.cyl(x, y, z - 0.8, z - 0.6, 4.0, "M_Light_Warm", seg=20)
    it.done()


# =================================================================== openings
def door_leaf(name, hinge, d, n, clear, wall_t, open_deg, main=False):
    cd = coll("01_Architecture/ARCH_Doors")
    hx, hy = hinge
    dx, dy = d
    nx, ny = n
    # frame (4 cm jambs + head) filling the wall thickness
    fr = Item(name + "_Frame", cd)
    jw = 5 if main else 4
    ax = "x" if dx != 0 else "y"
    a_h = hx if ax == "x" else hy
    a_o = a_h + (dx if ax == "x" else dy) * clear
    lo, hi = min(a_h, a_o), max(a_h, a_o)
    t_c = hy if ax == "x" else hx
    t0, t1 = t_c - wall_t / 2 - 1, t_c + wall_t / 2 + 1
    fm = "M_Walnut_Door"
    for a0, a1 in ((lo, lo + jw), (hi - jw, hi)):
        (fr.box(a0, a1, t0, t1, 0, DOOR_H, fm) if ax == "x" else fr.box(t0, t1, a0, a1, 0, DOOR_H, fm))
    (fr.box(lo, hi, t0, t1, DOOR_H - jw, DOOR_H, fm) if ax == "x" else fr.box(t0, t1, lo, hi, DOOR_H - jw, DOOR_H, fm))
    # architraves both sides
    for side in (-1, 1):
        tt = t_c + side * (wall_t / 2 + 1)
        for a0, a1, z0, z1 in ((lo - 6, lo, 0, DOOR_H + 6), (hi, hi + 6, 0, DOOR_H + 6), (lo - 6, hi + 6, DOOR_H, DOOR_H + 6)):
            (fr.box(a0, a1, tt, tt + side * 1.5, z0, z1, fm) if ax == "x" else fr.box(tt, tt + side * 1.5, a0, a1, z0, z1, fm))
    fr.done()
    # leaf: local +X from hinge along closed direction, rotate open towards n
    lw = clear - 2 * jw - 0.6
    lt = 4.5 if main else 3.5
    leaf = Item(name, cd)
    leaf.box(0, lw, -lt / 2, lt / 2, 0.8, DOOR_H - jw - 0.3, "M_Walnut_Door")
    if main:  # raised grooves (prehung veneer flush door) + smart lock
        for zz in (60, 105, 150):
            leaf.box(8, lw - 8, -lt / 2 - 0.3, -lt / 2, zz, zz + 1.2, "M_Brass")
            leaf.box(8, lw - 8, lt / 2, lt / 2 + 0.3, zz, zz + 1.2, "M_Brass")
        leaf.box(lw - 14, lw - 6, -lt / 2 - 2.5, -lt / 2, 95, 125, "M_Black_Gloss")
        leaf.box(lw - 14, lw - 6, lt / 2, lt / 2 + 2.5, 95, 125, "M_Black_Gloss")
    else:
        for zz in (40, 160):
            leaf.box(10, lw - 10, -lt / 2 - 0.2, -lt / 2, zz, zz + 0.8, "M_Walnut")
            leaf.box(10, lw - 10, lt / 2, lt / 2 + 0.2, zz, zz + 0.8, "M_Walnut")
    # lever handles both sides
    hxl = lw - 7
    for s in (-1, 1):
        leaf.cyl(hxl, s * (lt / 2 + 1), 100, 101, 2.5, "M_Chrome", seg=16, axis="x") if False else None
        leaf.box(hxl - 2.5, hxl + 2.5, s * lt / 2, s * (lt / 2 + 1.0), 92, 108, "M_Chrome")
        leaf.box(hxl - 13, hxl + 1.5, s * (lt / 2 + 4.5), s * (lt / 2 + 6.0), 98.5, 101.5, "M_Chrome")
        leaf.box(hxl - 1, hxl + 1.5, s * (lt / 2 + 1.0), s * (lt / 2 + 4.5), 98.5, 101.5, "M_Chrome")
    base_ang = math.atan2(dy, dx)
    nang = math.atan2(ny, nx)
    # rotate from closed dir towards n by open_deg
    sgn = 1 if math.sin(nang - base_ang) > 0 else -1
    ang = base_ang + sgn * math.radians(open_deg)
    pivot = (hx + nx * (wall_t / 2 - lt / 2), hy + ny * (wall_t / 2 - lt / 2), 0)
    ob = leaf.mb.build(name, cd, loc=Vector(pivot) * C, rot_z=ang)
    ob["closed_yaw_deg"] = math.degrees(base_ang)
    ob["open_yaw_deg"] = math.degrees(ang)
    ob["interactive_door"] = 1
    return ob


def build_doors():
    for name, hx, hy, d, n, clear, deg in DOORS:
        main = name == "DOOR_Main"
        door_leaf(name, (hx, hy), d, n, clear, EXT_T if main else INT_T, deg, main)


def window(name, ax, a0, a1, t0, t1, sill, head, vent=False):
    """Aluminium sliding window (2 sashes) with MS grill outside. ax = wall long axis."""
    cw = coll("01_Architecture/ARCH_Windows")
    it = Item(name, cw)
    tc = (t0 + t1) / 2
    fw = 4.5

    def B(a_0, a_1, u0, u1, z0, z1, m):
        if ax == "x":
            it.box(a_0, a_1, u0, u1, z0, z1, m)
        else:
            it.box(u0, u1, a_0, a_1, z0, z1, m)
    # outer frame
    B(a0, a1, tc - 4, tc + 4, sill, sill + fw, "M_Alu_Frame")
    B(a0, a1, tc - 4, tc + 4, head - fw, head, "M_Alu_Frame")
    B(a0, a0 + fw, tc - 4, tc + 4, sill, head, "M_Alu_Frame")
    B(a1 - fw, a1, tc - 4, tc + 4, sill, head, "M_Alu_Frame")
    gm = "M_Glass_Frosted" if vent else "M_Glass"
    if vent:  # louvres
        z = sill + fw
        while z < head - fw - 6:
            B(a0 + fw, a1 - fw, tc - 3, tc + 3, z, z + 0.6, gm)
            z += 8
        # exhaust fan disk
        mid = (a0 + a1) / 2
        if ax == "x":
            it.cyl(mid, tc - 4, (sill + head) / 2, (sill + head) / 2 + 0.1, 12, "M_Plastic_White", axis="y")
        else:
            it.cyl(tc - 4, mid, (sill + head) / 2, (sill + head) / 2 + 0.1, 12, "M_Plastic_White", axis="x")
    else:
        mid = (a0 + a1) / 2
        for s0, s1, off in ((a0 + fw, mid + 2, -1.5), (mid - 2, a1 - fw, 1.5)):
            B(s0, s1, tc + off - 1.2, tc + off + 1.2, sill + fw, sill + fw + 4, "M_Alu_Frame")
            B(s0, s1, tc + off - 1.2, tc + off + 1.2, head - fw - 4, head - fw, "M_Alu_Frame")
            B(s0, s0 + 4, tc + off - 1.2, tc + off + 1.2, sill + fw, head - fw, "M_Alu_Frame")
            B(s1 - 4, s1, tc + off - 1.2, tc + off + 1.2, sill + fw, head - fw, "M_Alu_Frame")
            B(s0 + 4, s1 - 4, tc + off - 0.3, tc + off + 0.3, sill + fw + 4, head - fw - 4, gm)
        # MS grill (horizontal flats) on the outer face
        outer = t1 + 0.5 if (ax == "x" and t1 > 0) or (ax == "y" and t1 > 0) else t0 - 0.5
        return it, outer
    return it, None


def build_windows():
    for name, x0, x1, y0, y1, openings, h in W:
        ax = "x" if (x1 - x0) >= (y1 - y0) else "y"
        t0, t1 = (y0, y1) if ax == "x" else (x0, x1)
        for i, (a0, a1, sill, head, kind) in enumerate(openings):
            if kind not in ("window", "vent"):
                continue
            it, _ = window("WIN_%s_%d" % (name, i), ax, a0, a1, t0, t1, sill, head, vent=(kind == "vent"))
            if kind == "window":
                # grill on the exterior face
                ext_t = t1 + 1 if zone_at(*(((a0 + a1) / 2, t1 + 5) if ax == "x" else (t1 + 5, (a0 + a1) / 2)))[1] in ("exterior", "service", "balcony") else t0 - 1
                sgn = 1 if ext_t > t1 else -1
                z = sill + 12
                while z < head - 4:
                    if ax == "x":
                        it.box(a0, a1, ext_t, ext_t + sgn * 1.2, z, z + 1.2, "M_BlackMetal")
                    else:
                        it.box(ext_t, ext_t + sgn * 1.2, a0, a1, z, z + 1.2, "M_BlackMetal")
                    z += 12
                for a in (a0 + 1, a1 - 2.2, (a0 + a1) / 2):
                    if ax == "x":
                        it.box(a, a + 1.2, ext_t, ext_t + sgn * 1.2, sill, head, "M_BlackMetal")
                    else:
                        it.box(ext_t, ext_t + sgn * 1.2, a, a + 1.2, sill, head, "M_BlackMetal")
            it.done()


def slider(name, ax, a0, a1, tc, panels, open_idx=None, head=DOOR_H):
    open_idx = open_idx or {}
    """Aluminium glazed sliding door; panels on two tracks, `open_idx` panels shifted behind neighbours."""
    it = Item(name, coll("01_Architecture/ARCH_Doors"))

    def B(p0, p1, u0, u1, z0, z1, m):
        if ax == "x":
            it.box(p0, p1, u0, u1, z0, z1, m)
        else:
            it.box(u0, u1, p0, p1, z0, z1, m)
    B(a0, a1, tc - 5, tc + 5, 0, 1.5, "M_Alu_Frame")
    B(a0, a1, tc - 5, tc + 5, head - 5, head, "M_Alu_Frame")
    B(a0, a0 + 5, tc - 5, tc + 5, 0, head, "M_Alu_Frame")
    B(a1 - 5, a1, tc - 5, tc + 5, 0, head, "M_Alu_Frame")
    pw = (a1 - a0 - 10) / panels
    for i in range(panels):
        p0 = a0 + 5 + i * pw - 2
        p1 = p0 + pw + 4
        off = -2.2 if i % 2 == 0 else 2.2
        if i in open_idx:  # slide over neighbour panel (other track)
            shift = (open_idx[i] - i) * pw
            p0 += shift
            p1 += shift
        B(p0, p1, tc + off - 1.5, tc + off + 1.5, 1.5, 6.5, "M_Alu_Frame")
        B(p0, p1, tc + off - 1.5, tc + off + 1.5, head - 10, head - 5, "M_Alu_Frame")
        B(p0, p0 + 4.5, tc + off - 1.5, tc + off + 1.5, 1.5, head - 5, "M_Alu_Frame")
        B(p1 - 4.5, p1, tc + off - 1.5, tc + off + 1.5, 1.5, head - 5, "M_Alu_Frame")
        B(p0 + 4.5, p1 - 4.5, tc + off - 0.4, tc + off + 0.4, 6.5, head - 10, "M_Glass")
        # D handle
        hp = p0 + 6 if i % 2 else p1 - 7
        B(hp, hp + 1.5, tc + off - 4, tc + off + 4, 95, 125, "M_Steel")
    it.done()


def build_railings():
    it = Item("ARCH_BalconyRailings", coll("01_Architecture/ARCH_Railings"))
    segs = [("y", -20, -10, 341, 500), ("x", 562, 572, 10, 138), ("x", 562, 572, 906, 1217)]
    for ax, t0, t1, a0, a1 in segs:
        def B(p0, p1, z0, z1, m, u0=t0, u1=t1):
            if ax == "x":
                it.box(p0, p1, u0, u1, z0, z1, m)
            else:
                it.box(u0, u1, p0, p1, z0, z1, m)
        B(a0, a1, 0, 15, "M_Ext_Paint")              # concrete curb
        tc = (t0 + t1) / 2
        B(a0, a1, 15, 105, "M_Glass", tc - 0.6, tc + 0.6)  # toughened glass
        B(a0, a1, 105, 110, "M_Steel", tc - 2.5, tc + 2.5)  # SS cap rail
        n = max(2, int((a1 - a0) / 110) + 1)
        for k in range(n):
            a = a0 + 2 + k * (a1 - a0 - 6) / (n - 1)
            B(a, a + 3, 15, 22, "M_Steel", tc - 2, tc + 2)
    it.done()


def build_switches():
    col = coll("02_Interior/INT_Electrical")
    it = Item("ELEC_SwitchPlates", col)
    plates = [  # (x, y, axis-plane, sign, width)
        ("x", 534, -1, 35, 14), ("y", 162, 1, 625, 14), ("y", 390, -1, 238, 8), ("x", 732, -1, 307, 8),
        ("y", 0, 1, 1460, 14), ("x", 1229, 1, 418, 14), ("y", 312, 1, 1440, 8), ("y", 325, -1, 128, 8),
        ("y", 413, -1, 1225 - 20, 8),
    ]
    for ax, c, s, a, w in plates:
        if ax == "x":
            it.box(c, c + s * 1.0, a - w / 2, a + w / 2, 115, 124, "M_Switch")
        else:
            it.box(a - w / 2, a + w / 2, c, c + s * 1.0, 115, 124, "M_Switch")
    # AC indoor units (practical in Kerala; estimated positions above windows / doors)
    for (x0, x1, y0, y1) in ((300, 385, 0, 22),):
        pass
    it.done()


def build_context():
    col = coll("05_Context")
    g = Item("CTX_Ground", col)
    g.box(-800000, 800000, -800000, 800000, -3001, -3000, "M_Ground")
    g.done()
    rnd = random.Random(3)
    b = Item("CTX_Buildings", col)
    for k in range(26):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(7000, 20000)
        cx, cy = 800 + r * math.cos(a), 270 + r * math.sin(a)
        sx, sy, h = rnd.uniform(900, 2000), rnd.uniform(900, 2000), rnd.uniform(600, 2400)
        b.box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, -3000, -3000 + h, ("M_Building_Far", "M_Ext_Paint", "M_Concrete")[k % 3])
    b.done()
    # trees as simple green blobs
    t = Item("CTX_Trees", col)
    for k in range(140):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(2500, 9000)
        cx, cy = 800 + r * math.cos(a), 270 + r * math.sin(a)
        rr = rnd.uniform(250, 600)
        t.sphere(cx, cy, -3000 + rr * 1.2, rr, rr, rr * 0.9, ("M_Leaf_Dark", "M_Leaf")[k % 2], seg=14, rings=8)
    t.done()
    # neighbouring facade continuation (same building, estimated)
    f = Item("CTX_Facade", col)
    f.box(-1500, 1075, -1500, -20, -3000, 3000, "M_Ext_Paint")     # unit F / core side
    f.box(1075, 1820, -1500, -250, -3000, 3000, "M_Ext_Paint")
    f.box(-20, 1609, -20, 572, -3000, -16, "M_Ext_Paint")
    f.box(-20, 1609, -20, 572, H_SLAB + 16, 3000, "M_Ext_Paint")
    f.done()


# =================================================================== lighting (Blender preview lights)
def build_lights():
    col = coll("03_Lighting/LGT_Lamps")
    s = bpy.context.scene
    for i, (x, y, z, p) in enumerate(DOWNLIGHTS):
        ld = bpy.data.lights.new("DL_%02d" % i, "SPOT")
        ld.energy = p
        ld.color = (1.0, 0.82, 0.64)
        ld.spot_size = math.radians(110)
        ld.spot_blend = 0.7
        ld.shadow_soft_size = 0.03
        ob = bpy.data.objects.new("LGT_Downlight_%02d" % i, ld)
        ob.location = (x * C, y * C, (z - 1.5) * C)
        col.objects.link(ob)
    for name, x, y, z, p, r in (("Pendant", 1060, 230, 192, 40, 0.05), ("FanLiv", 1400, 150, 238, 25, 0.08),
                                ("FanBR1", 195, 205, 238, 20, 0.08), ("FanBR2", 567, 357, 238, 20, 0.08),
                                ("SconceL", 1275, 14, 155, 8, 0.03), ("SconceR", 1445, 14, 155, 8, 0.03),
                                ("BR1_SconceA", 30, 16, 135, 8, 0.04), ("BR1_SconceB", 270, 16, 135, 8, 0.04),
                                ("VanSconce", 870, 196, 166, 6, 0.03), ("BR2_PendA", 712, 326, 205, 10, 0.07),
                                ("BR2_PendB", 712, 530, 205, 10, 0.07), ("Passage", 1450, -135, 270, 60, 0.2)):
        ld = bpy.data.lights.new("PT_" + name, "POINT")
        ld.energy = p
        ld.color = (1.0, 0.8, 0.6)
        ld.shadow_soft_size = r
        ob = bpy.data.objects.new("LGT_" + name, ld)
        ob.location = (x * C, y * C, z * C)
        col.objects.link(ob)
    # sun: morning light from the south-east (+Y side of the plan)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = 4.0
    sd.angle = math.radians(0.6)
    sd.color = (1.0, 0.95, 0.88)
    ob = bpy.data.objects.new("LGT_Sun", sd)
    ob.rotation_euler = (math.radians(55), 0, math.radians(200))
    coll("03_Lighting").objects.link(ob)
    # world sky
    w = bpy.data.worlds.new("World_Sky")
    s.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "MULTIPLE_SCATTERING"
    except Exception:
        pass
    sky.sun_disc = False
    sky.sun_elevation = math.radians(35)
    sky.sun_rotation = math.radians(110)
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.25


def passage_furnish():
    col = coll("05_Context")
    it = Item("CTX_PassageCeiling", col)
    it.box(1075, 1820, -250, -20, 270, 272, "M_Ceiling_White")
    it.done()
    # neighbour door + flat number plaque
    nd = Item("CTX_FlatPlaque", col)
    nd.box(1440, 1462, -21.5, -20, 140, 160, "M_Brass")
    nd.done()


# =================================================================== main
def main():
    reset()
    lib._MATS["M_Floor_Passage"] = lib.plain_tiles("M_Floor_Passage", "#bdb6aa", 0.8, 0.8, grout="#a39c90", rough=0.25)
    build_walls()
    build_floor_ceiling()
    build_false_ceilings()
    build_doors()
    build_windows()
    slider("SLD_Balcony1", "x", 0, 138, 319, 2, open_idx={1: 0})
    slider("SLD_Balcony2", "x", 906, 1217, 419, 4, open_idx={1: 0, 2: 3})
    build_railings()
    place_downlights()
    furnish.furnish_all()
    build_switches()
    build_context()
    passage_furnish()
    build_lights()
    # player spawn marker
    sp = bpy.data.objects.new("PlayerStart_Marker", None)
    sp.location = (SPAWN[0] * C, SPAWN[1] * C, 0.9)
    sp.rotation_euler.z = math.radians(SPAWN[3])
    sp.empty_display_type = "ARROWS"
    coll("04_Markers").objects.link(sp)
    import categories                      # flat_cat on every object (variants; see categories.py)
    rest = categories.tag_all()
    print("CATEGORIES defaulted to arch/light_other:", len(rest), sorted(rest)[:60])
    if OUT:
        bpy.ops.wm.save_as_mainfile(filepath=OUT)
        bpy.ops.file.make_paths_relative()
        bpy.ops.wm.save_mainfile()
        print("SAVED", OUT, len(bpy.data.objects), "objects")


main()
