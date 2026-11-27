"""Furniture and fittings for the Type G flat (v2: realistic construction + PBR materials).
Positions follow the furniture shown on plan_my_flat.jpg / plan_builder.webp. All values in cm."""
import bpy, bmesh, math, random
from mathutils import Vector
from lib import coll, bevel, soft
from items import (Item, local_item, cushion, upright_cushion, rbox, lathe, shell_arc, curtain, mould_frames, wall_art,
                   place, C, _finish)


class Frame:
    """Local placement frame: origin (bx, by) and yaw (deg). Local +y = 'forward' away from the wall."""

    def __init__(self, bx, by, yaw):
        self.b, self.yaw = Vector((bx, by)), yaw
        a = math.radians(yaw)
        self.c, self.s = math.cos(a), math.sin(a)

    def p(self, x, y, z=0):
        return (self.b.x + x * self.c - y * self.s, self.b.y + x * self.s + y * self.c, z)

    def r(self, rx=0, ry=0, rz=0):
        return (rx, ry, self.yaw + rz)


def drape(name, col, w, l, top, ov_x, ov_y, thick, mat, F, y0, seed=0, nx=40, ny=30, r=4.0):
    """Bedspread/throw lying on a mattress (width w, from local y0 to y0+l) with sides draping down."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    W = w + 2 * (ov_x + r * 0.6)
    L = l + ov_y + r * 0.6
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            s = -W / 2 + W * i / nx
            t = L * j / ny
            x, z = s, top
            ex = abs(s) - w / 2
            if ex > 0:
                arc = math.pi * r / 2
                if ex < arc:
                    th = ex / r
                    x = math.copysign(w / 2 + r * math.sin(th), s)
                    z = top - r * (1 - math.cos(th))
                else:
                    x = math.copysign(w / 2 + r, s)
                    z = top - r - (ex - arc)
            y = y0 + t
            ey = t - l
            if ey > 0:
                arc = math.pi * r / 2
                if ey < arc:
                    th = ey / r
                    y = y0 + l + r * math.sin(th)
                    z -= r * (1 - math.cos(th))
                else:
                    y = y0 + l + r
                    z -= r + (ey - arc)
            # soft wrinkles
            z += 0.6 * math.sin(s * 0.21 + rnd.uniform(0, 0.3)) * math.sin(t * 0.13) + rnd.uniform(-0.15, 0.15)
            if ex > 0 or ey > 0:
                bulge = 1.2 * math.sin(t * 0.25 + s * 0.05)
                if ex > 0:
                    x += math.copysign(bulge * 0.4, s)
            row.append(bm.verts.new(Vector(F.p(x, y, z)) * C))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    ob = _finish(bm, name, col, mat, (0, 0, 0), (0, 0, 0))
    sd = ob.modifiers.new("Solidify", "SOLIDIFY"); sd.thickness = thick * C; sd.offset = 1
    sb = ob.modifiers.new("Subdiv", "SUBSURF"); sb.levels = sb.render_levels = 1
    return ob


# =================================================================== reusable pieces
def bed(col, pre, F, w, l, head_mat, frame_mat, duvet_mat, throw_mat, cush_mats):
    rbox(pre + "_Plinth", col, w - 20, l - 20, 7, "M_BlackMetal", F.p(0, 9 + l / 2, 0), F.yaw, r=0.5)
    rbox(pre + "_Base", col, w + 10, l + 8, 27, frame_mat, F.p(0, 9 + l / 2 + 1, 6), F.yaw, r=1.2)
    rbox(pre + "_HeadPanel", col, w + 36, 6, 122, frame_mat, F.p(0, 3, 0), F.yaw, r=0.6)
    n = int((w + 30) / 16)
    cw = (w + 30) / n
    for k in range(n):
        x = -(w + 30) / 2 + cw * (k + 0.5)
        upright_cushion("%s_Head_%02d" % (pre, k), col, cw - 0.4, 98, 6, head_mat, F.p(x, 6, 20), 0, F.yaw + 180, crown=0.3, side=0.02, cuts=5, seed=k)
    rbox(pre + "_Mattress", col, w, l, 24, "M_Linen_White", F.p(0, 10 + l / 2, 32), F.yaw, r=5, seg=4)
    drape(pre + "_Duvet", col, w + 2, l * 0.74, 57.5, 22, 22, 4, duvet_mat, F, 10 + l * 0.26, seed=len(pre))
    cushion(pre + "_DuvetFold", col, w + 6, 26, 6, duvet_mat, F.p(0, 10 + l * 0.26 + 6, 56), F.yaw, crown=0.15, cuts=6)
    drape(pre + "_Throw", col, w + 4, 50, 62, 26, 10, 1.6, throw_mat, F, 10 + l - 54, seed=3, nx=34, ny=12, r=3)
    for i, x in enumerate((-w / 4 + 2, w / 4 - 2)):
        cushion("%s_Pillow_%d" % (pre, i), col, w / 2 - 8, 40, 13, "M_Linen_White", F.p(x, 34, 56), F.r(-8, 0, 0), crown=0.7, side=0.1, cuts=5, seed=i)
    for i, x in enumerate((-w / 4 + 4, w / 4 - 4)):
        upright_cushion("%s_Cushion_%d" % (pre, i), col, 46, 44, 12, cush_mats[0], F.p(x, 52, 58), 20, F.yaw + 180 + (i - 0.5) * 8, crown=0.55, seed=5 + i)
    upright_cushion(pre + "_Lumbar", col, 42, 26, 11, cush_mats[1], F.p(0, 64, 58), 18, F.yaw + 180, crown=0.55, seed=9)


def side_table(col, name, F, w=48, d=40, h=50, mat="M_Walnut"):
    it = Item(name, col)
    # carcass with drawer reveal and brass pull, on a recessed plinth (built in local, placed by frame)
    ob = rbox(name, col, w, d, h - 8, mat, F.p(0, 0, 8), F.yaw, r=0.6)
    rbox(name + "_Plinth", col, w - 6, d - 6, 8, "M_BlackMetal", F.p(0, 0, 0), F.yaw, r=0.3)
    rbox(name + "_Reveal", col, w - 1, 0.6, 0.6, "M_BlackMetal", F.p(0, d / 2 + 0.05, h - 16), F.yaw, r=0.1)
    rbox(name + "_Pull", col, 14, 1.4, 1.2, "M_Brass", F.p(0, d / 2 + 0.6, h - 10), F.yaw, r=0.3)
    return ob


def wardrobe(col, name, x0, x1, y0, y1, face, h=240, mat="M_Walnut", nd=2, handle="M_Brass"):
    it = Item(name, col)
    it.box(x0, x1, y0, y1, 8, h, mat)
    it.box(x0 + 2, x1 - 2, y0 + 2, y1 - 2, 0, 8, "M_BlackMetal")
    ax = "y" if face in ("+x", "-x") else "x"
    a0, a1 = (y0, y1) if ax == "y" else (x0, x1)
    fc = {"+x": x1, "-x": x0, "+y": y1, "-y": y0}[face]
    s = 1 if face[0] == "+" else -1
    dw = (a1 - a0) / nd
    for k in range(nd):
        g0, g1 = a0 + k * dw, a0 + (k + 1) * dw
        hb = g1 - 5 if k % 2 == 0 else g0 + 3.5
        if ax == "y":
            it.box(fc, fc + s * 0.3, g0 + 0.15, g0 + 0.45, 10, h - 2, "M_BlackMetal")
            it.box(fc + s * 1.2, fc + s * 2.6, hb, hb + 1.5, 70, 170, handle)
            for zz in (78, 162):
                it.box(fc, fc + s * 1.2, hb + 0.3, hb + 1.2, zz - 1, zz + 1, handle)
        else:
            it.box(g0 + 0.15, g0 + 0.45, fc, fc + s * 0.3, 10, h - 2, "M_BlackMetal")
            it.box(hb, hb + 1.5, fc + s * 1.2, fc + s * 2.6, 70, 170, handle)
            for zz in (78, 162):
                it.box(hb + 0.3, hb + 1.2, fc, fc + s * 1.2, zz - 1, zz + 1, handle)
    if ax == "y":
        it.box(fc, fc + s * 0.3, a0, a1, 199.5, 200.2, "M_BlackMetal")
    else:
        it.box(a0, a1, fc, fc + s * 0.3, 199.5, 200.2, "M_BlackMetal")
    ob = it.done()
    bevel(ob, 0.003, 2)
    return ob


def dining_chair(col, name, loc, yaw, fabric="M_Velvet_Beige", wood="M_Walnut"):
    """Curved-back upholstered dining chair (Marquis dining renders). Faces local +y."""
    F = Frame(loc[0], loc[1], yaw)
    rbox(name + "_SeatBase", col, 44, 42, 3, wood, F.p(0, 0, 41), F.yaw, r=0.8)
    cushion(name + "_Seat", col, 46, 44, 7, fabric, F.p(0, 1, 43.5), F.yaw, crown=0.22, side=0.06, cuts=5)
    shell_arc(name + "_Back", col, 23, 150, 49, 80, 5.5, fabric, F.p(0, 1, 0), F.yaw, flare=1.5)
    it = Item(name + "_Legs", col)
    for sx in (-1, 1):
        for sy in (-1, 1):
            it.cyl(sx * 18, sy * 16, 0, 41, 1.3, wood, seg=12, r1=1.9)
    ob = it.mb.build(name + "_Legs", col, loc=Vector(F.p(0, 0, 0)) * C, rot_z=math.radians(F.yaw))
    return ob


def tub_chair(col, name, loc, yaw, fabric="M_Fabric_Cream", wood="M_Walnut"):
    F = Frame(loc[0], loc[1], yaw)
    lathe(name + "_Base", col, [(0, 12), (31, 12), (33, 14), (33, 38), (31, 40), (0, 40)], fabric, F.p(0, 0, 0), F.yaw, seg=48)
    cushion(name + "_Seat", col, 54, 50, 11, fabric, F.p(0, 4, 39), F.yaw, crown=0.25, cuts=5)
    shell_arc(name + "_Shell", col, 30, 250, 36, 74, 10, fabric, F.p(0, 4, 0), F.yaw, flare=3, seg=24)
    it = Item(name + "_Legs", col)
    for a in (45, 135, 225, 315):
        x, y = 22 * math.cos(math.radians(a)), 22 * math.sin(math.radians(a))
        it.cyl(x, y, 0, 13, 1.2, wood, seg=12, r1=1.8)
    it.mb.build(name + "_Legs", col, loc=Vector(F.p(0, 0, 0)) * C, rot_z=math.radians(F.yaw))


def books(col, name, x, y, z, yaw=0, n=4):
    rnd = random.Random(len(name))
    zz = z
    for k in range(n):
        h = rnd.uniform(2.2, 3.5)
        rbox("%s_%d" % (name, k), col, rnd.uniform(20, 26), rnd.uniform(15, 18), h, ("M_Book_A", "M_Book_B", "M_Book_C", "M_Linen_White")[k % 4],
             (x, y, zz), yaw + rnd.uniform(-8, 8), r=0.3, seg=2)
        zz += h


def vessel_basin(col, name, loc, r=20, h=14, mat="M_Basin_Ceramic"):
    prof = [(0, 0.4), (r * 0.6, 0.0), (r * 0.92, 2.5), (r, h * 0.55), (r, h), (r - 0.9, h), (r - 1.2, h * 0.55),
            (r * 0.86, 3.0), (r * 0.55, 1.7), (0, 1.5)]
    return lathe(name, col, prof, mat, loc, 0, seg=56)


def wall_hung_wc(col, name, F):
    cushion(name + "_Bowl", col, 36, 52, 17, "M_Basin_Ceramic", F.p(0, 27, 27), F.yaw, crown=0.04, side=0.14, cuts=5)
    cushion(name + "_Seat", col, 36, 45, 2.4, "M_Basin_Ceramic", F.p(0, 29.5, 44), F.yaw, crown=0.05, side=0.05, cuts=4)
    rbox(name + "_Hinge", col, 16, 3, 2, "M_Chrome", F.p(0, 6, 44), F.yaw, r=0.6)


def rain_shower(col, name, wall_pt, out_dir):
    x, y = wall_pt
    dx, dy = out_dir
    it = Item(name, col)
    it.cyl(x, y, 100, 205, 1.1, "M_Chrome", seg=12)
    hx, hy = x + dx * 32, y + dy * 32
    it.box(min(x, hx) - 0.9, max(x, hx) + 0.9, min(y, hy) - 0.9, max(y, hy) + 0.9, 205, 207, "M_Chrome")
    it.cyl(hx, hy, 200, 203, 12, "M_Chrome", seg=40)
    it.cyl(hx, hy, 199.8, 200, 11, "M_Steel", seg=40)
    it.cyl(x + dx * 2, y + dy * 2, 105, 113, 4.5, "M_Chrome", seg=24)
    it.done()


# =================================================================== rooms
def living():
    col = coll("02_Interior/INT_Living")
    # ---- L sofa (back to the kitchen wall, chaise along the east wall - as drawn)
    rbox("LIV_Sofa_Base", col, 296, 92, 30, "M_Fabric_Beige", (1438, 254, 10), 0, r=2.5)
    rbox("LIV_Sofa_ChaiseBase", col, 96, 92, 30, "M_Fabric_Beige", (1538, 163, 10), 0, r=2.5)
    rbox("LIV_Sofa_BackRail", col, 296, 18, 44, "M_Fabric_Beige", (1438, 291, 38), 0, r=5, seg=4)
    rbox("LIV_Sofa_SideRail", col, 18, 168, 44, "M_Fabric_Beige", (1577, 199, 38), 0, r=5, seg=4)
    rbox("LIV_Sofa_Arm", col, 20, 92, 28, "M_Fabric_Beige", (1300, 254, 38), 0, r=7, seg=4)
    it = Item("LIV_Sofa_Legs", col)
    for x, y in ((1294, 212), (1294, 296), (1440, 212), (1582, 296), (1494, 121), (1582, 121)):
        it.cyl(x, y, 0, 10, 1.6, "M_Brass", seg=16, r1=2.2)
    it.done()
    for i, x in enumerate((1356, 1446)):
        cushion("LIV_Sofa_Seat_%d" % i, col, 88, 72, 14, "M_Fabric_Beige", (x, 245, 39), 0, crown=0.16, cuts=6, seed=i)
    cushion("LIV_Sofa_ChaiseSeat", col, 77, 160, 14, "M_Fabric_Beige", (1529, 201, 39), 0, crown=0.12, cuts=7, seed=7)
    for i, x in enumerate((1352, 1440, 1520)):
        upright_cushion("LIV_Sofa_Back_%d" % i, col, 86, 46, 20, "M_Fabric_Beige", (x, 282, 52), 14, 0, crown=0.3, side=0.05, cuts=6, seed=10 + i)
    for i, y in enumerate((165, 232)):
        upright_cushion("LIV_Sofa_SideBack_%d" % i, col, 66, 46, 20, "M_Fabric_Beige", (1568, y, 52), 14, -90, crown=0.3, side=0.05, cuts=6, seed=20 + i)
    for i, (x, y, m, rz) in enumerate(((1330, 262, "M_Fabric_Sage", 8), (1395, 262, "M_Fabric_Taupe", -5), (1548, 255, "M_Fabric_Charcoal", -40), (1547, 135, "M_Fabric_Sage", -80))):
        upright_cushion("LIV_Sofa_Pillow_%d" % i, col, 44, 44, 13, m, (x, y - 2, 53), 22, rz, crown=0.6, seed=30 + i)
    rbox("LIV_Sofa_Throw", col, 70, 42, 3, "M_Fabric_Charcoal", (1527, 150, 53), 8, r=1.5)
    # ---- armchair + coffee table + rug
    tub_chair(col, "LIV_Armchair", (1266, 168), -110)
    lathe("LIV_CoffeeTable_Drum", col, [(0, 0.5), (30, 0.5), (31, 1.5), (39, 36), (40.5, 37.5), (0, 37.5)], "M_Brass", (1405, 165, 0), 0, seg=64)
    lathe("LIV_CoffeeTable_Top", col, [(0, 37.5), (42.5, 37.5), (43.5, 38.4), (43.5, 40.6), (42.5, 41.5), (0, 41.5)], "M_Quartz_White", (1405, 165, 0), 0, seg=64)
    place("ceramic_vase_03", "LIV_Vase", col, (1388, 152, 41.5), 0, height=30)
    books(col, "LIV_Books", 1420, 178, 41.5, 20, 3)
    rbox("LIV_Rug", col, 210, 175, 1.2, "M_Rug_Beige", (1405, 172, 0), 0, r=2)
    # ---- TV wall: fluted panel, floating unit, TV, sconces
    tv = Item("LIV_TVWall", col)
    tv.box(1262, 1458, 0, 1.5, 0, 265, "M_Moulding_White")
    for k in range(int((1458 - 1262) / 4)):
        tv.cyl(1264 + k * 4, 1.6, 0, 265, 1.7, "M_Moulding_White", seg=10, caps=False)
    tv.done()
    rbox("LIV_TVUnit", col, 190, 40, 32, "M_White_Gloss", (1360, 22, 24), 0, r=0.8)
    rbox("LIV_TVUnit_Top", col, 192, 41, 2, "M_Walnut", (1360, 22.5, 56), 0, r=0.4)
    rbox("LIV_TVUnit_Reveal", col, 189, 0.5, 0.6, "M_BlackMetal", (1360, 42.1, 40), 0, r=0.1)
    rbox("LIV_TV", col, 123, 3, 71, "M_Black_Gloss", (1360, 4.5, 100), 0, r=0.4)
    rbox("LIV_TV_Screen", col, 121, 0.3, 69, "M_Screen", (1360, 6.1, 101), 0, r=0.05)
    place("ceramic_vase_01", "LIV_TVUnit_Vase", col, (1440, 24, 58), 0, height=34)
    books(col, "LIV_TVUnit_Books", 1290, 24, 58, 0, 3)
    for i, x in enumerate((1275, 1445)):
        it = Item("LIV_Sconce_%d" % i, col)
        it.box(x - 4, x + 4, 1.5, 3, 140, 170, "M_Brass")
        it.box(x - 1, x + 1, 3, 9, 152, 158, "M_Brass")
        it.done()
        lathe("LIV_Sconce_Shade_%d" % i, col, [(0, 0), (3.6, 0), (3.6, 40), (0, 40)], "M_Lampshade", (x, 10, 135), 0, seg=24)
    place("potted_plant_01", "LIV_Plant_A", col, (1236, 268, 0), 30, height=150)
    place("potted_plant_02", "LIV_Plant_B", col, (1238, 30, 0), 200, height=80)
    place("ceiling_fan", "LIV_CeilingFan", col, (1400, 150, 285), 0, scale=0.85, top_anchor=True)
    curtain(col, "LIV_Curtain_Drape_L", (1583, 92), (1583, 132), 2, 262, amp=5, seed=1)
    curtain(col, "LIV_Curtain_Drape_R", (1583, 268), (1583, 308), 2, 262, amp=5, seed=2)
    curtain(col, "LIV_Curtain_Sheer", (1579, 98), (1579, 302), 2, 262, amp=3, mat="M_Curtain_Sheer", rod=False, seed=3)


def dining():
    col = coll("02_Interior/INT_Dining")
    F = Frame(1060, 230, 90)          # table long axis along world Y
    rbox("DIN_Table_Top", col, 180, 92, 4, "M_Walnut", F.p(0, 0, 72), F.yaw, r=0.8)
    for sx in (-1, 1):
        rbox("DIN_Table_Leg_%d" % (sx > 0), col, 7, 74, 72, "M_Walnut", F.p(sx * 62, 0, 0), F.yaw, r=0.6)
    rbox("DIN_Table_Stretcher", col, 118, 5, 6, "M_Walnut", F.p(0, 0, 18), F.yaw, r=0.5)
    place("ceramic_vase_01", "DIN_Vase", col, (1060, 230, 76), 0, height=32)
    rbox("DIN_Runner", col, 30, 140, 0.4, "M_Fabric_Sage", (1060, 230, 76), 0, r=0.2)
    for i, yy in enumerate((172, 230, 288)):
        dining_chair(col, "DIN_Chair_W%d" % i, (990, yy), -90)
        dining_chair(col, "DIN_Chair_E%d" % i, (1130, yy), 90)
    # brass linear pendant with glass globes (Marquis)
    pd = Item("DIN_Pendant", col)
    for yy in (175, 285):
        pd.cyl(1060, yy, 206, 285, 0.25, "M_BlackMetal", seg=6)
    pd.box(1058.8, 1061.2, 150, 310, 203, 206, "M_Brass")
    pd.done()
    for k in range(5):
        yy = 160 + k * 35
        lathe("DIN_Pendant_Globe_%d" % k, col, [(0, -12), (3, -11.6), (5.6, -9.5), (6.6, -6), (5.6, -2.5), (3, -0.4), (1, 0), (1, 3), (0, 3)],
              "M_Light_Warm", (1060, yy, 200), 0, seg=32)
    mould_frames(col, "DIN_WallMoulding", ("x", 906, 1), [(168, 405, 20, 95), (168, 405, 105, 245)])
    wall_art(col, "DIN_Painting", ("x", 906, 1), 286, 172, 120, 80, "M_Art_Gold")
    place("potted_plant_01", "DIN_Plant", col, (934, 386, 0), 70, height=135)
    curtain(col, "DIN_Curtain_L", (910, 407), (962, 407), 2, 262, amp=5, seed=4)
    curtain(col, "DIN_Curtain_R", (1161, 407), (1213, 407), 2, 262, amp=5, seed=5)
    rbox("DIN_Rug", col, 190, 240, 1.2, "M_Rug_Grey", (1060, 230, 0), 0, r=2)


def kitchen():
    col = coll("02_Interior/INT_Kitchen")
    kb = Item("KIT_BaseCabinets", col)
    kb.box(1229, 1589, 492, 552, 10, 86, "M_Sage_Gloss")
    kb.box(1529, 1589, 390, 492, 10, 86, "M_Sage_Gloss")
    kb.box(1232, 1589, 497, 552, 0, 10, "M_BlackMetal")
    kb.box(1534, 1589, 390, 497, 0, 10, "M_BlackMetal")
    x = 1229
    while x < 1525:
        kb.box(x, x + 0.35, 491.75, 492, 10, 86, "M_BlackMetal")
        kb.box(x + 3, x + 57, 491.2, 492, 80.5, 82.5, "M_Brass_Brushed")
        if x > 1440:
            kb.box(x, x + 60, 491.75, 492, 50, 50.35, "M_BlackMetal")
        x += 60
    for y in (390, 445):
        kb.box(1528.75, 1529, y, y + 0.35, 10, 86, "M_BlackMetal")
    kb.box(1528.2, 1529, 396, 488, 80.5, 82.5, "M_Brass_Brushed")
    ob = kb.done(); bevel(ob, 0.0015, 1)
    ct = Item("KIT_Countertop", col)
    ct.box(1229, 1589, 489, 552, 86, 90, "M_Quartz_White")
    ct.box(1526, 1589, 390, 489, 86, 90, "M_Quartz_White")
    ct.box(1229, 1588, 550.8, 552, 90, 150, "M_Quartz_White")
    ct.box(1587.8, 1589, 390, 395, 90, 150, "M_Quartz_White")
    ct.box(1587.8, 1589, 395, 505, 90, 105, "M_Quartz_White")
    ct.box(1587.8, 1589, 505, 552, 90, 150, "M_Quartz_White")
    ob = ct.done(); bevel(ob, 0.002, 2)
    # undermount sink + gooseneck tap
    sk = Item("KIT_Sink", col)
    sk.box(1540, 1576, 427, 473, 70, 89.9, "M_Steel")
    sk.cyl(1558, 450, 89.95, 90.0, 2.0, "M_Steel", seg=20)
    sk.cyl(1579, 450, 90, 92, 2.6, "M_Chrome", seg=20)
    sk.cyl(1579, 450, 92, 118, 1.3, "M_Chrome", seg=16)
    sk.done()
    sp = Item("KIT_TapSpout", col)
    for k in range(10):
        a = math.pi * k / 9
        x0, z0 = 1579 - 10 * (1 - math.cos(a)), 118 + 10 * math.sin(a)
        sp.sphere(x0, 450, z0, 1.3, 1.3, 1.3, "M_Chrome", seg=10, rings=6)
    sp.done()
    # hob with burners and knobs
    hb = Item("KIT_Hob", col)
    hb.box(1350, 1430, 500, 545, 90, 90.8, "M_Black_Gloss")
    for (xx, yy, r) in ((1368, 512, 7), (1412, 512, 7), (1368, 533, 5), (1412, 533, 5)):
        hb.cyl(xx, yy, 90.8, 92.2, r, "M_BlackMetal", seg=28)
        hb.cyl(xx, yy, 92.2, 93.2, r * 0.55, "M_Brass_Brushed", seg=24)
    for k in range(4):
        hb.cyl(1362 + k * 18, 494, 80, 82, 1.8, "M_BlackMetal", seg=16, axis="y") if False else None
    hb.done()
    ch = Item("KIT_Chimney", col)
    ch.box(1345, 1435, 500, 552, 155, 160, "M_BlackMetal")
    ch.face([(1345, 500, 160), (1435, 500, 160), (1435, 530, 200), (1345, 530, 200)], "M_Black_Gloss")
    ch.face([(1345, 530, 200), (1435, 530, 200), (1435, 500, 160), (1345, 500, 160)], "M_Black_Gloss")
    ch.box(1345, 1435, 530, 552, 160, 200, "M_BlackMetal")
    ch.box(1370, 1410, 527, 552, 200, 285, "M_BlackMetal")
    ch.done()
    wc = Item("KIT_WallCabinets", col)
    for x0, x1 in ((1229, 1340), (1440, 1589)):
        wc.box(x0, x1, 517, 552, 150, 235, "M_Sage_Gloss")
        nd = max(1, round((x1 - x0) / 50))
        for k in range(1, nd):
            xx = x0 + k * (x1 - x0) / nd
            wc.box(xx - 0.2, xx + 0.2, 516.75, 517, 150, 235, "M_BlackMetal")
        wc.box(x0, x1, 516.6, 517, 150, 151, "M_Brass_Brushed")
    wc.box(1554, 1589, 505, 552, 150, 235, "M_Sage_Gloss")
    ob = wc.done(); bevel(ob, 0.0015, 1)
    led = Item("KIT_UnderCabinetLED", coll("03_Lighting/LGT_Emissive"))
    led.box(1232, 1338, 519, 521, 149.4, 150, "M_LED_Strip")
    led.box(1442, 1586, 519, 521, 149.4, 150, "M_LED_Strip")
    led.done()
    # black fridge + front-load washer against the living-room wall (as annotated)
    rbox("KIT_Fridge", col, 74, 69, 180, "M_Black_Gloss", (1388.5, 347.5, 2), 0, r=1.5)
    rbox("KIT_Fridge_Split", col, 74.2, 0.5, 0.6, "M_BlackMetal", (1388.5, 382.1, 122), 0, r=0.1)
    for z0 in (126, 60):
        rbox("KIT_Fridge_Handle_%d" % z0, col, 2, 3, 45, "M_Steel", (1355, 383.6, z0), 0, r=0.6)
    rbox("KIT_WashingMachine", col, 60, 60, 84, "M_Plastic_White", (1475, 343, 1), 0, r=2)
    lathe("KIT_WM_Door", col, [(0, 0), (19, 0), (20, 1), (20, 3), (16, 4.5), (0, 4.5)], "M_Steel", (1475, 373, 44), 0, seg=48)
    ob = bpy.data.objects["KIT_WM_Door"]; ob.rotation_euler = (math.radians(-90), 0, 0); ob.location.y = 3.73
    ob.location.z = 0.44
    rbox("KIT_WM_Panel", col, 56, 0.6, 10, "M_Black_Gloss", (1475, 373.1, 72), 0, r=0.3)
    # accessories
    for k, (x, h) in enumerate(((1250, 16), (1262, 20), (1274, 12))):
        lathe("KIT_Jar_%d" % k, col, [(0, 0), (4, 0), (4, h), (3, h + 1), (0, h + 1)], ("M_Ceramic_White", "M_Walnut", "M_Glass")[k], (x, 532, 90), 0, seg=24)
    rbox("KIT_Board", col, 40, 26, 2, "M_Oak_Light", (1480, 532, 90), 10, r=0.6)
    place("potted_plant_04", "KIT_Herb", col, (1570, 520, 90), 0, height=24)


def bed1():
    col = coll("02_Interior/INT_Bed1")
    F = Frame(150, 0, 0)
    bed(col, "BR1_Bed", F, 180, 200, "M_Fabric_Grey", "M_Walnut", "M_Fabric_Cream", "M_Fabric_Charcoal", ("M_Fabric_Taupe", "M_Fabric_Charcoal"))
    side_table(col, "BR1_SideTable_L", Frame(30, 22, 0))
    side_table(col, "BR1_SideTable_R", Frame(270, 22, 0))
    place("standing_picture_frame_01", "BR1_PhotoFrame", col, (262, 18, 50), 10, height=22)
    books(col, "BR1_Books", 34, 22, 50, 5, 2)
    for i, x in enumerate((30, 270)):
        it = Item("BR1_Sconce_%d" % i, col)
        it.box(x - 4, x + 4, 0.5, 3, 128, 152, "M_Brass")
        it.box(x - 1, x + 1, 3, 13, 138, 141, "M_Brass")
        it.done()
        lathe("BR1_Sconce_Shade_%d" % i, col, [(0, 0), (7, 0), (5, 18), (0, 18)], "M_Lampshade", (x, 15, 124), 0, seg=32)
    mould_frames(col, "BR1_HeadboardMoulding", ("y", 0, 1), [(6, 58, 60, 255), (66, 234, 132, 255), (242, 294, 60, 255), (300, 384, 25, 255)])
    wardrobe(col, "BR1_Wardrobe", 330, 390, 252, 390, "-x", nd=2)
    dk = Item("BR1_StudyDesk", col)
    dk.box(338, 390, 178, 248, 72, 75, "M_Walnut")
    dk.box(346, 390, 180, 246, 60, 72, "M_Walnut")
    dk.box(355, 389, 186, 240, 150, 152.5, "M_Walnut")
    ob = dk.done(); bevel(ob, 0.002, 2)
    lathe("BR1_DeskLamp", col, [(0, 0), (6, 0), (6, 1.5), (1, 2), (1, 34), (8, 34), (5, 46), (0, 46)], "M_Brass_Brushed", (376, 230, 75), 0, seg=24)
    books(col, "BR1_ShelfBooks", 372, 204, 152.5, 90, 3)
    dining_chair(col, "BR1_DeskChair", (354, 212), -90)          # tucked under the desk
    rbox("BR1_Rug", col, 250, 180, 1.2, "M_Rug_Beige", (150, 205, 0), 0, r=2)
    place("ceiling_fan", "BR1_CeilingFan", col, (195, 205, 285), 0, scale=0.85, top_anchor=True)
    curtain(col, "BR1_Curtain_Win_L", (4, 62), (4, 108), 2, 262, amp=5, seed=6)
    curtain(col, "BR1_Curtain_Win_R", (4, 252), (4, 298), 2, 262, amp=5, seed=7)
    curtain(col, "BR1_Curtain_Win_Sheer", (8, 70), (8, 290), 2, 262, amp=3, mat="M_Curtain_Sheer", rod=False, seed=8)
    curtain(col, "BR1_Curtain_Bal", (2, 306), (44, 306), 2, 262, amp=5, seed=9)
    place("potted_plant_01", "BR1_Plant_Entry", col, (512, 26, 0), 120, height=140)
    mr = Item("BR1_Mirror", col)
    mr.box(420, 500, 0, 2.5, 30, 200, "M_Walnut")
    mr.box(424, 496, 2.5, 2.8, 34, 196, "M_Mirror")
    mr.done()


def bed2():
    col = coll("02_Interior/INT_Bed2")
    F = Frame(732, 430, 90)        # headboard on the toilet wall, bed extends towards -X
    bed(col, "BR2_Bed", F, 160, 200, "M_Fabric_Beige", "M_Oak_Light", "M_Linen_White", "M_Fabric_Sage", ("M_Fabric_Sage", "M_Fabric_Taupe"))
    side_table(col, "BR2_SideTable_A", Frame(708, 326, 90), w=42, d=40, mat="M_Oak_Light")
    side_table(col, "BR2_SideTable_B", Frame(710, 530, 90), w=36, d=38, mat="M_Oak_Light")
    place("ceramic_vase_03", "BR2_Vase", col, (705, 326, 50), 0, height=24)
    for i, yy in enumerate((326, 530)):
        place("modern_ceiling_lamp_01", "BR2_Pendant_%d" % i, col, (712, yy, 285), 0, top_anchor=True)
    mould_frames(col, "BR2_HeadboardMoulding", ("x", 732, -1), [(345, 515, 132, 255)])
    wardrobe(col, "BR2_Wardrobe", 404, 536, 162, 222, "+y", nd=2, mat="M_Grey_Matte", handle="M_Brass")
    dk = Item("BR2_StudyDesk", col)
    dk.box(540, 636, 162, 212, 72, 75, "M_Oak_Light")
    dk.box(548, 628, 162, 192, 60, 72, "M_Oak_Light")
    dk.box(548, 628, 162, 192, 130, 175, "M_Oak_Light")
    dk.box(548, 628, 191.8, 192.2, 152, 153, "M_BlackMetal")
    ob = dk.done(); bevel(ob, 0.002, 2)
    books(col, "BR2_DeskBooks", 610, 178, 75, 0, 3)
    place("potted_plant_04", "BR2_DeskPlant", col, (560, 180, 75), 0, height=22)
    dining_chair(col, "BR2_DeskChair", (588, 222), 180, fabric="M_Fabric_Sage", wood="M_Oak_Light")
    rbox("BR2_Rug", col, 220, 200, 1.2, "M_Rug_Grey", (585, 430, 0), 0, r=2)
    place("ceiling_fan", "BR2_CeilingFan", col, (567, 357, 285), 0, scale=0.85, top_anchor=True)
    curtain(col, "BR2_Curtain_L", (410, 548), (454, 548), 2, 262, amp=5, mat="M_Fabric_Sage", seed=10)
    curtain(col, "BR2_Curtain_R", (640, 548), (684, 548), 2, 262, amp=5, mat="M_Fabric_Sage", seed=11)
    curtain(col, "BR2_Curtain_Sheer", (430, 544), (664, 544), 2, 262, amp=3, mat="M_Curtain_Sheer", rod=False, seed=12)
    place("potted_plant_02", "BR2_Plant", col, (422, 520, 0), 40, height=75)


def toilets():
    # ---- Toilet 1 (240 x 150): basin on the partition wall, WC on the outer wall, shower behind glass
    col = coll("02_Interior/INT_Toilet1")
    wall_hung_wc(col, "T1_WC", Frame(260, 552, 180))
    rbox("T1_FlushPlate", col, 22, 1, 14, "M_Chrome", (260, 551, 98), 0, r=0.4)
    rbox("T1_BasinLedge", col, 46, 70, 6, "M_Walnut", (173, 515, 78), 0, r=0.6)
    vessel_basin(col, "T1_Basin", (172, 515, 84), r=19, h=13)
    it = Item("T1_Tap", col)
    it.cyl(155, 515, 84, 112, 1.3, "M_Chrome", seg=16)
    it.box(155, 166, 513.8, 516.2, 109, 112, "M_Chrome")
    it.done()
    rbox("T1_Mirror", col, 1, 60, 80, "M_Mirror", (150.6, 516, 110), 0, r=0.2)
    rain_shower(col, "T1_Shower", (345, 403), (0, 1))
    rbox("T1_GlassPartition", col, 1, 82, 198, "M_Glass", (300, 511, 2), 0, r=0.2)
    it = Item("T1_Accessories", col)
    it.box(386, 390, 470, 540, 120, 122, "M_Chrome")
    it.box(330, 360, 415, 425, 0.05, 0.4, "M_Steel")
    it.done()
    cushion("T1_Towel", col, 4, 50, 58, "M_Towel", (384, 505, 64), 0, crown=0.1, cuts=4)
    # ---- Toilet 2 (150 x 240): fittings on the east wall
    col = coll("02_Interior/INT_Toilet2")
    wall_hung_wc(col, "T2_WC", Frame(894, 327, 90))
    rbox("T2_FlushPlate", col, 1, 22, 14, "M_Chrome", (893.5, 327, 98), 0, r=0.4)
    rbox("T2_BasinLedge", col, 46, 62, 6, "M_Walnut", (871, 258, 78), 0, r=0.6)
    vessel_basin(col, "T2_Basin", (869, 258, 84), r=18, h=13)
    it = Item("T2_Tap", col)
    it.cyl(890, 258, 84, 112, 1.3, "M_Chrome", seg=16)
    it.box(879, 890, 256.8, 259.2, 109, 112, "M_Chrome")
    it.done()
    rbox("T2_Mirror", col, 1, 52, 80, "M_Mirror", (893.4, 258, 110), 0, r=0.2)
    rain_shower(col, "T2_Shower", (893, 422), (-1, 0))
    rbox("T2_GlassPartition", col, 74, 1, 198, "M_Glass", (857, 388, 2), 0, r=0.2)
    it = Item("T2_Accessories", col)
    it.box(744, 748, 330, 400, 120, 122, "M_Chrome")
    it.box(840, 870, 430, 440, 0.05, 0.4, "M_Steel")
    it.done()
    cushion("T2_Towel", col, 50, 4, 58, "M_Towel", (746, 365, 64), 90, crown=0.1, cuts=4)
    # ---- wash-basin alcove off the foyer (Marquis: fluted walnut base + vessel basin)
    col = coll("02_Interior/INT_Foyer")
    vn = Item("VAN_Counter", col)
    vn.box(748, 890, 162, 205, 20, 84, "M_Walnut")
    for k in range(int(142 / 4)):
        vn.cyl(750 + k * 4, 162, 20, 82, 1.5, "M_Walnut", seg=10, caps=False)
    vn.done()
    rbox("VAN_Top", col, 146, 48, 4, "M_Quartz_White", (819, 181, 84), 0, r=0.4)
    vessel_basin(col, "VAN_Basin", (819, 184, 88), r=21, h=14)
    it = Item("VAN_Tap", col)
    it.cyl(819, 202, 88, 120, 1.4, "M_Chrome", seg=16)
    it.box(817.8, 820.2, 188, 202, 117, 120, "M_Chrome")
    it.done()
    mr = Item("VAN_Mirror", col)
    pts, pts2 = [], []
    for k in range(48):
        a = 2 * math.pi * k / 48
        pts.append((819 + 32 * math.cos(a), 203.6, 150 + 42 * math.sin(a)))
        pts2.append((819 + 34 * math.cos(a), 204.4, 150 + 44 * math.sin(a)))
    mr.face(pts, "M_Mirror")
    mr.face(pts2, "M_Brass")
    mr.done()
    it = Item("VAN_Sconce", col)
    it.box(866, 874, 202, 205, 150, 180, "M_Brass")
    it.done()
    lathe("VAN_Sconce_Shade", col, [(0, 0), (3.2, 0), (3.2, 24), (0, 24)], "M_Lampshade", (870, 198, 154), 0, seg=24)
    cushion("VAN_HandTowel", col, 30, 4, 40, "M_Towel", (884, 202, 92), 0, crown=0.1, cuts=4)


def foyer():
    col = coll("02_Interior/INT_Foyer")
    rbox("FOY_Runner", col, 230, 94, 1.2, "M_Rug_Beige", (755, 75, 0), 0, r=2)
    place("potted_plant_02", "FOY_Plant", col, (572, 28, 0), 160, height=85)
    wall_art(col, "FOY_Art", ("y", 0, 1), 760, 150, 90, 60, "M_Art_Calm")
    mould_frames(col, "FOY_Moulding", ("y", 0, 1), [(630, 890, 20, 95), (630, 890, 105, 250)])


def balconies():
    col = coll("02_Interior/INT_Balconies")
    tub_chair(col, "BAL1_Chair", (52, 490), 0, fabric="M_Leather_Cream", wood="M_Oak_Light")
    lathe("BAL1_SideTable", col, [(0, 0), (16, 0), (18, 2), (14, 44), (18, 46), (18, 48), (0, 48)], "M_Oak_Light", (116, 500, 0), 0, seg=40)
    place("potted_plant_01", "BAL1_Plant_A", col, (14, 362, 0), 200, height=120)
    place("potted_plant_02", "BAL1_Plant_B", col, (116, 538, 0), 10, height=70)
    # balcony 2 (147 deep): seating at the kitchen end, walkway kept clear in front of the slider
    tub_chair(col, "BAL2_Chair_A", (1108, 505), 25, fabric="M_Leather_Cream", wood="M_Oak_Light")
    tub_chair(col, "BAL2_Chair_B", (1180, 492), -35, fabric="M_Leather_Cream", wood="M_Oak_Light")
    lathe("BAL2_SideTable", col, [(0, 0), (16, 0), (18, 2), (14, 44), (18, 46), (18, 48), (0, 48)], "M_Oak_Light", (1150, 545, 0), 0, seg=40)
    place("potted_plant_01", "BAL2_Plant_A", col, (934, 536, 0), 0, height=140)
    place("potted_plant_02", "BAL2_Plant_B", col, (996, 545, 0), 250, height=60)


def furnish_all():
    living()
    dining()
    kitchen()
    bed1()
    bed2()
    toilets()
    foyer()
    balconies()
