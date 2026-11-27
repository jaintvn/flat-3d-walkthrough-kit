"""Preview renders (Cycles, Metal GPU).

Blender -b flat_typeG.blend -P render_previews.py -- <outdir> <view,view,...|all> [samples] [scale%]
"""
import bpy, sys, os, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout

argv = sys.argv[sys.argv.index("--") + 1:]
OUTDIR = argv[0]
VIEWS = argv[1].split(",") if len(argv) > 1 else ["all"]
SAMPLES = int(argv[2]) if len(argv) > 2 else 96
SCALE = int(argv[3]) if len(argv) > 3 else 100
C = 0.01
os.makedirs(OUTDIR, exist_ok=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- engine
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.sample_clamp_indirect = 8.0
sc.cycles.max_bounces = 8
sc.cycles.transparent_max_bounces = 16
sc.view_settings.view_transform = "AgX"
try:
    sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 92
sc.view_settings.exposure = 0.35

# interior cameras: (name, eye xyz cm, target xyz cm, lens mm)
CAMS = {
    "living":   ((880, 55, 150), (1589, 210, 115), 16),
    "dining":   ((1540, 90, 150), (930, 360, 120), 16),
    "kitchen":  ((1505, 398, 160), (1250, 545, 110), 14),
    "bed1":     ((322, 300, 150), (110, 20, 95), 15),
    "bed1b":    ((60, 120, 150), (360, 330, 120), 16),
    "bed2":     ((425, 262, 150), (732, 460, 100), 15),
    "foyer":    ((560, 100, 150), (1500, 60, 120), 16),
    "toilet2":  ((758, 448, 150), (894, 255, 100), 13),
    "toilet1":  ((175, 412, 150), (330, 552, 100), 13),
    "vanity":   ((840, 20, 150), (819, 205, 120), 18),
    "balcony2": ((1060, 300, 150), (1060, 572, 100), 16),
}
OVERHEAD_HIDE = ["ARCH_Ceilings", "ARCH_FalseCeiling", "LGT_Emissive", "LGT_Fixtures"]
OVERHEAD_OBJ = ["ARCH_SlabAbove", "CTX_PassageCeiling", "CTX_Facade", "LIV_CeilingFan", "BR1_CeilingFan", "BR2_CeilingFan",
                "DIN_Pendant", "KIT_Chimney", "KIT_WallCabinets", "BR2_Pendant_0", "BR2_Pendant_1"]


def set_hidden(names_coll, names_obj, hide):
    for cn in names_coll:
        c = bpy.data.collections.get(cn)
        if c:
            for o in c.all_objects:
                o.hide_render = hide
    for on in names_obj:
        o = bpy.data.objects.get(on)
        if o:
            o.hide_render = hide


def look_cam(name, eye, tgt, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.05
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    e, t = Vector(eye) * C, Vector(tgt) * C
    d = t - e
    yaw = math.atan2(d.y, d.x) - math.pi / 2
    ob.location = e
    ob.rotation_euler = (math.radians(90), 0, yaw)  # level camera -> straight verticals
    # vertical shift to frame the target height
    horiz = Vector((d.x, d.y)).length
    cd.shift_y = max(-0.3, min(0.3, (d.z / horiz) * (lens / 36) * 0.9))
    return ob


def render(name, cam, res=(1600, 1000)):
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = SCALE
    sc.render.filepath = os.path.join(OUTDIR, name + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", sc.render.filepath)


def plan_caps(z=200.0):
    """Dark section caps for walls cut at height z (cm)."""
    me = bpy.data.meshes.new("PLAN_Caps")
    verts, faces = [], []
    for name, x0, x1, y0, y1, ops, h in layout.W:
        ax = "x" if (x1 - x0) >= (y1 - y0) else "y"
        a0, a1 = (x0, x1) if ax == "x" else (y0, y1)
        cuts = sorted([(max(a0, o[0]), min(a1, o[1])) for o in ops if o[2] < z < o[3]])
        segs, cur = [], a0
        for c0, c1 in cuts:
            if c0 > cur:
                segs.append((cur, c0))
            cur = max(cur, c1)
        if cur < a1:
            segs.append((cur, a1))
        for s0, s1 in segs:
            if ax == "x":
                q = [(s0, y0), (s1, y0), (s1, y1), (s0, y1)]
            else:
                q = [(x0, s0), (x1, s0), (x1, s1), (x0, s1)]
            i = len(verts)
            verts += [(px * C, py * C, z * C) for px, py in q]
            faces.append((i, i + 1, i + 2, i + 3))
    # external duct
    for (x0, x1, y0, y1) in ((265, 410, 572, 650),):
        i = len(verts)
        verts += [(x0 * C, y0 * C, z * C), (x1 * C, y0 * C, z * C), (x1 * C, y1 * C, z * C), (x0 * C, y1 * C, z * C)]
        faces.append((i, i + 1, i + 2, i + 3))
    me.from_pydata(verts, [], faces)
    m = bpy.data.materials.new("PLAN_Cap")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
    b.inputs["Roughness"].default_value = 1
    me.materials.append(m)
    ob = bpy.data.objects.new("PLAN_Caps", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def furniture_caps(z=200.0):
    """Section caps for tall furniture cut by the plan plane (wardrobes etc.)."""
    import bmesh
    me = bpy.data.meshes.new("PLAN_FCaps")
    verts, faces = [], []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.hide_render or not o.users_collection:
            continue
        if not any(c.name.startswith("INT_") for c in o.users_collection):
            continue
        bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
        zmin, zmax = min(v.z for v in bb), max(v.z for v in bb)
        if zmin < z * C < zmax and (zmax - zmin) > 1.5:
            x0, x1 = min(v.x for v in bb), max(v.x for v in bb)
            y0, y1 = min(v.y for v in bb), max(v.y for v in bb)
            i = len(verts)
            verts += [(x0, y0, z * C), (x1, y0, z * C), (x1, y1, z * C), (x0, y1, z * C)]
            faces.append((i, i + 1, i + 2, i + 3))
    me.from_pydata(verts, [], faces)
    m = bpy.data.materials.new("PLAN_FCap")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.10, 0.06, 1)
    me.materials.append(m)
    ob = bpy.data.objects.new("PLAN_FCaps", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def lights_on(flag):
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.name != "LGT_Sun":
            o.hide_render = not flag


def top_view():
    set_hidden(OVERHEAD_HIDE, OVERHEAD_OBJ, True)
    caps = plan_caps(200)
    fcaps = furniture_caps(200)
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    lights_on(False)
    sun = bpy.data.objects["LGT_Sun"]
    old = tuple(sun.rotation_euler)
    sun.rotation_euler = (math.radians(12), 0, math.radians(200))
    sun.data.energy = 3.5
    w = sc.world.node_tree.nodes["Background"]
    ws = w.inputs["Strength"].default_value
    w.inputs["Strength"].default_value = 0.6
    cd = bpy.data.cameras.new("CAM_Top")
    cd.type = "ORTHO"
    X0, X1, Y0, Y1 = -60, 1840, -280, 680
    cd.ortho_scale = (X1 - X0) * C
    cd.clip_start = 10 - 2.0
    cd.clip_end = 10.3
    ob = bpy.data.objects.new("CAM_Top", cd)
    sc.collection.objects.link(ob)
    ob.location = ((X0 + X1) / 2 * C, (Y0 + Y1) / 2 * C, 10)
    W = 2850
    H = int(W * (Y1 - Y0) / (X1 - X0))
    sky_col = sc.world.node_tree.nodes.get("Sky Texture")
    lnk = [l for l in sc.world.node_tree.links if l.to_node == w]
    for l in lnk:
        sc.world.node_tree.links.remove(l)
    w.inputs["Color"].default_value = (1, 1, 1, 1)
    sc.render.filepath = os.path.join(OUTDIR, "00_top_plan")
    sc.camera = ob
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = SCALE
    bpy.ops.render.render(write_still=True)
    print("RENDERED top")
    if sky_col:
        sc.world.node_tree.links.new(sky_col.outputs["Color"], w.inputs["Color"])
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.color_mode = "RGB"
    bpy.data.objects.remove(fcaps)
    with open(os.path.join(OUTDIR, "00_top_plan.txt"), "w") as f:
        f.write("%d %d %d %d %d %d\n" % (X0, X1, Y0, Y1, W, H))
    # restore
    bpy.data.objects.remove(caps)
    sun.rotation_euler = old
    sun.data.energy = 4.0
    w.inputs["Strength"].default_value = ws
    set_hidden(OVERHEAD_HIDE, OVERHEAD_OBJ, False)
    lights_on(True)


def iso_view():
    set_hidden(OVERHEAD_HIDE, OVERHEAD_OBJ + ["CTX_Buildings", "CTX_Trees"], True)
    cd = bpy.data.cameras.new("CAM_Iso")
    cd.lens = 30
    ob = bpy.data.objects.new("CAM_Iso", cd)
    sc.collection.objects.link(ob)
    eye = Vector((420, 1250, 1050)) * C
    tgt = Vector((820, 240, 0)) * C
    ob.location = eye
    ob.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
    render("01_cutaway_overview", ob, (1800, 1100))
    set_hidden(OVERHEAD_HIDE, OVERHEAD_OBJ + ["CTX_Buildings", "CTX_Trees"], False)


todo = list(CAMS.keys()) + ["top", "iso"] if VIEWS == ["all"] else VIEWS
for v in todo:
    if v == "top":
        top_view()
    elif v == "iso":
        iso_view()
    else:
        eye, tgt, lens = CAMS[v]
        cam = look_cam("CAM_" + v, eye, tgt, lens)
        render("view_" + v, cam)
