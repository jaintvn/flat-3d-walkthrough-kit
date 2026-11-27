"""Geometry + material helpers for the Type G flat build (Blender 5.x)."""
import bpy, math
from mathutils import Vector, Matrix

CM = 0.01


# ------------------------------------------------------------------ collections
def coll(path):
    parent = bpy.context.scene.collection
    for part in path.split("/"):
        c = bpy.data.collections.get(part)
        if c is None:
            c = bpy.data.collections.new(part)
            parent.children.link(c)
        parent = c
    return parent


# ------------------------------------------------------------------ mesh builder
class MB:
    """Collects quads/ngons in local metres; per-face material names; box-projected UVs (1 UV = 1 m)."""

    def __init__(self):
        self.v, self.f, self.fm, self.smooth = [], [], [], []

    def face(self, pts, mat, smooth=False):
        i = len(self.v)
        self.v += [Vector(p) for p in pts]
        self.f.append(tuple(range(i, i + len(pts))))
        self.fm.append(mat)
        self.smooth.append(smooth)

    def box(self, x0, x1, y0, y1, z0, z1, mat, skip=()):
        """mat: str or dict with keys '+x','-x','+y','-y','+z','-z' (missing -> '*')."""
        if x0 > x1: x0, x1 = x1, x0
        if y0 > y1: y0, y1 = y1, y0
        if z0 > z1: z0, z1 = z1, z0
        g = (lambda k: mat.get(k, mat.get("*"))) if isinstance(mat, dict) else (lambda k: mat)
        F = {
            "+z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            "-z": [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
            "+x": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            "-x": [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
            "+y": [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
            "-y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        }
        for k, pts in F.items():
            if k in skip:
                continue
            self.face(pts, g(k))

    def boxc(self, cx, cy, z0, sx, sy, h, mat, **kw):
        self.box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0, z0 + h, mat, **kw)

    def cyl(self, cx, cy, z0, z1, r, mat, seg=24, r1=None, caps=True, smooth=True, axis="z"):
        r1 = r if r1 is None else r1
        ring0, ring1 = [], []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            c, s = math.cos(a), math.sin(a)
            ring0.append(self._ax(axis, cx, cy, z0, r * c, r * s))
            ring1.append(self._ax(axis, cx, cy, z1, r1 * c, r1 * s))
        for i in range(seg):
            j = (i + 1) % seg
            self.face([ring0[i], ring0[j], ring1[j], ring1[i]], mat, smooth)
        if caps:
            self.face(list(reversed(ring0)), mat)
            self.face(ring1, mat)

    @staticmethod
    def _ax(axis, cx, cy, z, a, b):
        if axis == "z":
            return (cx + a, cy + b, z)
        if axis == "x":
            return (z, cx + a, cy + b)
        return (cx + a, z, cy + b)  # axis y

    def torus(self, cx, cy, cz, R, r, mat, seg=48, rseg=10):
        rings = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring = []
            for j in range(rseg):
                b = 2 * math.pi * j / rseg
                d = R + r * math.cos(b)
                ring.append((cx + d * math.cos(a), cy + d * math.sin(a), cz + r * math.sin(b)))
            rings.append(ring)
        for i in range(seg):
            for j in range(rseg):
                i2, j2 = (i + 1) % seg, (j + 1) % rseg
                self.face([rings[i][j], rings[i2][j], rings[i2][j2], rings[i][j2]], mat, True)

    def sphere(self, cx, cy, cz, rx, ry, rz, mat, seg=16, rings=10):
        pts = []
        for i in range(rings + 1):
            t = math.pi * i / rings
            row = []
            for j in range(seg):
                p = 2 * math.pi * j / seg
                row.append((cx + rx * math.sin(t) * math.cos(p), cy + ry * math.sin(t) * math.sin(p), cz - rz * math.cos(t)))
            pts.append(row)
        for i in range(rings):
            for j in range(seg):
                j2 = (j + 1) % seg
                self.face([pts[i][j], pts[i][j2], pts[i + 1][j2], pts[i + 1][j]], mat, True)

    def transform(self, M, start=0):
        for i in range(start, len(self.v)):
            self.v[i] = M @ self.v[i]

    def build(self, name, collection, loc=(0, 0, 0), rot_z=0.0, uv_scale=1.0):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(p) for p in self.v], [], self.f)
        mats = []
        for mname in self.fm:
            if mname not in mats:
                mats.append(mname)
        for mname in mats:
            me.materials.append(get_mat(mname))
        idx = {n: i for i, n in enumerate(mats)}
        for p, mname, sm in zip(me.polygons, self.fm, self.smooth):
            p.material_index = idx[mname]
            p.use_smooth = sm
        box_uv(me, uv_scale)
        me.validate()
        ob = bpy.data.objects.new(name, me)
        ob.location = loc
        ob.rotation_euler.z = rot_z
        collection.objects.link(ob)
        return ob


def box_uv(me, scale=1.0):
    uv = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 2:
                u, v = co.x, co.y * (1 if n.z > 0 else -1)
            elif ax == 0:
                u, v = co.y * (1 if n.x > 0 else -1), co.z
            else:
                u, v = -co.x * (1 if n.y > 0 else -1), co.z
            uv.data[li].uv = (u * scale, v * scale)


def add_lightmap_uv(ob):
    """Second UV channel for Unreal lightmaps (smart project, non-overlapping)."""
    me = ob.data
    if len(me.uv_layers) > 1:
        return
    me.uv_layers.new(name="LightmapUV")


def bevel(ob, w=0.005, seg=2, harden=True):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = w
    m.segments = seg
    m.limit_method = "ANGLE"
    m.harden_normals = harden
    return m


def soft(ob, w=0.04, seg=5):
    m = bevel(ob, w, seg, harden=False)
    m.limit_method = "NONE"
    m.use_clamp_overlap = True
    for p in ob.data.polygons:
        p.use_smooth = True
    return m


def subsurf(ob, lv=2):
    m = ob.modifiers.new("Subdiv", "SUBSURF")
    m.levels = lv
    m.render_levels = lv
    for p in ob.data.polygons:
        p.use_smooth = True
    return m


# ------------------------------------------------------------------ materials
_MATS = {}


def _pbsdf(m):
    m.use_nodes = True
    nt = m.node_tree
    return nt, nt.nodes["Principled BSDF"]


def _rgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def simple(name, col, rough=0.5, metal=0.0, coat=0.0, sheen=0.0, emit=None, estr=0.0, trans=0.0, ior=1.45, alpha=1.0):
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    b.inputs["Base Color"].default_value = _rgb(col)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Transmission Weight"].default_value = trans
    b.inputs["IOR"].default_value = ior
    b.inputs["Alpha"].default_value = alpha
    if emit:
        b.inputs["Emission Color"].default_value = _rgb(emit)
        b.inputs["Emission Strength"].default_value = estr
    m.diffuse_color = _rgb(col)[:3] + (alpha,)
    return m


def _uv(nt, scale=(1, 1, 1), rot=0.0):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def _ramp(nt, inp, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    cr = r.color_ramp
    cr.elements[0].position, cr.elements[0].color = stops[0][0], _rgb(stops[0][1])
    cr.elements[1].position, cr.elements[1].color = stops[-1][0], _rgb(stops[-1][1])
    for pos, col in stops[1:-1]:
        e = cr.elements.new(pos)
        e.color = _rgb(col)
    nt.links.new(inp, r.inputs["Fac"])
    return r.outputs["Color"]


def _mix(nt, a, b, fac, blend="MIX"):
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = blend
    nt.links.new(fac, mx.inputs["Factor"]) if not isinstance(fac, float) else None
    if isinstance(fac, float):
        mx.inputs["Factor"].default_value = fac
    for sock, val in ((mx.inputs[6], a), (mx.inputs[7], b)):
        if isinstance(val, tuple):
            sock.default_value = val
        else:
            nt.links.new(val, sock)
    return mx.outputs[2]


def marble_tiles(name, base, vein, tile=0.8, grout="#d9d2c4", rough=0.12, vein_amt=0.55, vscale=1.0):
    """Polished marble-look vitrified tiles: warped Voronoi crack veins + soft clouding + grout lines."""
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    vec = _uv(nt)
    warp = nt.nodes.new("ShaderNodeTexNoise")
    warp.inputs["Scale"].default_value = 1.1 * vscale
    warp.inputs["Detail"].default_value = 8
    warp.inputs["Roughness"].default_value = 0.6
    nt.links.new(vec, warp.inputs["Vector"])
    wsc = nt.nodes.new("ShaderNodeVectorMath"); wsc.operation = "SCALE"; wsc.inputs["Scale"].default_value = 0.45
    nt.links.new(warp.outputs["Color"], wsc.inputs[0])
    wadd = nt.nodes.new("ShaderNodeVectorMath"); wadd.operation = "ADD"
    nt.links.new(vec, wadd.inputs[0]); nt.links.new(wsc.outputs[0], wadd.inputs[1])

    def veins(scale, width, amt):
        vo = nt.nodes.new("ShaderNodeTexVoronoi")
        vo.feature = "DISTANCE_TO_EDGE"
        vo.inputs["Scale"].default_value = scale * vscale
        vo.inputs["Randomness"].default_value = 1.0
        nt.links.new(wadd.outputs[0], vo.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs[1].default_value = 0.0
        mr.inputs[2].default_value = width
        mr.inputs[3].default_value = amt
        mr.inputs[4].default_value = 0.0
        nt.links.new(vo.outputs["Distance"], mr.inputs[0])
        return mr.outputs[0]
    v1 = veins(0.9, 0.012, vein_amt)
    v2 = veins(2.6, 0.006, vein_amt * 0.45)
    vsum = nt.nodes.new("ShaderNodeMath"); vsum.operation = "MAXIMUM"; vsum.use_clamp = True
    nt.links.new(v1, vsum.inputs[0]); nt.links.new(v2, vsum.inputs[1])
    cl = nt.nodes.new("ShaderNodeTexNoise")
    cl.inputs["Scale"].default_value = 0.7 * vscale
    cl.inputs["Detail"].default_value = 4
    nt.links.new(vec, cl.inputs["Vector"])
    cloud = _ramp(nt, cl.outputs["Fac"], [(0.35, _hexmix(base, "#9a8f80", 0.10)), (0.65, _hexmix(base, "#ffffff", 0.25))])
    col = _mix(nt, cloud, _rgb(vein), vsum.outputs[0])
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.0018
    br.inputs["Mortar Smooth"].default_value = 0.2
    br.inputs["Brick Width"].default_value = tile
    br.inputs["Row Height"].default_value = tile
    br.inputs["Color1"].default_value = (1, 1, 1, 1)
    br.inputs["Color2"].default_value = (0.96, 0.96, 0.95, 1)
    br.inputs["Mortar"].default_value = _rgb(grout)
    nt.links.new(vec, br.inputs["Vector"])
    final = _mix(nt, col, br.outputs["Color"], 1.0, "MULTIPLY")
    nt.links.new(final, b.inputs["Base Color"])
    rmap = nt.nodes.new("ShaderNodeMapRange")
    rmap.inputs[3].default_value = 0.6
    rmap.inputs[4].default_value = rough
    nt.links.new(br.outputs["Fac"], rmap.inputs[0])
    nt.links.new(rmap.outputs[0], b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.2
    nt.links.new(br.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = _rgb(base)
    return m


def plain_tiles(name, col, w=0.6, h=1.2, grout="#9a948a", rough=0.45, var=0.04, noise_amt=0.05):
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    vec = _uv(nt)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.5; nz.inputs["Detail"].default_value = 6
    nt.links.new(vec, nz.inputs["Vector"])
    c = _ramp(nt, nz.outputs["Fac"], [(0.3, _hexmix(col, "#000000", noise_amt)), (0.7, _hexmix(col, "#ffffff", noise_amt))])
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.5 if h < w else 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.003 / max(w, h)
    br.inputs["Brick Width"].default_value = w
    br.inputs["Row Height"].default_value = h
    br.inputs["Color1"].default_value = (1, 1, 1, 1)
    br.inputs["Color2"].default_value = (1 - var, 1 - var, 1 - var, 1)
    br.inputs["Mortar"].default_value = _rgb(grout)
    nt.links.new(vec, br.inputs["Vector"])
    final = _mix(nt, c, br.outputs["Color"], 1.0, "MULTIPLY")
    nt.links.new(final, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.3
    nt.links.new(br.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = _rgb(col)
    return m


def wood(name, c1, c2, rough=0.45, scale=1.0, plank=None, coat=0.15, rot=0.0):
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    vec = _uv(nt, scale=(scale * 1.0, scale * 9.0, scale), rot=rot)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.5; nz.inputs["Detail"].default_value = 10
    nz.inputs["Distortion"].default_value = 1.5
    nt.links.new(vec, nz.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 3.0; wv.inputs["Distortion"].default_value = 6; wv.inputs["Detail"].default_value = 4
    nt.links.new(vec, wv.inputs["Vector"])
    f = nt.nodes.new("ShaderNodeMath"); f.operation = "MULTIPLY"
    nt.links.new(wv.outputs["Fac"], f.inputs[0]); nt.links.new(nz.outputs["Fac"], f.inputs[1])
    col = _ramp(nt, f.outputs[0], [(0.05, c2), (0.45, c1), (0.75, _hexmix(c1, "#ffffff", 0.08))])
    if plank:
        br = nt.nodes.new("ShaderNodeTexBrick")
        br.offset = 0.5
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Brick Width"].default_value = plank[1]
        br.inputs["Row Height"].default_value = plank[0]
        br.inputs["Mortar Size"].default_value = 0.002
        br.inputs["Color1"].default_value = (1, 1, 1, 1)
        br.inputs["Color2"].default_value = (0.85, 0.85, 0.85, 1)
        br.inputs["Mortar"].default_value = (0.05, 0.04, 0.03, 1)
        v2 = _uv(nt)
        nt.links.new(v2, br.inputs["Vector"])
        col = _mix(nt, col, br.outputs["Color"], 1.0, "MULTIPLY")
    nt.links.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = _rgb(c1)
    return m


def fabric(name, col, rough=0.85, weave=220.0, sheen=0.6):
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    vec = _uv(nt)
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = weave; wv.inputs["Distortion"].default_value = 0.4
    nt.links.new(vec, wv.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 30; nt.links.new(vec, nz.inputs["Vector"])
    c = _ramp(nt, nz.outputs["Fac"], [(0.3, _hexmix(col, "#000000", 0.08)), (0.7, _hexmix(col, "#ffffff", 0.06))])
    nt.links.new(c, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = sheen
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.15
    nt.links.new(wv.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m.diffuse_color = _rgb(col)
    return m


def art(name, cols):
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    vec = _uv(nt, scale=(1.5, 1.5, 1.5))
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.2; nz.inputs["Detail"].default_value = 12
    nz.inputs["Distortion"].default_value = 2.5
    nt.links.new(vec, nz.inputs["Vector"])
    stops = [(i / (len(cols) - 1), c) for i, c in enumerate(cols)]
    c = _ramp(nt, nz.outputs["Fac"], stops)
    nt.links.new(c, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    m.diffuse_color = _rgb(cols[len(cols) // 2])
    return m


def rug(name, c1, c2):
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    vec = _uv(nt)
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "DIAGONAL"
    wv.inputs["Scale"].default_value = 14; wv.inputs["Distortion"].default_value = 0.5
    nt.links.new(vec, wv.inputs["Vector"])
    ch = nt.nodes.new("ShaderNodeTexChecker"); ch.inputs["Scale"].default_value = 40
    nt.links.new(vec, ch.inputs["Vector"])
    c = _ramp(nt, wv.outputs["Fac"], [(0.4, c1), (0.6, c2)])
    c = _mix(nt, c, ch.outputs["Color"], 0.08, "OVERLAY")
    nt.links.new(c, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    b.inputs["Sheen Weight"].default_value = 0.8
    m.diffuse_color = _rgb(c1)
    return m


def _hexmix(a, b, t):
    a = a.lstrip("#"); b = b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join("%02x" % round(x + (y - x) * t) for x, y in zip(ca, cb))


def curtain_sheer(name, col):
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    b.inputs["Base Color"].default_value = _rgb(col)
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Transmission Weight"].default_value = 0.0
    b.inputs["Alpha"].default_value = 0.55
    b.inputs["Sheen Weight"].default_value = 0.5
    m.diffuse_color = _rgb(col)[:3] + (0.55,)
    try:
        m.surface_render_method = "BLENDED"
    except Exception:
        pass
    return m


def glass(name, tint="#f2f6f5", rough=0.0):
    m = simple(name, tint, rough=rough, trans=1.0, ior=1.5)
    return m


def make_all():
    P = {}
    P["M_Floor_Marble"] = marble_tiles("M_Floor_Marble", "#ebe3d5", "#a88f6c", tile=0.8, vein_amt=0.5)
    P["M_Quartz_White"] = marble_tiles("M_Quartz_White", "#f1eee8", "#9c968d", tile=3.0, grout="#f1eee8", rough=0.08, vein_amt=0.35, vscale=2.0)
    P["M_Bath_WallTile"] = plain_tiles("M_Bath_WallTile", "#d6cdbf", 0.6, 1.2, grout="#c2b8aa", rough=0.3)
    P["M_Bath_FloorTile"] = plain_tiles("M_Bath_FloorTile", "#948d82", 0.6, 0.6, grout="#7a746a", rough=0.7)
    P["M_Balcony_WoodTile"] = wood("M_Balcony_WoodTile", "#9a7656", "#6e4f36", rough=0.75, plank=(0.2, 1.2), coat=0.0)
    P["M_Wall_Paint"] = simple("M_Wall_Paint", "#e6dccb", 0.9)
    P["M_Wall_Accent"] = simple("M_Wall_Accent", "#d9cbb5", 0.9)
    P["M_Ceiling_White"] = simple("M_Ceiling_White", "#f4f1ea", 0.92)
    P["M_Moulding_White"] = simple("M_Moulding_White", "#f3efe6", 0.6)
    P["M_Ext_Paint"] = simple("M_Ext_Paint", "#e8e2d6", 0.85)
    P["M_Concrete"] = plain_tiles("M_Concrete", "#a39d93", 2.0, 2.0, grout="#a39d93", rough=0.9, noise_amt=0.12)
    P["M_WallTop"] = simple("M_WallTop", "#3a3836", 0.9)
    P["M_Walnut"] = wood("M_Walnut", "#5b3b26", "#33200f", rough=0.42)
    P["M_Walnut_Door"] = wood("M_Walnut_Door", "#4e3221", "#2c1b0e", rough=0.38, coat=0.2)
    P["M_Oak_Light"] = wood("M_Oak_Light", "#b89068", "#8a6644", rough=0.5)
    P["M_Sage_Gloss"] = simple("M_Sage_Gloss", "#7d9686", 0.12, coat=0.6)
    P["M_Grey_Matte"] = simple("M_Grey_Matte", "#55575a", 0.55)
    P["M_White_Gloss"] = simple("M_White_Gloss", "#f2f0ea", 0.15, coat=0.4)
    P["M_Fabric_Beige"] = fabric("M_Fabric_Beige", "#cbbfac")
    P["M_Fabric_Grey"] = fabric("M_Fabric_Grey", "#8d8a86")
    P["M_Fabric_Taupe"] = fabric("M_Fabric_Taupe", "#9e8b77")
    P["M_Fabric_Sage"] = fabric("M_Fabric_Sage", "#8a9a86")
    P["M_Fabric_Cream"] = fabric("M_Fabric_Cream", "#ece7dd", weave=300)
    P["M_Fabric_Charcoal"] = fabric("M_Fabric_Charcoal", "#4a4846")
    P["M_Linen_White"] = fabric("M_Linen_White", "#f1eee8", weave=400, sheen=0.3)
    P["M_Curtain_Drape"] = fabric("M_Curtain_Drape", "#a8957f", weave=160)
    P["M_Curtain_Sheer"] = curtain_sheer("M_Curtain_Sheer", "#f4f1ea")
    P["M_Brass"] = simple("M_Brass", "#c8a35a", 0.28, metal=1.0)
    P["M_Chrome"] = simple("M_Chrome", "#e0e0e0", 0.08, metal=1.0)
    P["M_Steel"] = simple("M_Steel", "#bdbdbd", 0.3, metal=1.0)
    P["M_BlackMetal"] = simple("M_BlackMetal", "#202020", 0.45, metal=0.6)
    P["M_Alu_Frame"] = simple("M_Alu_Frame", "#2b2a29", 0.4, metal=0.7)
    P["M_Glass"] = glass("M_Glass")
    P["M_Glass_Frosted"] = glass("M_Glass_Frosted", rough=0.35)
    P["M_Mirror"] = simple("M_Mirror", "#f5f5f5", 0.0, metal=1.0)
    P["M_Ceramic_White"] = simple("M_Ceramic_White", "#f6f5f1", 0.06, coat=0.5)
    P["M_Black_Gloss"] = simple("M_Black_Gloss", "#0b0b0c", 0.05, coat=0.8)
    P["M_Screen"] = simple("M_Screen", "#050607", 0.03)
    P["M_Leaf"] = simple("M_Leaf", "#3f6a33", 0.55, sheen=0.2)
    P["M_Leaf_Dark"] = simple("M_Leaf_Dark", "#2c4e27", 0.5)
    P["M_Soil"] = simple("M_Soil", "#2a1d14", 1.0)
    P["M_Pot_White"] = simple("M_Pot_White", "#ebe8e1", 0.3)
    P["M_Pot_Concrete"] = simple("M_Pot_Concrete", "#8f8a82", 0.8)
    P["M_Light_Warm"] = simple("M_Light_Warm", "#fff4e0", 0.5, emit="#ffd9a8", estr=12.0)
    P["M_LED_Strip"] = simple("M_LED_Strip", "#fff4e0", 0.5, emit="#ffcf94", estr=25.0)
    P["M_Lampshade"] = simple("M_Lampshade", "#efe6d6", 0.8, emit="#ffd9a8", estr=1.5)
    P["M_Art_Gold"] = art("M_Art_Gold", ["#2c2a33", "#7b5a2e", "#d9a441", "#f0d48a", "#5b6f7c"])
    P["M_Art_Calm"] = art("M_Art_Calm", ["#e8e1d4", "#c9b79c", "#8e9a8b", "#5d6b66"])
    P["M_Rug_Beige"] = rug("M_Rug_Beige", "#cbbca6", "#a8967f")
    P["M_Rug_Grey"] = rug("M_Rug_Grey", "#9d9790", "#7c766f")
    P["M_Granite_Black"] = simple("M_Granite_Black", "#1d1b1a", 0.2, coat=0.5)
    P["M_Rubber"] = simple("M_Rubber", "#151515", 0.8)
    P["M_Plastic_White"] = simple("M_Plastic_White", "#f0eeea", 0.35)
    P["M_Ground"] = simple("M_Ground", "#5f6b4a", 0.95)
    P["M_Road"] = simple("M_Road", "#4a4a4a", 0.9)
    P["M_Building_Far"] = simple("M_Building_Far", "#d8d2c6", 0.85)
    P["M_Switch"] = simple("M_Switch", "#f7f6f2", 0.3)
    P["M_Velvet_Beige"] = fabric("M_Velvet_Beige", "#c9baa4")
    P["M_Leather_Cream"] = simple("M_Leather_Cream", "#e2dace", 0.45)
    P["M_Basin_Ceramic"] = simple("M_Basin_Ceramic", "#f7f6f2", 0.05, coat=0.6)
    P["M_Brass_Brushed"] = simple("M_Brass_Brushed", "#bf9a55", 0.38, metal=1.0)
    P["M_Book_A"] = simple("M_Book_A", "#3f4a44", 0.6)
    P["M_Book_B"] = simple("M_Book_B", "#c9b79a", 0.6)
    P["M_Book_C"] = simple("M_Book_C", "#7a3f2c", 0.6)
    P["M_Towel"] = fabric("M_Towel", "#efe9df", weave=500)
    for k, v in P.items():
        _MATS[k] = v
    apply_textured()
    return P


BLENDER_DIR = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))

# material name -> (texture set, roughness range, normal strength, extra)
TEXTURED = {
    "M_Floor_Marble": ("Floor_Marble", None, 0.6, {}),
    "M_Floor_Passage": ("Floor_Marble", None, 0.6, {"tint": "#e9e4dc"}),
    "M_Quartz_White": ("Quartz", None, 0.0, {"coat": 0.2}),
    "M_Bath_WallTile": ("Bath_Wall", None, 0.6, {}),
    "M_Bath_FloorTile": ("Toilet_Floor", (0.35, 0.7), 1.0, {}),
    "M_Balcony_WoodTile": ("Balcony_Stone", (0.5, 0.9), 1.0, {}),
    "M_Wall_Paint": ("Paint_Wall", (0.82, 0.95), 0.25, {}),
    "M_Ceiling_White": ("Paint_Ceiling", (0.85, 0.95), 0.2, {}),
    "M_Ext_Paint": ("Paint_Ext", (0.8, 0.95), 0.5, {}),
    "M_Concrete": ("Concrete", (0.7, 1.0), 1.0, {}),
    "M_Walnut": ("Walnut", (0.35, 0.55), 0.5, {"coat": 0.15}),
    "M_Walnut_Door": ("Walnut_Door", (0.3, 0.5), 0.5, {"coat": 0.25}),
    "M_Oak_Light": ("Oak", (0.4, 0.6), 0.5, {"coat": 0.1}),
    "M_Fabric_Beige": ("Linen_Beige", (0.75, 0.95), 0.8, {"sheen": 0.5}),
    "M_Fabric_Grey": ("Velvet_Grey", (0.6, 0.9), 0.6, {"sheen": 0.9}),
    "M_Fabric_Taupe": ("Linen_Taupe", (0.75, 0.95), 0.8, {"sheen": 0.5}),
    "M_Fabric_Sage": ("Linen_Sage", (0.75, 0.95), 0.8, {"sheen": 0.5}),
    "M_Fabric_Cream": ("Linen_Cream", (0.75, 0.95), 0.8, {"sheen": 0.5}),
    "M_Fabric_Charcoal": ("Linen_Charcoal", (0.75, 0.95), 0.8, {"sheen": 0.5}),
    "M_Linen_White": ("Linen_White", (0.75, 0.95), 0.6, {"sheen": 0.4}),
    "M_Curtain_Drape": ("Linen_Drape", (0.8, 0.95), 0.8, {"sheen": 0.5}),
    "M_Velvet_Beige": ("Velvet_Beige", (0.6, 0.9), 0.6, {"sheen": 0.9}),
    "M_Leather_Cream": ("Leather_Cream", (0.35, 0.6), 0.8, {}),
    "M_Rug_Beige": ("Rug_Beige", (0.9, 1.0), 1.5, {"sheen": 0.8}),
    "M_Rug_Grey": ("Rug_Grey", (0.9, 1.0), 1.5, {"sheen": 0.8}),
    "M_Art_Gold": ("Art_Gold", None, 0.0, {"rough": 0.55}),
    "M_Art_Calm": ("Art_Calm", None, 0.0, {"rough": 0.55}),
}


def pbr(name, tset, rr, nstr, extra, manifest):
    import os
    e = manifest[tset]
    m = bpy.data.materials.new(name)
    nt, b = _pbsdf(m)
    sc = 1.0 / e["size_m"]
    vec = _uv(nt, scale=(sc, sc, sc))

    def img(rel, data):
        im = bpy.data.images.load(os.path.join(BLENDER_DIR, rel), check_existing=True)
        if data:
            im.colorspace_settings.name = "Non-Color"
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = im
        n.interpolation = "Cubic" if data else "Linear"
        nt.links.new(vec, n.inputs["Vector"])
        return n
    d = img(e["D"], False)
    col = d.outputs["Color"]
    if "tint" in extra:
        col = _mix(nt, col, _rgb(extra["tint"]), 1.0, "MULTIPLY")
        mxn = nt.nodes.new("ShaderNodeMix"); mxn.data_type = "RGBA"
    nt.links.new(col, b.inputs["Base Color"])
    if e.get("R"):
        r = img(e["R"], True)
        if rr:
            mr = nt.nodes.new("ShaderNodeMapRange")
            mr.inputs[3].default_value, mr.inputs[4].default_value = rr
            nt.links.new(r.outputs["Color"], mr.inputs[0])
            nt.links.new(mr.outputs[0], b.inputs["Roughness"])
        else:
            nt.links.new(r.outputs["Color"], b.inputs["Roughness"])
    if e.get("N") and nstr > 0:
        nn = img(e["N"], True)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = nstr
        nt.links.new(nn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Coat Weight"].default_value = extra.get("coat", 0.0)
    b.inputs["Sheen Weight"].default_value = extra.get("sheen", 0.0)
    if not e.get("R"):
        b.inputs["Roughness"].default_value = extra.get("rough", 0.5)
    m["texset"] = tset
    m["rough_range"] = list(rr) if rr else [0.0, 1.0]
    m["normal_strength"] = nstr
    m["tint"] = extra.get("tint", "#ffffff")
    m["coat"] = extra.get("coat", 0.0)
    m["uv_size_m"] = e["size_m"]
    return m


def apply_textured():
    import json, os
    mp = os.path.join(BLENDER_DIR, "textures", "derived", "manifest.json")
    if not os.path.exists(mp):
        print("WARNING: no texture manifest, keeping procedural materials")
        return
    man = json.load(open(mp))
    for name, (tset, rr, nstr, extra) in TEXTURED.items():
        old = bpy.data.materials.get(name)
        if old:
            old.name = name + "_procedural_old"
        _MATS[name] = pbr(name, tset, rr, nstr, extra, man)
    for m in list(bpy.data.materials):
        if m.name.endswith("_procedural_old") and m.users == 0:
            bpy.data.materials.remove(m)


def get_mat(name):
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.get(name)
    if m is None:
        m = simple(name, "#ff00ff", 0.5)
    _MATS[name] = m
    return m
