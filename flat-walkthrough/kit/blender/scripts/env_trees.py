"""Procedural Kerala vegetation for the exterior environment (all opaque geometry: Nanite and Cycles friendly).

Coconut palm (Cocos nucifera, West Coast Tall): 12-22 m, 30-35 cm trunk with a swollen base and leaf-scar rings,
often leaning and curved; 26-32 fronds of 4.5-5.5 m, pinnate with drooping V-set leaflets; a few dead brown fronds
and nut bunches under the crown.  Areca palm: slender 8-14 m stem, small 2.5-3.5 m crown.  Banana: 3-4 m.
Broadleaf (mango / jackfruit / anjili type): dense dome-shaped crowns built from many small leaf quads on a branch
skeleton.

build_assets() returns {name: object}.  Every object has its origin at the base of the trunk, +Z up, metres.
Each asset exists in a near version (full leaflets) and a far version (_FAR, ~10x fewer triangles).
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Quaternion

# ------------------------------------------------------------------ materials
def _mat(name, base, rough=0.6, sss=0.0, spec=0.35, two_tone=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    try:
        b.inputs["Specular IOR Level"].default_value = spec
    except KeyError:
        pass
    if sss:
        try:
            b.inputs["Transmission Weight"].default_value = 0.0
            b.inputs["Subsurface Weight"].default_value = sss
            b.inputs["Subsurface Radius"].default_value = (0.05, 0.08, 0.02)
        except KeyError:
            pass
    # per-instance colour variation: mix two tones with the object's random value (vertex colour drives the
    # within-tree variation); keeps whole stands from looking cloned
    if two_tone:
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        ca = nt.nodes.new("ShaderNodeVertexColor")
        ca.layer_name = "Col"
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["A"].default_value = (*base, 1)
        mix.inputs["B"].default_value = (*two_tone, 1)
        nt.links.new(oi.outputs["Random"], mix.inputs["Factor"])
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(mix.outputs["Result"], mul.inputs["A"])
        nt.links.new(ca.outputs["Color"], mul.inputs["B"])
        nt.links.new(mul.outputs["Result"], b.inputs["Base Color"])
    else:
        b.inputs["Base Color"].default_value = (*base, 1)
    m.diffuse_color = (*base, 1)
    return m


def materials():
    return {
        "frond": _mat("M_Env_PalmFrond", (0.10, 0.15, 0.03), 0.58, 0.15, 0.28, two_tone=(0.17, 0.19, 0.04)),
        "frond_dry": _mat("M_Env_PalmFrondDry", (0.24, 0.15, 0.07), 0.8, two_tone=(0.30, 0.22, 0.11)),
        "trunk": _mat("M_Env_PalmTrunk", (0.20, 0.18, 0.15), 0.9, two_tone=(0.27, 0.25, 0.21)),
        "nut": _mat("M_Env_Coconut", (0.32, 0.30, 0.06), 0.5),
        "areca_leaf": _mat("M_Env_ArecaLeaf", (0.13, 0.20, 0.04), 0.45, 0.15, two_tone=(0.17, 0.22, 0.04)),
        "areca_stem": _mat("M_Env_ArecaStem", (0.33, 0.33, 0.29), 0.85),
        "banana": _mat("M_Env_BananaLeaf", (0.16, 0.27, 0.05), 0.5, 0.15, two_tone=(0.22, 0.30, 0.06)),
        "bark": _mat("M_Env_Bark", (0.11, 0.09, 0.07), 0.95, two_tone=(0.16, 0.14, 0.11)),
        "leaf": _mat("M_Env_Leaf", (0.040, 0.085, 0.020), 0.55, 0.12, two_tone=(0.07, 0.115, 0.025)),
    }


# ------------------------------------------------------------------ helpers
class MB:
    """Tiny mesh builder: vertices + faces per material slot, vertex colour per face corner."""
    def __init__(self):
        self.v, self.f, self.m, self.c = [], [], [], []

    def add(self, pts, faces, mat, col=(1, 1, 1)):
        o = len(self.v)
        self.v += [tuple(p) for p in pts]
        for f in faces:
            self.f.append(tuple(o + i for i in f))
            self.m.append(mat)
            self.c.append(col)

    def build(self, name, mats):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        order = list(dict.fromkeys(self.m))
        for k in order:
            me.materials.append(mats[k])
        idx = {k: i for i, k in enumerate(order)}
        for p, k in zip(me.polygons, self.m):
            p.material_index = idx[k]
            p.use_smooth = True
        ca = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        for p, col in zip(me.polygons, self.c):
            for li in p.loop_indices:
                ca.data[li].color = (*col, 1)
        me.validate()
        ob = bpy.data.objects.new(name, me)
        return ob


def frame(t):
    """Orthonormal frame with tangent t."""
    t = t.normalized()
    up = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))
    s = t.cross(up).normalized()
    u = s.cross(t).normalized()
    return s, u


def tube(mb, path, radii, sides, mat, col=(1, 1, 1), cap=False, ring_dark=None):
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)])
        s, u = frame(t)
        r = radii[i]
        rings.append([p + (s * math.cos(a) + u * math.sin(a)) * r for a in (2 * math.pi * k / sides for k in range(sides))])
    pts = [q for r in rings for q in r]
    faces = []
    for i in range(len(rings) - 1):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    o = len(mb.v)
    mb.v += [tuple(p) for p in pts]
    for n, f in enumerate(faces):
        mb.f.append(tuple(o + i for i in f))
        mb.m.append(mat)
        if ring_dark:
            seg = n // sides
            mb.c.append(ring_dark(seg))
        else:
            mb.c.append(col)
    if cap:
        last = len(rings) - 1
        mb.f.append(tuple(o + last * sides + k for k in range(sides))[::-1])
        mb.m.append(mat)
        mb.c.append(col)


def bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t * t
        d = t ** 3
        out.append(p0 * a + p1 * b + p2 * c + p3 * d)
    return out


# ------------------------------------------------------------------ coconut palm
def coconut(name, seed, height, lean, mats, far=False):
    R = random.Random(seed)
    mb = MB()
    # trunk: curved (leans then recovers towards vertical), swollen base, slight taper, leaf-scar rings
    az = R.uniform(0, 2 * math.pi)
    dirh = Vector((math.cos(az), math.sin(az), 0))
    top = dirh * (height * math.sin(lean)) + Vector((0, 0, height * math.cos(lean)))
    p1 = dirh * height * math.sin(lean) * 0.55 + Vector((0, 0, height * 0.30))
    p2 = top - Vector((0, 0, height * 0.25)) + dirh * height * 0.02
    nseg = 10 if far else 36
    path = bezier(Vector((0, 0, -0.3)), p1, p2, top, nseg)
    radii = []
    for i in range(nseg + 1):
        t = i / nseg
        r = 0.16 + 0.12 * math.exp(-t * 18) + 0.015 * math.sin(t * 9 + seed)
        radii.append(r * (0.92 if t > 0.9 else 1.0))
    shade = lambda seg: (0.78, 0.78, 0.78) if (seg % 2 == 0 and seg > 1) else (1, 1, 1)
    tube(mb, path, radii, 6 if far else 12, "trunk", ring_dark=None if far else shade)
    crown = top
    tdir = (path[-1] - path[-2]).normalized()
    # crown "boot" (sheaths) - a short fat cone
    if not far:
        boot = [crown - tdir * 0.6, crown - tdir * 0.25, crown + tdir * 0.15, crown + tdir * 0.4]
        tube(mb, boot, [0.2, 0.27, 0.25, 0.08], 10, "trunk", col=(0.85, 0.8, 0.7), cap=True)
    # nut bunches
    if not far:
        for k in range(R.randint(3, 6)):
            a = R.uniform(0, 2 * math.pi)
            cpos = crown + Vector((math.cos(a), math.sin(a), 0)) * 0.42 - Vector((0, 0, R.uniform(0.1, 0.5)))
            for j in range(R.randint(4, 8)):
                c = cpos + Vector((R.uniform(-.18, .18), R.uniform(-.18, .18), R.uniform(-.2, .1)))
                ico_s = 0.11
                pts = [c + Vector(v) * ico_s for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1.2), (0, 0, -1.2))]
                mb.add(pts, [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)], "nut",
                       col=(1, 1, 1) if R.random() < 0.7 else (1.3, 1.2, 0.6))
    # fronds: spiral phyllotaxis, pitch from +70 deg (spear) to -55 deg (old)
    nf = 14 if far else R.randint(26, 32)
    golden = math.radians(137.5)
    for i in range(nf):
        age = i / (nf - 1)                     # 0 young (top), 1 old
        yaw = i * golden + R.uniform(-.15, .15)
        pitch = math.radians(68 - 100 * age ** 0.9 + R.uniform(-8, 8))
        dead = (age > 0.88 and R.random() < 0.55) or (age > 0.75 and R.random() < 0.08)
        L = R.uniform(4.3, 5.6) * (0.55 + 0.45 * min(1, age * 3))
        dvec = Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)))
        side = Vector((-math.sin(yaw), math.cos(yaw), 0))
        base = crown + Vector((math.cos(yaw), math.sin(yaw), 0)) * 0.15 - Vector((0, 0, 0.15 * age))
        # rachis: quadratic with gravity sag (old fronds sag more); dead fronds hang
        sag = (0.10 + 0.42 * age) * L * (2.0 if dead else 1.0)
        ns = 6 if far else 14
        pts = []
        for s in range(ns + 1):
            t = s / ns
            p = base + dvec * (L * t) - Vector((0, 0, sag * t * t))
            if dead:
                p = base + dvec * (L * 0.25 * t) - Vector((0, 0, L * 0.9 * t * t))
            pts.append(p)
        mat = "frond_dry" if dead else "frond"
        # rachis as thin strip (petiole first 18% has no leaflets)
        rr = [0.05 * (1 - 0.8 * s / ns) for s in range(ns + 1)]
        tube(mb, pts, rr, 3 if far else 4, mat)
        # leaflets
        npair = 16 if far else (42 if dead else 62)
        droop = 0.22 + 0.35 * age
        for k in range(npair):
            t = 0.18 + 0.8 * k / (npair - 1)
            fi = t * ns
            i0 = min(int(fi), ns - 1)
            fr = fi - i0
            p = pts[i0].lerp(pts[i0 + 1], fr)
            tng = (pts[i0 + 1] - pts[i0]).normalized()
            sd = tng.cross(Vector((0, 0, 1)))
            if sd.length < 1e-4:
                sd = side
            sd.normalize()
            up = sd.cross(tng).normalized()
            ll = (0.95 * math.sin(math.pi * min(1, (t - 0.1) / 0.95)) + 0.12) * (0.95 + 0.1 * R.random())
            if dead:
                ll *= 0.75
            w = 0.028 if not far else 0.11
            for sgn in (-1, 1):
                # leaflet: V-set (raised 25 deg), swept forward, drooping tip
                lat = (sd * sgn * math.cos(math.radians(25)) + up * math.sin(math.radians(25))).normalized()
                fwd = tng * 0.35
                segs = 1 if far else 3
                ctr = []
                for s in range(segs + 1):
                    u = s / segs
                    q = p + (lat + fwd * u) * (ll * u) - Vector((0, 0, droop * ll * u * u * 0.8))
                    if dead:
                        q = p + (sd * sgn * 0.3 + Vector((0, 0, -1))).normalized() * ll * u
                    ctr.append(q)
                vs = []
                for s, q in enumerate(ctr):
                    u = s / segs
                    ww = w * (1 - 0.85 * u) * (0.6 if u == 0 else 1)
                    vs += [q + tng * ww, q - tng * ww]
                fcs = [(2 * s, 2 * s + 1, 2 * s + 3, 2 * s + 2) for s in range(segs)]
                tint = R.uniform(0.82, 1.15)
                mb.add(vs, fcs, mat, col=(tint, tint, tint * 0.9))
    return mb.build(name, mats)


# ------------------------------------------------------------------ areca palm
def areca(name, seed, height, mats, far=False):
    R = random.Random(seed)
    mb = MB()
    lean = R.uniform(0, 0.06)
    az = R.uniform(0, 6.28)
    top = Vector((math.cos(az) * height * lean, math.sin(az) * height * lean, height))
    path = [Vector((0, 0, -0.2)).lerp(top, i / 12) for i in range(13)]
    tube(mb, path, [0.10 - 0.035 * i / 12 for i in range(13)], 5 if far else 8, "areca_stem",
         ring_dark=None if far else (lambda s: (0.85, 0.85, 0.85) if s % 2 else (1, 1, 1)))
    # green crown shaft
    tube(mb, [top, top + Vector((0, 0, 1.0))], [0.08, 0.06], 6, "areca_leaf", cap=True)
    crown = top + Vector((0, 0, 1.0))
    nf = 6 if far else 9
    for i in range(nf):
        yaw = i * 2.4 + R.uniform(-.2, .2)
        pitch = math.radians(55 - 80 * i / nf)
        L = R.uniform(1.8, 2.4)
        dvec = Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)))
        pts = [crown + dvec * L * t - Vector((0, 0, 0.7 * L * t * t)) for t in [s / 8 for s in range(9)]]
        tube(mb, pts, [0.025] * 9, 3, "areca_leaf")
        npair = 8 if far else 22
        for k in range(npair):
            t = 0.15 + 0.85 * k / npair
            p = pts[0].lerp(pts[-1], t) - Vector((0, 0, 0.7 * L * (t * t - t)))
            tng = dvec
            sd = tng.cross(Vector((0, 0, 1))).normalized()
            ll = 0.55 * math.sin(math.pi * t) + 0.15
            for sgn in (-1, 1):
                q1 = p + (sd * sgn + Vector((0, 0, -0.5))).normalized() * ll
                w = 0.03 if not far else 0.08
                mb.add([p + tng * w, p - tng * w, q1 - tng * w * 0.2, q1 + tng * w * 0.2], [(0, 1, 2, 3)], "areca_leaf")
    return mb.build(name, mats)


# ------------------------------------------------------------------ banana
def banana(name, seed, mats, far=False):
    R = random.Random(seed)
    mb = MB()
    h = R.uniform(2.2, 3.0)
    tube(mb, [Vector((0, 0, -0.1)), Vector((0, 0, h))], [0.14, 0.10], 8, "banana", col=(0.8, 0.8, 0.6))
    for i in range(7 if far else 10):
        yaw = i * 2.4
        pitch = math.radians(R.uniform(10, 60))
        L = R.uniform(1.6, 2.4)
        d = Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)))
        sd = d.cross(Vector((0, 0, 1))).normalized()
        base = Vector((0, 0, h))
        segs = 3 if far else 6
        vs = []
        for s in range(segs + 1):
            t = s / segs
            c = base + d * L * t - Vector((0, 0, 0.6 * L * t * t))
            w = 0.3 * math.sin(math.pi * min(0.98, t * 0.95 + 0.04))
            vs += [c + sd * w - Vector((0, 0, w * 0.25)), c - sd * w - Vector((0, 0, w * 0.25)), c]
        fcs = []
        for s in range(segs):
            a = 3 * s
            fcs += [(a, a + 2, a + 5, a + 3), (a + 2, a + 1, a + 4, a + 5)]
        mb.add(vs, fcs, "banana", col=(R.uniform(.9, 1.1),) * 3)
    return mb.build(name, mats)


# ------------------------------------------------------------------ broadleaf (mango / jackfruit / anjili)
def broadleaf(name, seed, height, crown_w, shape, mats, far=False):
    """shape: 'dome' (mango), 'tall' (jackfruit / anjili), 'spread' (rain tree / Ailanthus-like)."""
    R = random.Random(seed)
    mb = MB()
    trunk_h = height * (0.28 if shape != "tall" else 0.45)
    r0 = 0.12 + 0.013 * height
    tube(mb, [Vector((0, 0, -0.3)), Vector((0, 0, trunk_h * 0.5)), Vector((R.uniform(-.2, .2), R.uniform(-.2, .2), trunk_h))], [r0 * 1.25, r0 * 0.9, r0 * 0.6], 7, "bark")
    crown_c = Vector((0, 0, trunk_h + (height - trunk_h) * 0.5))
    rx = crown_w / 2
    rz = (height - trunk_h) / 2 * (1.25 if shape == "tall" else 1.0)
    if shape == "spread":
        rz *= 0.7
    # branches from trunk top to points on the crown surface
    tips = []
    nb = 5 if far else R.randint(7, 10)
    for b in range(nb):
        a = b / nb * 2 * math.pi + R.uniform(-.3, .3)
        el = R.uniform(-0.1, 0.8)
        tip = crown_c + Vector((math.cos(a) * rx * 0.7 * math.cos(el), math.sin(a) * rx * 0.7 * math.cos(el), rz * 0.6 * math.sin(el)))
        start = Vector((0, 0, trunk_h * R.uniform(0.85, 1.0)))
        mid = start.lerp(tip, 0.5) + Vector((0, 0, R.uniform(0.2, 1.0)))
        pts = bezier(start, mid, mid, tip, 4)
        tube(mb, pts, [r0 * 0.5 * (1 - 0.8 * i / 4) for i in range(5)], 5, "bark")
        tips.append(tip)
    # leaf clumps: many quads distributed in ellipsoid shells around clump centres, denser outside
    nclump = 14 if far else 34
    leaves_per = 26 if far else 260
    for c in range(nclump):
        th = R.uniform(0, 2 * math.pi)
        ph = math.acos(R.uniform(-0.65, 1.0))
        cc = crown_c + Vector((math.sin(ph) * math.cos(th) * rx * 0.62, math.sin(ph) * math.sin(th) * rx * 0.62, math.cos(ph) * rz * 0.62))
        cr = R.uniform(1.3, 1.9) * (crown_w / 8)
        tone = R.uniform(0.75, 1.2)
        for k in range(leaves_per):
            v = Vector((R.gauss(0, 1), R.gauss(0, 1), R.gauss(0, 1))).normalized() * (cr * R.uniform(0.25, 1.0) ** 0.5)
            p = cc + v
            n = (v + Vector((0, 0, 0.6))).normalized()
            s, u = frame(n)
            q = Quaternion(n, R.uniform(0, 6.28))
            s = q @ s
            u = q @ u
            L = 0.42 if not far else 1.1
            W = 0.17 if not far else 0.6
            pts = [p - s * L / 2, p - u * W / 2, p + s * L / 2, p + u * W / 2]
            mb.add(pts, [(0, 1, 2, 3)], "leaf", col=(tone * R.uniform(.9, 1.1),) * 3)
    return mb.build(name, mats)


# ------------------------------------------------------------------ catalogue
PALM_SPECS = [("PALM_A", 11, 15.5, 0.06), ("PALM_B", 12, 18.0, 0.13), ("PALM_C", 13, 21.0, 0.04),
              ("PALM_D", 14, 13.0, 0.18), ("PALM_E", 15, 19.5, 0.09)]
BROAD_SPECS = [("BROAD_DOME_A", 21, 11.0, 10.0, "dome"), ("BROAD_DOME_B", 22, 8.0, 8.0, "dome"),
               ("BROAD_TALL_A", 23, 17.0, 8.0, "tall"), ("BROAD_SPREAD_A", 24, 13.0, 14.0, "spread")]


def build_assets(collection):
    mats = materials()
    out = {}
    def link(ob):
        collection.objects.link(ob)
        out[ob.name] = ob
    for n, s, h, l in PALM_SPECS:
        link(coconut(n, s, h, l, mats))
        link(coconut(n + "_FAR", s, h, l, mats, far=True))
    for n, s, h in (("ARECA_A", 31, 11.0), ("ARECA_B", 32, 13.5)):
        link(areca(n, s, h, mats))
        link(areca(n + "_FAR", s, h, mats, far=True))
    link(banana("BANANA_A", 41, mats))
    link(banana("BANANA_A_FAR", 41, mats, far=True))
    for n, s, h, w, sh in BROAD_SPECS:
        link(broadleaf(n, s, h, w, sh, mats))
        link(broadleaf(n + "_FAR", s, h, w, sh, mats, far=True))
    return out


if __name__ == "__main__":
    import sys
    col = bpy.data.collections.new("ENV_TreeAssets")
    bpy.context.scene.collection.children.link(col)
    obs = build_assets(col)
    for k, ob in obs.items():
        print("TREE", k, len(ob.data.polygons))
