"""Builds the geo-referenced exterior environment into blender/environment.blend (collection 06_Environment).

Blender -b --factory-startup -P env_build.py -- <FlatTypeG dir>

Everything is placed in the FLAT's frame (metres, the frame used by flat_typeG.blend), so the environment can be
linked next to the untouched interior:
  site frame  : E/N metres from the project pin (11.251028 N, 75.818917 E), z = metres above the plot's ground
  flat frame  : +X = bearing 220 deg, +Y = bearing 130 deg (balconies), z = 0 at the 11th-floor finished floor
Inputs come from blender/env_data (env_extract.py): terrain.npz, houses.json, trees.json, roads.json, towers.json.
"""
import bpy, bmesh, json, math, os, sys, random
import numpy as np
from mathutils import Vector

ROOT = sys.argv[sys.argv.index("--") + 1]
HERE = os.path.join(ROOT, "blender", "scripts")
DATA = os.path.join(ROOT, "blender", "env_data")
sys.path.insert(0, HERE)
import env_trees

# ------------------------------------------------------------------ frame
# Per-site values come from <ROOT>/site.json (see the flat-environment skill); the example project's numbers are the fallback.
#   ffl_m           finished floor of the flat's storey above the plot ground
#   plan_m_per_px   scale of the typical-floor plan image used for the tower footprint
#   bearing_plus_y  compass bearing of the flat's +Y axis (towards the balconies in Type G); +X = bearing_plus_y + 90
#   plan_centre_px  footprint centre on that plan (u, v pixels)
#   shift_m         footprint centre offset from the pin along bearing_plus_y - 90 (metres)
#   flat_origin_px  the flat's (0, 0) corner on that plan (u, v pixels)
_SITE = json.load(open(os.path.join(ROOT, "site.json"))).get("env_build", {}) if os.path.exists(os.path.join(ROOT, "site.json")) else {}
FFL = float(_SITE.get("ffl_m", 34.8))
PX = float(_SITE.get("plan_m_per_px", 0.0341))
_BY = float(_SITE.get("bearing_plus_y", 130.0))
B130 = math.radians(_BY)            # name kept from Type G: bearing of +Y
B40 = math.radians(_BY - 90.0)      # plan "up" in Type G; +X points the opposite way (bearing_plus_y + 90)
D130 = (math.sin(B130), math.cos(B130))
D40 = (math.sin(B40), math.cos(B40))
D220 = (-D40[0], -D40[1])
PLAN_C = tuple(_SITE.get("plan_centre_px", (1170.0, 712.0)))
SHIFT40 = float(_SITE.get("shift_m", 10.0))
_FO = tuple(_SITE.get("flat_origin_px", (1071.0, 137.0)))


def page_to_site(u, v):
    a130 = (u - PLAN_C[0]) * PX
    a40 = (PLAN_C[1] - v) * PX + SHIFT40
    return a130 * D130[0] + a40 * D40[0], a130 * D130[1] + a40 * D40[1]


TE, TN = page_to_site(*_FO)      # flat origin (inner face of the flat's corner walls)


def to_flat(E, N, z=0.0):
    dE, dN = E - TE, N - TN
    return (dE * D220[0] + dN * D220[1], dE * D130[0] + dN * D130[1], z - FFL)


def page_to_flat(u, v, z=0.0):
    return ((v - _FO[1]) * PX, (u - _FO[0]) * PX, z - FFL)


def flat_dir(bearing_deg):
    """unit vector in flat XY for a compass bearing"""
    b = math.radians(bearing_deg)
    e, n = math.sin(b), math.cos(b)
    return Vector((e * D220[0] + n * D220[1], e * D130[0] + n * D130[1], 0))



# ------------------------------------------------------------------ terrain sampling
T = np.load(os.path.join(DATA, "terrain.npz"))
NEAR, NSTEP = T["near"], float(T["near_step"])
FAR, FSTEP = T["far"], float(T["far_step"])
CN, CF = T["cover_near"], T["cover_far"]


def _bilin(a, step, E, N):
    n = a.shape[0]
    fj = E / step + (n - 1) / 2
    fi = (n - 1) / 2 - N / step
    j0 = min(max(int(math.floor(fj)), 0), n - 2)
    i0 = min(max(int(math.floor(fi)), 0), n - 2)
    tj = min(max(fj - j0, 0), 1)
    ti = min(max(fi - i0, 0), 1)
    return (a[i0, j0] * (1 - tj) * (1 - ti) + a[i0, j0 + 1] * tj * (1 - ti) + a[i0 + 1, j0] * (1 - tj) * ti + a[i0 + 1, j0 + 1] * tj * ti)


PLOT_R = 48.0
PLOT_C = page_to_site(*PLAN_C)


def ground(E, N):
    half = NSTEP * (NEAR.shape[0] - 1) / 2
    if abs(E) < half - NSTEP and abs(N) < half - NSTEP:
        h = float(_bilin(NEAR, NSTEP, E, N))
    else:
        h = float(_bilin(FAR, FSTEP, E, N))
    # the plot is levelled for construction: blend to 0 around the footprint centre
    d = math.hypot(E - PLOT_C[0], N - PLOT_C[1])
    if d < PLOT_R + 40:
        w = min(1, max(0, (d - PLOT_R) / 40))
        w = w * w * (3 - 2 * w)
        h = h * w
    return h


def cover(E, N):
    half = 1000
    if abs(E) < half and abs(N) < half:
        a, step = CN, 10.0
    else:
        a, step = CF, 90.0
    n = a.shape[0]
    j = int(round(E / step + (n - 1) / 2))
    i = int(round((n - 1) / 2 - N / step))
    if 0 <= i < n and 0 <= j < n:
        return a[i, j]
    return (0.6, 0.05)


# ------------------------------------------------------------------ scene helpers
def coll(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or bpy.context.scene.collection
    if c.name not in [x.name for x in p.children]:
        p.children.link(c)
    return c


def mat(name, rgb, rough=0.8, metal=0.0, spec=0.5, vcol=False):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    try:
        b.inputs["Specular IOR Level"].default_value = spec
    except KeyError:
        pass
    if vcol:
        ca = m.node_tree.nodes.new("ShaderNodeVertexColor")
        ca.layer_name = "Col"
        mul = m.node_tree.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        mul.inputs["A"].default_value = (*rgb, 1)
        m.node_tree.links.new(ca.outputs["Color"], mul.inputs["B"])
        m.node_tree.links.new(mul.outputs["Result"], b.inputs["Base Color"])
    m.diffuse_color = (*rgb, 1)
    return m


WALL_PALETTE = [(0.70, 0.69, 0.65), (0.66, 0.59, 0.45), (0.68, 0.61, 0.38), (0.66, 0.50, 0.39),
                (0.47, 0.56, 0.61), (0.50, 0.60, 0.50), (0.52, 0.52, 0.50), (0.64, 0.50, 0.50)]


def materials():
    M = {}
    for i, c in enumerate(WALL_PALETTE):
        M["wall%d" % i] = mat("M_Env_HouseWall_%d" % i, c, 0.92, vcol=True)
    M["roof_concrete"] = mat("M_Env_RoofConcrete", (0.36, 0.35, 0.32), 0.95, vcol=True)
    M["roof_tile"] = mat("M_Env_RoofTile", (0.27, 0.105, 0.06), 0.85, vcol=True)
    M["roof_sheet"] = mat("M_Env_RoofSheet", (0.17, 0.26, 0.42), 0.45, 0.3, vcol=True)
    M["window"] = mat("M_Env_Window", (0.025, 0.03, 0.035), 0.15, 0.0, 0.6)
    M["frame"] = mat("M_Env_WindowFrame", (0.35, 0.33, 0.30), 0.5, 0.0)
    M["tank"] = mat("M_Env_WaterTank", (0.02, 0.02, 0.02), 0.5)
    M["road"] = mat("M_Env_Asphalt", (0.075, 0.075, 0.072), 0.85)
    M["lane"] = mat("M_Env_Laterite", (0.33, 0.16, 0.085), 0.95)
    M["terrain"] = mat("M_Env_Terrain", (1, 1, 1), 0.95, vcol=True)
    M["cwall"] = mat("M_Env_CompoundWall", (0.55, 0.53, 0.48), 0.95, vcol=True)
    M["pole"] = mat("M_Env_ConcretePole", (0.48, 0.47, 0.44), 0.9)
    M["wire"] = mat("M_Env_Wire", (0.02, 0.02, 0.02), 0.6)
    # towers
    M["t_white"] = mat("M_Env_TowerWhite", (0.74, 0.73, 0.69), 0.75)
    M["t_cream"] = mat("M_Env_TowerCream", (0.70, 0.63, 0.50), 0.8)
    M["t_grey"] = mat("M_Env_TowerGrey", (0.50, 0.50, 0.49), 0.8)
    M["t_glass"] = mat("M_Env_TowerGlass", (0.035, 0.05, 0.06), 0.06, 0.0, 0.8)
    M["t_rail"] = mat("M_Env_RailGlass", (0.10, 0.13, 0.14), 0.05, 0.0, 0.8)
    M["own_wall"] = mat("M_Env_OwnFacadeWhite", (0.76, 0.75, 0.71), 0.7)
    M["own_beige"] = mat("M_Env_OwnFacadeBeige", (0.64, 0.57, 0.46), 0.75)
    M["own_glass"] = mat("M_Env_OwnGlass", (0.04, 0.05, 0.055), 0.05, 0.0, 0.8)
    M["paving"] = mat("M_Env_Paving", (0.42, 0.41, 0.38), 0.85)
    M["lawn"] = mat("M_Env_Lawn", (0.09, 0.15, 0.04), 0.9)
    M["stone"] = mat("M_Env_StoneCladding", (0.46, 0.42, 0.36), 0.9)
    return M


class Acc:
    """accumulates quads per material and emits one mesh object"""
    def __init__(self, name, col, M):
        self.name, self.col, self.M = name, col, M
        self.v, self.f, self.mi, self.c = [], [], [], []
        self.mats = []

    def _m(self, key):
        if key not in self.mats:
            self.mats.append(key)
        return self.mats.index(key)

    def quad(self, pts, key, col=(1, 1, 1), up=False, out=None):
        """up: flip so the face normal points +Z; out: flip so the normal points along vector `out`"""
        if up or out is not None:
            a, b, c = Vector(pts[0]), Vector(pts[1]), Vector(pts[2])
            nrm = (b - a).cross(c - a)
            ref = Vector((0, 0, 1)) if up else out
            if nrm.dot(ref) < 0:
                pts = list(pts)[::-1]
        o = len(self.v)
        self.v += [tuple(p) for p in pts]
        self.f.append(tuple(range(o, o + len(pts))))
        self.mi.append(self._m(key))
        self.c.append(col)

    def box(self, c, ax, ay, hx, hy, z0, z1, key, col=(1, 1, 1), top=True, bottom=False):
        """oriented box: centre c (x,y), unit axes ax, ay (flat XY), half sizes hx, hy, z0..z1"""
        P = [Vector((c[0], c[1], 0)) + ax * sx * hx + ay * sy * hy for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        lo = [Vector((p.x, p.y, z0)) for p in P]
        hi = [Vector((p.x, p.y, z1)) for p in P]
        for i in range(4):
            j = (i + 1) % 4
            self.quad([lo[i], lo[j], hi[j], hi[i]], key, col)
        if top:
            self.quad(hi, key, col)
        if bottom:
            self.quad(lo[::-1], key, col)

    def emit(self):
        if not self.f:
            return None
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.v, [], self.f)
        for k in self.mats:
            me.materials.append(self.M[k])
        for p, i in zip(me.polygons, self.mi):
            p.material_index = i
        ca = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        for p, col in zip(me.polygons, self.c):
            for li in p.loop_indices:
                ca.data[li].color = (*col, 1)
        me.validate()
        ob = bpy.data.objects.new(self.name, me)
        self.col.objects.link(ob)
        return ob


def site_axes(ang_deg):
    """unit axes in flat XY for a site-frame angle (deg anticlockwise from East)"""
    a = math.radians(ang_deg)
    e, n = math.cos(a), math.sin(a)
    ax = Vector((e * D220[0] + n * D220[1], e * D130[0] + n * D130[1], 0))
    ay = Vector((-ax.y, ax.x, 0))
    return ax, ay


# ------------------------------------------------------------------ terrain
def build_terrain(col, M):
    rng = random.Random(1)
    objs = []
    for name, half, step, hole in (("ENV_Terrain_Near", 1000, 10.0, 0), ("ENV_Terrain_Far", 3600, 90.0, 990)):
        n = int(2 * half / step) + 1
        verts, cols = [], []
        for i in range(n):
            for j in range(n):
                E = (j - (n - 1) / 2) * step
                N = ((n - 1) / 2 - i) * step
                h = ground(E, N) - (0.6 if hole else 0.0)
                verts.append(to_flat(E, N, h))
                v, s = cover(E, N)
                # under canopy: dark leaf litter/grass; open: laterite red-brown soil or dry grass
                # under canopy: shaded leaf litter / weeds with laterite showing; open: red soil or dry grass
                soil = min(1, s * 2.5) * (1 - min(1, v * 1.6))      # bare soil only in open ground
                # post-monsoon: mostly weeds/grass under the palms, with patches of brown litter
                litter = np.array([0.040, 0.062, 0.020]) * (1 - 0.3 * rng.random()) + np.array([0.06, 0.035, 0.018]) * 0.35 * rng.random()
                g = litter * v + np.array([0.26, 0.13, 0.075]) * soil * (1 - v) + np.array([0.14, 0.13, 0.065]) * (1 - v) * (1 - soil)
                g *= rng.uniform(0.8, 1.15)
                cols.append(tuple(g))
        faces = []
        for i in range(n - 1):
            for j in range(n - 1):
                if hole:
                    E = (j + 0.5 - (n - 1) / 2) * step
                    N = ((n - 1) / 2 - i - 0.5) * step
                    if abs(E) < hole - step and abs(N) < hole - step:
                        continue
                a = i * n + j
                faces.append((a, a + n, a + n + 1, a + 1))
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.materials.append(M["terrain"])
        ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        for k, c in enumerate(cols):
            ca.data[k].color = (*c, 1)
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(name, me)
        col.objects.link(ob)
        objs.append(ob)
    # horizon apron to 25 km (flat coastal plain / sea-level horizon)
    bm = bmesh.new()
    rin, rout, seg = 3500, 25000, 96
    z = float(np.median(FAR[[0, -1], :])) - 1.0
    ring_i = [bm.verts.new(to_flat(rin * math.cos(t), rin * math.sin(t), z)) for t in (2 * math.pi * k / seg for k in range(seg))]
    ring_o = [bm.verts.new(to_flat(rout * math.cos(t), rout * math.sin(t), z - 20)) for t in (2 * math.pi * k / seg for k in range(seg))]
    for k in range(seg):
        bm.faces.new((ring_i[k], ring_o[k], ring_o[(k + 1) % seg], ring_i[(k + 1) % seg]))
    me = bpy.data.meshes.new("ENV_Horizon")
    bm.to_mesh(me)
    me.materials.append(M["terrain"])
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for d in ca.data:
        d.color = (0.075, 0.10, 0.04, 1)
    ob = bpy.data.objects.new("ENV_Horizon", me)
    col.objects.link(ob)
    return objs


# ------------------------------------------------------------------ houses
def hrand(h, salt):
    return random.Random(hash((round(h["E"], 1), round(h["N"], 1), salt)) & 0xffffffff)


def build_houses(col, M, houses):
    accs = {}
    eye = Vector((0, 0, 0))
    for h in houses:
        R = hrand(h, 1)
        E, N = h["E"], h["N"]
        dist = math.hypot(E - TE, N - TN)
        tile = (int((E + 4000) // 600), int((N + 4000) // 600))
        acc = accs.get(tile)
        if acc is None:
            acc = accs[tile] = Acc("ENV_Houses_%d_%d" % tile, col, M)
        area = h["w"] * h["d"]
        if area < 70:
            floors = R.choice((1, 1, 2))
        elif area < 180:
            floors = R.choice((1, 2, 2, 2, 3))
        elif area < 450:
            floors = R.choice((2, 3, 3, 4))
        else:
            floors = R.choice((3, 4, 5, 6))
        fh = 3.15
        g = ground(E, N)
        z0 = g - 1.0 - FFL
        z1 = g + 0.45 + floors * fh - FFL
        c = to_flat(E, N)
        ax, ay = site_axes(math.degrees(h["ang"]))
        hx, hy = h["w"] / 2 * 0.92, h["d"] / 2 * 0.92            # roof outline is wider than the walls (eaves)
        wall = "wall%d" % R.randrange(len(WALL_PALETTE))
        dirt = R.uniform(0.75, 1.05)
        acc.box(c, ax, ay, hx, hy, z0, z1, wall, col=(dirt, dirt, dirt * 0.97), top=(h["roof"] != "tile"))
        # windows (near field only): dark panes on each face, per floor
        if dist < 450:
            for f in range(floors):
                zc = g + 0.45 + f * fh + 1.55 - FFL
                for axis, half_len, half_other, nrm in ((ax, hx, hy, ay), (ax, hx, hy, -ay), (ay, hy, hx, ax), (ay, hy, hx, -ax)):
                    nw = max(1, int(half_len * 2 / 3.2))
                    for k in range(nw):
                        if R.random() < 0.25:
                            continue
                        t = (k + 0.5) / nw * 2 - 1
                        p = Vector((c[0], c[1], 0)) + axis * t * half_len * 0.8 + nrm * (half_other + 0.03)
                        a = axis * 0.6
                        acc.quad([p - a + Vector((0, 0, zc - 0.65)), p + a + Vector((0, 0, zc - 0.65)),
                                  p + a + Vector((0, 0, zc + 0.6)), p - a + Vector((0, 0, zc + 0.6))], "window", out=nrm)
                # sunshade (chajja) over the windows: thin slab band projecting 0.5 m
                zz = g + 0.45 + f * fh + 2.35 - FFL
                acc.box(c, ax, ay, hx + 0.5, hy + 0.5, zz, zz + 0.1, wall, col=(dirt * 0.9,) * 3, bottom=True)
        if h["roof"] == "tile":
            # hip roof
            rh = min(hx, hy) * 0.55
            P = [Vector((c[0], c[1], 0)) + ax * sx * (hx + 0.6) + ay * sy * (hy + 0.6) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            lo = [Vector((p.x, p.y, z1)) for p in P]
            ridge = max(0.0, hx - hy) if hx > hy else max(0.0, hy - hx)
            if hx >= hy:
                r1 = Vector((c[0], c[1], z1 + rh)) - ax * ridge
                r2 = Vector((c[0], c[1], z1 + rh)) + ax * ridge
                acc.quad([lo[0], lo[1], r2, r1], "roof_tile", (dirt,) * 3, up=True)
                acc.quad([lo[2], lo[3], r1, r2], "roof_tile", (dirt * 0.9,) * 3, up=True)
                acc.quad([lo[1], lo[2], r2], "roof_tile", (dirt * 0.95,) * 3, up=True)
                acc.quad([lo[3], lo[0], r1], "roof_tile", (dirt,) * 3, up=True)
            else:
                r1 = Vector((c[0], c[1], z1 + rh)) - ay * ridge
                r2 = Vector((c[0], c[1], z1 + rh)) + ay * ridge
                acc.quad([lo[1], lo[2], r2, r1], "roof_tile", (dirt,) * 3, up=True)
                acc.quad([lo[3], lo[0], r1, r2], "roof_tile", (dirt * 0.9,) * 3, up=True)
                acc.quad([lo[2], lo[3], r2], "roof_tile", (dirt * 0.95,) * 3, up=True)
                acc.quad([lo[0], lo[1], r1], "roof_tile", (dirt,) * 3, up=True)
        elif h["roof"] == "sheet":
            acc.box(c, ax, ay, hx + 0.4, hy + 0.4, z1 + 0.6, z1 + 0.75, "roof_sheet", (dirt,) * 3, bottom=True)
        else:
            # flat roof: parapet, stained concrete, black water tank, sometimes a stair cabin / truss shed
            acc.box(c, ax, ay, hx * 0.98, hy * 0.98, z1, z1 + 0.02, "roof_concrete", (dirt * R.uniform(0.8, 1.1),) * 3)
            for (sx, sy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cc = (c[0] + (ax.x * sx * hx + ay.x * sy * hy), c[1] + (ax.y * sx * hx + ay.y * sy * hy))
                if sx:
                    acc.box(cc, ax, ay, 0.1, hy, z1, z1 + 0.9, wall, (dirt * 0.95,) * 3)
                else:
                    acc.box(cc, ax, ay, hx, 0.1, z1, z1 + 0.9, wall, (dirt * 0.95,) * 3)
            if R.random() < 0.8:
                tc = (c[0] + ax.x * hx * 0.5 + ay.x * hy * 0.4, c[1] + ax.y * hx * 0.5 + ay.y * hy * 0.4)
                acc.box(tc, ax, ay, 0.6, 0.6, z1 + 1.2, z1 + 2.5, "tank")
                acc.box(tc, ax, ay, 0.8, 0.8, z1, z1 + 1.2, wall, (dirt * 0.9,) * 3)
            if R.random() < 0.35:
                sc_ = (c[0] - ax.x * hx * 0.45, c[1] - ax.y * hx * 0.45)
                acc.box(sc_, ax, ay, min(1.6, hx * 0.3), min(1.6, hy * 0.3), z1, z1 + 2.6, wall, (dirt,) * 3)
            if R.random() < 0.2:      # GI truss roof over the terrace, very common in Kozhikode
                acc.box(c, ax, ay, hx * 0.95, hy * 0.95, z1 + 3.0, z1 + 3.1, "roof_sheet", (dirt,) * 3, bottom=True)
    for a in accs.values():
        a.emit()
    return len(houses)


# ------------------------------------------------------------------ towers (known high-rises)
STYLE = {"res_white": ("t_white", "t_glass"), "res_cream": ("t_cream", "t_glass"), "res_grey": ("t_grey", "t_glass"),
         "res_low": ("t_cream", "t_glass"), "mall": ("t_grey", "t_glass"), "office_glass": ("t_glass", "t_grey")}


def facade_box(acc, c, ax, ay, hx, hy, zb, h, floors, wallk, glassk, slab_k=None, bay=3.6, pier=1.1):
    """per-floor: slab band + piers + recessed glazing on all four faces"""
    fh = h / max(1, floors)
    slab_k = slab_k or wallk
    for f in range(floors):
        z0 = zb + f * fh
        acc.box(c, ax, ay, hx + 0.15, hy + 0.15, z0, z0 + 0.3, slab_k, bottom=(f == 0))
        acc.box(c, ax, ay, hx - 0.25, hy - 0.25, z0 + 0.3, z0 + fh, glassk, top=False)
        for axis, hl, ho, nrm in ((ax, hx, hy, ay), (ay, hy, hx, -ax)):
            n = max(1, int(2 * hl / bay))
            for k in range(n + 1):
                t = -1 + 2 * k / n
                for s in (-1, 1):
                    pc = Vector((c[0], c[1], 0)) + axis * t * (hl - pier / 2) + nrm * s * (ho - 0.15)
                    acc.box((pc.x, pc.y), axis, nrm, pier / 2, 0.15, z0 + 0.3, z0 + fh, wallk, top=False)
    acc.box(c, ax, ay, hx + 0.15, hy + 0.15, zb + h, zb + h + 1.2, slab_k)            # parapet / roof
    acc.box(c, ax, ay, min(hx, 6), min(hy, 5), zb + h + 1.2, zb + h + 5.0, wallk)      # lift machine room


def build_towers(col, M, towers):
    acc = Acc("ENV_Towers", col, M)
    for t in towers:
        g = ground(t["E"], t["N"])
        c = to_flat(t["E"], t["N"])
        ax, ay = site_axes(t["ang"])
        wk, gk = STYLE.get(t["style"], ("t_white", "t_glass"))
        zb = g - 1.5 - FFL
        if t.get("round"):
            r = t["w"] / 2
            seg = 24
            for k in range(seg):
                a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
                p0 = Vector((c[0], c[1], 0)) + (ax * math.cos(a0) + ay * math.sin(a0)) * r
                p1 = Vector((c[0], c[1], 0)) + (ax * math.cos(a1) + ay * math.sin(a1)) * r
                acc.quad([p0 + Vector((0, 0, zb)), p1 + Vector((0, 0, zb)), p1 + Vector((0, 0, zb + t["h"])), p0 + Vector((0, 0, zb + t["h"]))], gk, out=(p0 + p1) / 2 - Vector((c[0], c[1], 0)))
                acc.quad([Vector((c[0], c[1], zb + t["h"])), p0 + Vector((0, 0, zb + t["h"])), p1 + Vector((0, 0, zb + t["h"]))], wk, up=True)
            continue
        facade_box(acc, c, ax, ay, t["w"] / 2, t["d"] / 2, zb + 1.5, t["h"], t["floors"], wk, gk,
                   bay=4.5 if t["style"] != "office_glass" else 9.0, pier=1.4 if t["style"] != "office_glass" else 0.5)
    acc.emit()


# ------------------------------------------------------------------ own tower (rest of the typical floor plate)
# plan rectangles (page px, y down) of the typical floor, from the 14th-17th floor plan; G handled separately
PLATE = [
    ("F",    805, 105, 1065, 460),
    ("core", 1000, 460, 1065, 985),
    ("coreE", 1065, 640, 1345, 985),
    ("H",    655, 490, 1000, 1090),
    ("A",    1345, 640, 1640, 985),
    ("BC",   955, 985, 1650, 1320),
]
G_BLOCK = (1065, 131, 1239, 609)
LEVELS = [(-0.6, 0.6, "plinth")] + [(0.6, 3.6, "ground"), (4.2, 3.6, "first")] + [(7.8 + 3.0 * k, 3.0, "typ%d" % (k + 2)) for k in range(16)]
ROOF_Z = 7.8 + 3.0 * 16


def gface(acc, zf):
    """Type G openings for the floors above/below the modelled flat (flat-frame metres, taken from layout.py):
    balcony 1 (x -0.2..1.38) and balcony 2 (x 9.06..12.17) open on the +Y face (y = 5.72), bedroom 1 window on -X."""
    Y = 5.74
    for x0, x1 in ((-0.2, 1.38), (9.06, 12.17)):
        acc.quad([(x0, Y, zf + 0.15), (x1, Y, zf + 0.15), (x1, Y, zf + 2.85), (x0, Y, zf + 2.85)], "own_glass", out=Vector((0, 1, 0)))
        acc.quad([(x0, Y + 0.04, zf + 0.15), (x1, Y + 0.04, zf + 0.15), (x1, Y + 0.04, zf + 1.1), (x0, Y + 0.04, zf + 1.1)], "t_rail", out=Vector((0, 1, 0)))
    for x0, x1 in ((3.2, 5.3), (13.4, 14.5)):       # bedroom 2 / kitchen windows on the +Y face
        acc.quad([(x0, Y, zf + 0.9), (x1, Y, zf + 0.9), (x1, Y, zf + 2.25), (x0, Y, zf + 2.25)], "own_glass", out=Vector((0, 1, 0)))
    X = -0.22
    acc.quad([(X, 0.95, zf + 0.9), (X, 2.95, zf + 0.9), (X, 2.95, zf + 2.25), (X, 0.95, zf + 2.25)], "own_glass", out=Vector((-1, 0, 0)))


def build_own_tower(col, M):
    """Own tower from the traced floor plate of the 4th-13th floor plan (env_floorplate.py -> own_floorplate.json).
    Every level is the traced outline extruded; on the 11th floor the outline excludes Type G and the common passage
    (the interior model contains both), and on every other floor Type G is a closed volume with the flat's openings."""
    from mathutils.geometry import tessellate_polygon
    FP = json.load(open(os.path.join(DATA, "own_floorplate.json")))
    typical = [p for p in FP["typical"] if len(p) > 3]
    floor11 = [p for p in FP["floor11"] if len(p) > 3]
    acc = Acc("ENV_OwnTower", col, M)

    def ccw(poly):
        a = sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly)))
        return poly if a > 0 else poly[::-1]

    typical = [ccw(p) for p in typical]
    floor11 = [ccw(p) for p in floor11]

    def cap(poly, z, up=True):
        tris = tessellate_polygon([[Vector((x, y, z)) for x, y in poly]])
        for t in tris:
            pts = [Vector((poly[k][0], poly[k][1], z)) for k in t]
            acc.quad(pts, "own_wall", up=up, out=None if up else Vector((0, 0, -1)))

    def offset(poly, d):
        """mitred outward offset of a CCW outline (miter clamped at 3x)"""
        n = len(poly)
        out = []
        for k in range(n):
            p0, p1, p2 = Vector((*poly[k - 1], 0)), Vector((*poly[k], 0)), Vector((*poly[(k + 1) % n], 0))
            e0, e1 = (p1 - p0), (p2 - p1)
            n0 = Vector((e0.y, -e0.x, 0)).normalized() if e0.length > 1e-6 else Vector((0, 0, 0))
            n1 = Vector((e1.y, -e1.x, 0)).normalized() if e1.length > 1e-6 else n0
            m = (n0 + n1)
            if m.length < 1e-6:
                m = n1
            m.normalize()
            c = max(0.34, m.dot(n1))
            out.append(p1 + m * (d / c))
        return out

    def storey(poly, zf, fh, tag, R):
        n = len(poly)
        band = offset(poly, 0.12)
        for k in range(n):
            q0, q1 = band[k], band[(k + 1) % n]
            if (q1 - q0).length > 1e-3:
                ob = Vector(((q1 - q0).y, -(q1 - q0).x, 0)).normalized()
                acc.quad([q0 + Vector((0, 0, zf - 0.15)), q1 + Vector((0, 0, zf - 0.15)), q1 + Vector((0, 0, zf + 0.15)), q0 + Vector((0, 0, zf + 0.15))], "own_wall", out=ob)
        for k in range(n):
            a, b = Vector((*poly[k], 0)), Vector((*poly[(k + 1) % n], 0))
            e = b - a
            L = e.length
            if L < 1e-3:
                continue
            t = e / L
            o = Vector((t.y, -t.x, 0))                        # outward for a CCW outline
            Z = lambda z: Vector((0, 0, z))
            # slab edge band (projects 12 cm) and the wall
            acc.quad([a + Z(zf + 0.15), b + Z(zf + 0.15), b + Z(zf + fh - 0.15), a + Z(zf + fh - 0.15)],
                     "own_beige" if tag == "ground" else "own_wall", out=o)
            if tag in ("ground", "plinth") or L < 1.6:
                continue
            nwin = max(1, int(L / 3.4))
            balcony = R.random() < 0.2 and L > 2.6
            for w in range(nwin):
                c = a + t * (L * (w + 0.5) / nwin) + o * 0.02
                hw = min(0.75, L / nwin * 0.35) if not balcony else min(1.4, L / nwin * 0.45)
                h0, h1 = (0.9, 2.25) if not balcony else (0.15, 2.5)
                acc.quad([c - t * hw + Z(zf + h0), c + t * hw + Z(zf + h0), c + t * hw + Z(zf + h1), c - t * hw + Z(zf + h1)], "own_glass", out=o)
                if balcony:
                    r = c + o * 0.06
                    acc.quad([r - t * hw + Z(zf + 0.15), r + t * hw + Z(zf + 0.15), r + t * hw + Z(zf + 1.1), r - t * hw + Z(zf + 1.1)], "t_rail", out=o)
                else:
                    sh = c + o * 0.3
                    acc.box((sh.x, sh.y), t, o, hw + 0.2, 0.3, zf + 2.35, zf + 2.43, "own_wall", bottom=True)

    gx0, gy0 = FP["g_block"][0]
    gx1, gy1 = FP["g_block"][2]
    gc = ((gx0 + gx1) / 2, (gy0 + gy1) / 2)
    ghx, ghy = abs(gx1 - gx0) / 2, abs(gy1 - gy0) / 2
    AX, AY = Vector((1, 0, 0)), Vector((0, 1, 0))
    for (z0, fh, tag) in LEVELS:
        zf = z0 - FFL
        floor_no = int(tag[3:]) if tag.startswith("typ") else None
        R = random.Random(17)                          # same balcony bays on every floor
        if tag == "plinth":
            for p in typical:
                storey(p, zf - 0.4, fh + 0.4, "plinth", R)
            continue
        if floor_no is None:                           # ground (parking) and 1st (lobby, gym): full outline
            for p in typical:
                storey(p, zf, fh, tag, R)
            continue
        for p in floor11:
            storey(p, zf, fh, tag, R)
        if floor_no != 11:
            acc.box(gc, AX, AY, ghx + 0.12, ghy + 0.12, zf + (0.01 if floor_no == 12 else -0.15), zf + 0.15, "own_wall", bottom=True)
            acc.box(gc, AX, AY, ghx, ghy, zf + 0.15, zf + fh - 0.16, "own_wall", top=False)
            gface(acc, zf)
    top = ROOF_Z - FFL
    R = random.Random(3)
    for p in typical:
        storey(p, top, 1.2, "plinth", R)               # parapet
        cap(p, top + 0.02)
        cap(p, LEVELS[0][0] - FFL - 0.4, up=False)
    # lift / stair machine room over the core (plan: lifts and stairs around page (1160, 860))
    cx, cy = (860 - 155) * 0.0361, (1160 - 1083) * 0.0361
    acc.box((cx, cy), AX, AY, 6.0, 4.5, top, top + 4.0, "own_wall")
    acc.emit()
    # own plot: paving + lawn + stone boundary wall around the tower with a ~9 m margin
    xs = [x for p in typical for x, y in p]
    ys = [y for p in typical for x, y in p]
    pc = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    hx, hy = (max(xs) - min(xs)) / 2 + 9, (max(ys) - min(ys)) / 2 + 9
    pl = Acc("ENV_OwnPlot", col, M)
    pl.box(pc, AX, AY, hx, hy, -FFL - 0.5, -FFL + 0.02, "paving")
    for (ox, oy) in ((1, 0), (-1, 0), (0, 1)):
        cc = (pc[0] + ox * (hx - 3), pc[1] + oy * (hy - 3))
        pl.box(cc, AX, AY, 3 if ox else hx - 6, 3 if oy else hy - 6, -FFL, -FFL + 0.06, "lawn")
    for (sx, sy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cc = (pc[0] + sx * hx, pc[1] + sy * hy)
        bx, by = (0.12, hy) if sx else (hx, 0.12)
        pl.box(cc, AX, AY, bx, by, -FFL - 0.5, -FFL + 2.0, "stone")
    pl.emit()
    return (pc, hx, hy)


# ------------------------------------------------------------------ roads, compound walls, poles + wires
def polyline_ribbon(acc, pts, width, key, lift=0.12):
    for (e0, n0), (e1, n1) in zip(pts, pts[1:]):
        L = math.hypot(e1 - e0, n1 - n0)
        if L < 0.5:
            continue
        nseg = max(1, int(L / 8))
        for s in range(nseg):
            t0, t1 = s / nseg, (s + 1) / nseg
            a = (e0 + (e1 - e0) * t0, n0 + (n1 - n0) * t0)
            b = (e0 + (e1 - e0) * t1, n0 + (n1 - n0) * t1)
            de, dn = (n1 - n0) / L * width / 2, -(e1 - e0) / L * width / 2
            q = [to_flat(a[0] + de, a[1] + dn, ground(*a) + lift), to_flat(b[0] + de, b[1] + dn, ground(*b) + lift),
                 to_flat(b[0] - de, b[1] - dn, ground(*b) + lift), to_flat(a[0] - de, a[1] - dn, ground(*a) + lift)]
            acc.quad(q, key, up=True)


def build_roads(col, M, roads):
    acc = Acc("ENV_Roads", col, M)
    walls = Acc("ENV_CompoundWalls", col, M)
    poles = Acc("ENV_Poles", col, M)
    wires = []
    rng = random.Random(5)
    for r in roads:
        pts = r["pts"]
        key = "road" if r["kind"] in ("trunk", "primary", "secondary", "tertiary") else "lane"
        if r["kind"] in ("unclassified", "residential") and rng.random() < 0.6:
            key = "road"           # many panchayat roads are tarred
        polyline_ribbon(acc, pts, r["width"], key)
        near = min(math.hypot(e - TE, n - TN) for e, n in pts) < 450
        if not near or r["kind"] == "trunk":
            continue
        # compound walls both sides (with gaps for gates) and a pole line on one side every ~35 m
        prev_pole = None
        acc_len = 0.0
        for (e0, n0), (e1, n1) in zip(pts, pts[1:]):
            L = math.hypot(e1 - e0, n1 - n0)
            if L < 0.5:
                continue
            ue, un = (e1 - e0) / L, (n1 - n0) / L
            ne, nn = un, -ue
            s = 0.0
            while s < L:
                e, n = e0 + ue * s, n0 + un * s
                for side in (-1, 1):
                    if rng.random() < 0.72:
                        off = r["width"] / 2 + 0.6
                        we, wn = e + ne * side * off, n + nn * side * off
                        g = ground(we, wn)
                        cc = to_flat(we, wn)
                        ax = Vector(to_flat(we + ue, wn + un)) - Vector(cc)
                        ax.z = 0
                        ax.normalize()
                        ay = Vector((-ax.y, ax.x, 0))
                        walls.box(cc[:2], ax, ay, 2.1, 0.1, g - 0.5 - FFL, g + 1.6 - FFL, "cwall",
                                  col=(rng.uniform(0.7, 1.05),) * 3)
                acc_len += 4.2
                if acc_len >= 35:
                    acc_len = 0
                    off = r["width"] / 2 + 0.3
                    pe, pn = e + ne * off, n + nn * off
                    g = ground(pe, pn)
                    base = Vector(to_flat(pe, pn, g))
                    poles.box((base.x, base.y), Vector((1, 0, 0)), Vector((0, 1, 0)), 0.11, 0.11, base.z - 0.5, base.z + 9.0, "pole", top=True)
                    arm = Vector(to_flat(pe + ne * 0.9, pn + nn * 0.9, g)) - base
                    arm.z = 0
                    arm.normalize()
                    side_ax = Vector((-arm.y, arm.x, 0))
                    poles.box((base.x, base.y), arm, side_ax, 0.9, 0.06, base.z + 8.3, base.z + 8.45, "pole")
                    tops = [base + arm * o + Vector((0, 0, 8.5)) for o in (-0.75, 0.0, 0.75)] + [base + Vector((0, 0, 6.8))]
                    if prev_pole is not None and (base - prev_pole[0]).length < 60:
                        for a, b in zip(prev_pole[1], tops):
                            wires.append((a, b))
                    prev_pole = (base, tops)
                s += 4.2
    acc.emit()
    walls.emit()
    poles.emit()
    # wires: catenaries as thin square tubes
    w = Acc("ENV_Wires", col, M)
    for a, b in wires:
        n = 10
        prev = None
        L = (b - a).length
        for k in range(n + 1):
            t = k / n
            p = a.lerp(b, t) - Vector((0, 0, 4 * 0.025 * L * t * (1 - t)))
            if prev is not None:
                d = (p - prev).normalized()
                s = d.cross(Vector((0, 0, 1))).normalized() * 0.012
                u = Vector((0, 0, 0.012))
                w.quad([prev - s, p - s, p + s, prev + s], "wire")
                w.quad([prev - u, prev + u, p + u, p - u], "wire")
            prev = p
    w.emit()
    return len(wires)


# ------------------------------------------------------------------ vegetation
def build_trees(col, M, trees, houses, plot):
    assets_col = coll("ENV_TreeAssets", col)
    assets = env_trees.build_assets(assets_col)
    for ob in assets.values():
        ob.hide_render = True
        ob.hide_viewport = True
    # occupancy grid of house footprints (+1 m) so no tree grows through a roof
    occ = {}
    for h in houses:
        r = max(h["w"], h["d"]) / 2 + 1.0
        for i in range(int((h["E"] - r) // 5), int((h["E"] + r) // 5) + 1):
            for j in range(int((h["N"] - r) // 5), int((h["N"] + r) // 5) + 1):
                occ.setdefault((i, j), []).append(h)
    def in_house(E, N):
        for h in occ.get((int(E // 5), int(N // 5)), ()):
            a = h["ang"]
            dx, dy = E - h["E"], N - h["N"]
            u = dx * math.cos(a) + dy * math.sin(a)
            v = -dx * math.sin(a) + dy * math.cos(a)
            if abs(u) < h["w"] / 2 + 1.0 and abs(v) < h["d"] / 2 + 1.0:
                return True
        return False
    pc, phx, phy = plot
    rng = random.Random(11)
    groups = {}
    kept = 0
    for E, N, src in trees:
        f = to_flat(E, N)
        # inside own plot: only a few retained palms along the boundary
        if abs(f[0] - pc[0]) < phx + 1 and abs(f[1] - pc[1]) < phy + 1:
            edge = min(phx - abs(f[0] - pc[0]), phy - abs(f[1] - pc[1]))
            if edge > 3.5 or rng.random() < 0.6:
                continue
        if in_house(E, N):
            continue
        d = math.hypot(E - TE, N - TN)
        r = rng.random()
        if d < 900:
            kind = "PALM" if r < 0.56 else ("BROAD" if r < 0.84 else ("ARECA" if r < 0.94 else "BANANA"))
        else:
            kind = "PALM" if r < 0.62 else "BROAD"
        if kind == "PALM":
            name = rng.choice(["PALM_A", "PALM_B", "PALM_C", "PALM_D", "PALM_E"])
            s = rng.uniform(0.85, 1.12)
        elif kind == "BROAD":
            name = rng.choice(["BROAD_DOME_A", "BROAD_DOME_A", "BROAD_DOME_B", "BROAD_TALL_A", "BROAD_SPREAD_A"])
            s = rng.uniform(0.9, 1.45)
        elif kind == "ARECA":
            name = rng.choice(["ARECA_A", "ARECA_B"])
            s = rng.uniform(0.85, 1.15)
        else:
            name = "BANANA_A"
            s = rng.uniform(0.8, 1.2)
        if d > 380:
            name += "_FAR"
        g = ground(E, N)
        groups.setdefault(name, []).append((f[0], f[1], g - FFL, rng.uniform(0, 2 * math.pi), s))
        kept += 1
    # undergrowth: shrubs and young palms between the trees within 700 m (jittered grid on the canopy mask)
    srng = random.Random(23)
    for E in np.arange(-700, 700, 4.5):
        for N in np.arange(-700, 700, 4.5):
            e, n = E + srng.uniform(0, 4.5), N + srng.uniform(0, 4.5)
            dd = math.hypot(e - TE, n - TN)
            if dd > 700 or cover(e, n)[0] < 0.45 or in_house(e, n):
                continue
            f = to_flat(e, n)
            if abs(f[0] - pc[0]) < phx + 1 and abs(f[1] - pc[1]) < phy + 1:
                continue
            r = srng.random()
            if r < 0.55:
                name, s = "BROAD_DOME_B" + ("_FAR" if dd > 250 else ""), srng.uniform(0.3, 0.55)
            elif r < 0.75:
                name, s = "BANANA_A" + ("_FAR" if dd > 250 else ""), srng.uniform(0.8, 1.2)
            else:
                name, s = "PALM_D" + ("_FAR" if dd > 250 else ""), srng.uniform(0.25, 0.4)
            groups.setdefault(name, []).append((f[0], f[1], ground(e, n) - FFL, srng.uniform(0, 6.283), s))
    inst_col = coll("ENV_Trees", col)
    for name, pts in groups.items():
        me = bpy.data.meshes.new("PTS_" + name)
        me.from_pydata([(x, y, z) for x, y, z, r, s in pts], [], [])
        ra = me.attributes.new("rot", "FLOAT", "POINT")
        sa = me.attributes.new("scl", "FLOAT", "POINT")
        ra.data.foreach_set("value", [p[3] for p in pts])
        sa.data.foreach_set("value", [p[4] for p in pts])
        ob = bpy.data.objects.new("ENV_Trees_" + name, me)
        inst_col.objects.link(ob)
        mod = ob.modifiers.new("inst", "NODES")
        mod.node_group = instancer_group(assets[name])
    return kept, groups


def instancer_group(asset):
    ng = bpy.data.node_groups.new("INST_" + asset.name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = asset
    oi.transform_space = "ORIGINAL"
    iop = N.new("GeometryNodeInstanceOnPoints")
    rot = N.new("GeometryNodeInputNamedAttribute")
    rot.data_type = "FLOAT"
    rot.inputs["Name"].default_value = "rot"
    scl = N.new("GeometryNodeInputNamedAttribute")
    scl.data_type = "FLOAT"
    scl.inputs["Name"].default_value = "scl"
    comb = N.new("ShaderNodeCombineXYZ")
    L = ng.links
    L.new(rot.outputs["Attribute"], comb.inputs["Z"])
    L.new(gi.outputs["Geometry"], iop.inputs["Points"])
    L.new(oi.outputs["Geometry"], iop.inputs["Instance"])
    L.new(comb.outputs["Vector"], iop.inputs["Rotation"])
    L.new(scl.outputs["Attribute"], iop.inputs["Scale"])
    L.new(iop.outputs["Instances"], go.inputs["Geometry"])
    return ng


# ------------------------------------------------------------------ main
def main():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    M = materials()
    root = coll("06_Environment")
    houses = json.load(open(os.path.join(DATA, "houses.json")))["houses"]
    trees = json.load(open(os.path.join(DATA, "trees.json")))["trees"]
    roads = json.load(open(os.path.join(DATA, "roads.json")))["roads"]
    towers = json.load(open(os.path.join(DATA, "towers.json")))["towers"]
    build_terrain(coll("ENV_Terrain", root), M)
    nh = build_houses(coll("ENV_Houses", root), M, houses)
    build_towers(coll("ENV_Towers", root), M, towers)
    plot = build_own_tower(coll("ENV_OwnTower", root), M)
    nw = build_roads(coll("ENV_Roads", root), M, roads)
    kept, groups = build_trees(coll("ENV_Vegetation", root), M, trees, houses, plot)
    # placement record for the Unreal import (flat frame, metres; UE = (x, -y, z) * 100)
    json.dump({k: [[round(x, 3), round(y, 3), round(z, 3), round(r, 4), round(s, 4)] for x, y, z, r, s in v] for k, v in groups.items()},
              open(os.path.join(DATA, "tree_instances_flat.json"), "w"))
    meta = {"FFL": FFL, "flat_origin_site_EN": [TE, TN], "plan_px_m": PX, "bearing_plusY": _BY, "bearing_plusX": (_BY + 90) % 360,
            "houses": nh, "trees": kept, "wires": nw, "groups": {k: len(v) for k, v in groups.items()}}
    json.dump(meta, open(os.path.join(DATA, "build_meta.json"), "w"), indent=1)
    out = os.path.join(ROOT, "blender", "environment.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("ENV_BUILD", json.dumps(meta))


main()
