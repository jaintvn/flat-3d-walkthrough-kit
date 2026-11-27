"""Geometry toolkit (all inputs in centimetres): boxes, cushions, rounded boxes, lathes,
curved shells, curtains and Poly Haven asset placement."""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, Euler
from lib import MB, coll, get_mat, box_uv

C = 0.01
BLENDER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ Item (multi-part, single object)
class Item:
    """Accumulates geometry in cm, builds one object with origin at `origin` (cm)."""

    def __init__(self, name, collection, origin=(0, 0, 0)):
        self.name, self.col, self.o = name, collection, origin
        self.mb = MB()

    def box(self, x0, x1, y0, y1, z0, z1, mat, skip=()):
        self.mb.box(x0 * C, x1 * C, y0 * C, y1 * C, z0 * C, z1 * C, mat, skip)

    def cyl(self, cx, cy, z0, z1, r, mat, seg=24, r1=None, axis="z", caps=True):
        self.mb.cyl(cx * C, cy * C, z0 * C, z1 * C, r * C, mat, seg, None if r1 is None else r1 * C, caps=caps, axis=axis)

    def torus(self, cx, cy, cz, R, r, mat, seg=48, rseg=10):
        self.mb.torus(cx * C, cy * C, cz * C, R * C, r * C, mat, seg, rseg)

    def sphere(self, cx, cy, cz, rx, ry, rz, mat, seg=16, rings=10):
        self.mb.sphere(cx * C, cy * C, cz * C, rx * C, ry * C, rz * C, mat, seg, rings)

    def face(self, pts, mat, smooth=False):
        self.mb.face([(x * C, y * C, z * C) for x, y, z in pts], mat, smooth)

    def done(self, rot_deg=0.0):
        o = Vector(self.o) * C
        self.mb.v = [p - o for p in self.mb.v]
        return self.mb.build(self.name, self.col, loc=o, rot_z=math.radians(rot_deg))


def local_item(name, collection, loc_cm, rot_deg, build_fn):
    it = Item(name, collection, (0, 0, 0))
    build_fn(it)
    return it.mb.build(name, collection, loc=Vector(loc_cm) * C, rot_z=math.radians(rot_deg))


# ------------------------------------------------------------------ bmesh helpers
def _finish(bm, name, col, mat, loc, rot, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if isinstance(mat, (list, tuple)):
        for m in mat:
            me.materials.append(get_mat(m))
    else:
        me.materials.append(get_mat(mat))
    for p in me.polygons:
        p.use_smooth = smooth
    box_uv(me)
    ob = bpy.data.objects.new(name, me)
    ob.location = Vector(loc) * C
    ob.rotation_euler = Euler([math.radians(a) for a in rot])
    col.objects.link(ob)
    return ob


def _xyz(rot):
    return rot if isinstance(rot, (list, tuple)) else (0, 0, rot)


def cushion(name, col, sx, sy, sz, mat, loc=(0, 0, 0), rot=0, crown=0.18, side=0.06, cuts=6, sub=2, seed=0, sag=0.0):
    """Upholstered cushion: subdivided box with crowned faces + subdivision surface. loc = bottom centre."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        u, w, h = v.co.x * 2, v.co.y * 2, v.co.z * 2            # -1..1
        x, y, z = u * sx / 2, w * sy / 2, h * sz / 2
        top = (1 - u * u) * (1 - w * w)
        z += math.copysign(crown * sz / 2 * top, h) if abs(h) > 0.99 else 0
        if abs(h) > 0.99 and h > 0:
            z -= sag * sz * (1 - u * u) * (1 - w * w)
        x += math.copysign(side * sx / 2 * (1 - w * w) * (1 - h * h), u) if abs(u) > 0.99 else 0
        y += math.copysign(side * sy / 2 * (1 - u * u) * (1 - h * h), w) if abs(w) > 0.99 else 0
        x += rnd.uniform(-0.15, 0.15); y += rnd.uniform(-0.15, 0.15); z += rnd.uniform(-0.1, 0.1)
        v.co = Vector((x * C, y * C, (z + sz / 2) * C))
    ob = _finish(bm, name, col, mat, loc, _xyz(rot))
    m = ob.modifiers.new("Subdiv", "SUBSURF")
    m.levels = m.render_levels = sub
    return ob


def upright_cushion(name, col, w, h, t, mat, base, lean=12.0, yaw=0.0, crown=0.5, side=0.08, cuts=5, seed=0):
    """Standing cushion (pillow / back cushion / headboard channel) puffed on its front and back faces.
    base = (x, y, z) cm of the bottom-edge midpoint; leans back by `lean` deg towards local -y of the yaw frame
    (i.e. the pillow's front faces +y of the frame)."""
    rot = Euler((math.radians(90 - lean), 0, math.radians(yaw)))
    ob = cushion(name, col, w, h, t, mat, (0, 0, 0), 0, crown=crown, side=side, cuts=cuts, seed=seed)
    ob.rotation_euler = rot
    # base = bottom edge of the back face (local y=-h/2, z=0)
    ob.location = Vector(base) * C - rot.to_matrix() @ Vector((0, -h / 2 * C, 0))
    return ob


def rbox(name, col, sx, sy, sz, mat, loc=(0, 0, 0), rot=0, r=1.0, seg=3):
    """Rounded box (bevel modifier, hardened normals). loc = bottom centre."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx * C, v.co.y * sy * C, (v.co.z + 0.5) * sz * C))
    ob = _finish(bm, name, col, mat, loc, _xyz(rot), smooth=True)
    b = ob.modifiers.new("Bevel", "BEVEL")
    b.width = r * C
    b.segments = seg
    b.limit_method = "NONE"
    b.harden_normals = True
    b.use_clamp_overlap = True
    return ob


def lathe(name, col, profile, mat, loc=(0, 0, 0), rot=0, seg=48, smooth=True, sub=0):
    """Surface of revolution around local Z. profile: [(r, z), ...] cm, ordered along the surface."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring.append(bm.verts.new((r * math.cos(a) * C, r * math.sin(a) * C, z * C)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            try:
                bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = _finish(bm, name, col, mat, loc, _xyz(rot), smooth)
    if sub:
        m = ob.modifiers.new("Subdiv", "SUBSURF"); m.levels = m.render_levels = sub
    return ob


def shell_arc(name, col, R, ang, z0, z1, thick, mat, loc=(0, 0, 0), rot=0, seg=18, vseg=4, flare=0.0, sub=2):
    """Curved upholstered shell (chair backs / tub chairs): arc of radius R behind the origin (toward -Y)."""
    bm = bmesh.new()
    grid = []
    for j in range(vseg + 1):
        t = j / vseg
        z = z0 + (z1 - z0) * t
        rr = R + flare * t
        row = []
        for i in range(seg + 1):
            a = math.radians(-ang / 2 + ang * i / seg)
            row.append(bm.verts.new((rr * math.sin(a) * C, -rr * math.cos(a) * C, z * C)))
        grid.append(row)
    for j in range(vseg):
        for i in range(seg):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    ob = _finish(bm, name, col, mat, loc, _xyz(rot))
    s = ob.modifiers.new("Solidify", "SOLIDIFY")
    s.thickness = thick * C
    s.offset = 0
    m = ob.modifiers.new("Subdiv", "SUBSURF"); m.levels = m.render_levels = sub
    return ob


def curtain(col, name, p0, p1, z0, z1, mat="M_Curtain_Drape", amp=4.5, rod=True, seed=1, rows=10):
    """Pleated curtain along p0->p1 (cm). Folds flare slightly towards the hem."""
    rnd = random.Random(seed)
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    d.normalize()
    n = Vector((-d.y, d.x))
    folds = max(2, int(L / 10))
    steps = folds * 6
    phase = [rnd.uniform(-0.25, 0.25) for _ in range(folds + 2)]
    ampv = [amp * rnd.uniform(0.75, 1.2) for _ in range(folds + 2)]
    bm = bmesh.new()
    grid = []
    for r in range(rows + 1):
        t = r / rows
        z = z1 - (z1 - z0) * t
        row = []
        for i in range(steps + 1):
            s = i / steps
            k = int(s * folds)
            a = ampv[k] * (1 + 0.35 * t)
            off = a * math.sin((s * folds + phase[k] * t) * 2 * math.pi)
            p = p0 + d * (L * s) + n * off
            row.append(bm.verts.new((p.x * C, p.y * C, z * C)))
        grid.append(row)
    for r in range(rows):
        for i in range(steps):
            bm.faces.new((grid[r][i], grid[r][i + 1], grid[r + 1][i + 1], grid[r + 1][i]))
    ob = _finish(bm, name, col, mat, (0, 0, 0), (0, 0, 0))
    sd = ob.modifiers.new("Solidify", "SOLIDIFY"); sd.thickness = 0.004; sd.offset = 0
    if rod:
        it = Item(name + "_Rod", col)
        q0, q1 = p0 - d * 8, p1 + d * 8
        if abs(d.x) > abs(d.y):
            it.cyl(0, 0, 0, 0, 0, "M_BlackMetal", seg=3, caps=False) if False else None
            it.box(min(q0.x, q1.x), max(q0.x, q1.x), q0.y - 0.9, q0.y + 0.9, z1 + 2, z1 + 3.8, "M_BlackMetal")
        else:
            it.box(q0.x - 0.9, q0.x + 0.9, min(q0.y, q1.y), max(q0.y, q1.y), z1 + 2, z1 + 3.8, "M_BlackMetal")
        it.done()
    return ob


def mould_frames(col, name, plane, rects, depth=1.6, w=3.0, mat="M_Moulding_White"):
    """Picture-frame wall mouldings with a stepped profile. plane=('x'|'y', coord, sign)."""
    it = Item(name, col)
    ax, c, s = plane
    for a0, a1, z0, z1 in rects:
        for (p0, p1, q0, q1) in ((a0, a1, z0, z0 + w), (a0, a1, z1 - w, z1), (a0, a0 + w, z0, z1), (a1 - w, a1, z0, z1)):
            for dd, inset in ((depth * 0.55, 0.0), (depth, 0.8)):
                pp0, pp1 = p0 + (inset if p1 - p0 > w + 0.1 else 0), p1 - (inset if p1 - p0 > w + 0.1 else 0)
                qq0, qq1 = q0 + (inset if q1 - q0 > w + 0.1 else 0), q1 - (inset if q1 - q0 > w + 0.1 else 0)
                if p1 - p0 <= w + 0.1:
                    pp0, pp1 = p0 + inset, p1 - inset
                if q1 - q0 <= w + 0.1:
                    qq0, qq1 = q0 + inset, q1 - inset
                if ax == "y":
                    it.box(pp0, pp1, c, c + s * dd, qq0, qq1, mat)
                else:
                    it.box(c, c + s * dd, pp0, pp1, qq0, qq1, mat)
    return it.done()


def wall_art(col, name, plane, a_c, z_c, w, h, mat, frame="M_Brass"):
    it = Item(name, col)
    ax, c, s = plane
    if ax == "y":
        it.box(a_c - w / 2, a_c + w / 2, c, c + s * 3, z_c - h / 2, z_c + h / 2, frame)
        it.box(a_c - w / 2 + 2, a_c + w / 2 - 2, c + s * 3, c + s * 3.4, z_c - h / 2 + 2, z_c + h / 2 - 2, mat)
    else:
        it.box(c, c + s * 3, a_c - w / 2, a_c + w / 2, z_c - h / 2, z_c + h / 2, frame)
        it.box(c + s * 3, c + s * 3.4, a_c - w / 2 + 2, a_c + w / 2 - 2, z_c - h / 2 + 2, z_c + h / 2 - 2, mat)
    return it.done()


# ------------------------------------------------------------------ Poly Haven assets
_ASSETS = {}


def asset_src(aid):
    """Imports assets/<aid>/<aid>_2k.gltf once, joins parts, origin at bottom centre, stores in an excluded collection."""
    if aid in _ASSETS:
        return _ASSETS[aid]
    path = os.path.join(BLENDER_DIR, "assets", aid, aid + "_2k.gltf")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in meshes:
        o.data = o.data.copy()
        o.data.transform(o.matrix_world)
    for o in meshes:
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    main = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=main, object=main, selected_objects=meshes, selected_editable_objects=meshes):
            bpy.ops.object.join()
    pts = [Vector(v.co) for v in main.data.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    off = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    main.data.transform(Matrix.Translation(-off))
    main.name = main.data.name = "SM_" + aid
    src_col = coll("99_AssetSource")
    for c in list(main.users_collection):
        c.objects.unlink(main)
    src_col.objects.link(main)
    lc = bpy.context.view_layer.layer_collection.children.get("99_AssetSource")
    if lc:
        lc.exclude = True
    main["size_cm"] = [(mx.x - mn.x) * 100, (mx.y - mn.y) * 100, (mx.z - mn.z) * 100]
    _ASSETS[aid] = main
    return main


def place(aid, name, col, loc_cm, rot_deg=0.0, scale=1.0, height=None, top_anchor=False):
    """Linked duplicate of an asset. height (cm) rescales uniformly; top_anchor puts loc at the top (pendants)."""
    src = asset_src(aid)
    if height:
        scale = height / src["size_cm"][2]
    ob = bpy.data.objects.new(name, src.data)
    z = loc_cm[2] - (src["size_cm"][2] * scale if top_anchor else 0)
    ob.location = (loc_cm[0] * C, loc_cm[1] * C, z * C)
    ob.rotation_euler.z = math.radians(rot_deg)
    ob.scale = (scale, scale, scale)
    ob["asset"] = aid
    col.objects.link(ob)
    return ob
