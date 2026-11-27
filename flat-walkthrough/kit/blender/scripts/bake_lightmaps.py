"""Bakes the flat's lighting with Cycles into per-object lightmaps for the mobile (Android) build.

For every exported mesh it adds a second UV channel (LightmapUV, unique non-overlapping islands) and re-exports the
FBX (same asset names as export_ue.py, so Unreal re-imports in place). Then it bakes DIFFUSE direct+indirect lighting
(sun, sky, downlights, coves, emissive strips, all bounces) for every instance into its own float lightmap.

Blender -b flat_typeG.blend -P bake_lightmaps.py -- <unreal/import dir> [samples=512] [texels_per_m=80] [only_regex]

Writes <out>/meshes/*.fbx (2 UV sets), <out>/lightmaps/raw/LM_*.npy (float16 RGB) and <out>/lightmaps/lightmaps.json.
The .blend is not saved.
"""
import bpy, json, os, re, sys, math, time
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
SAMPLES = int(argv[1]) if len(argv) > 1 else 512
DENSITY = float(argv[2]) if len(argv) > 2 else 80.0
ONLY = re.compile(argv[3]) if len(argv) > 3 and argv[3] else None
MESH_DIR = os.path.join(OUT, "meshes")
RAW_DIR = os.path.join(OUT, "lightmaps", "raw")
os.makedirs(RAW_DIR, exist_ok=True)
MARGIN_PX = 6
DENSE = re.compile(r"potted_plant|ceiling_fan")     # Poly Haven assets whose own UV0 (unique, 0-1) is used as the lightmap UV
T0 = time.time()


def log(*a):
    print("BAKE [%5.0fs]" % (time.time() - T0), *a, flush=True)


def sanitize(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


sc = bpy.context.scene
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_adaptive_sampling = False
sc.cycles.sample_clamp_indirect = 8.0          # same as the approved preview renders
sc.cycles.max_bounces = 8
sc.cycles.transparent_max_bounces = 16
bk = sc.render.bake
bk.use_pass_direct, bk.use_pass_indirect, bk.use_pass_color = True, True, False
bk.margin, bk.margin_type = MARGIN_PX, "EXTEND"
bk.target = "IMAGE_TEXTURES"
bk.use_clear = True

# ------------------------------------------------------------------ which objects
dg = bpy.context.evaluated_depsgraph_get()
insts = []
for ob in list(sc.objects):
    if ob.type != "MESH" or ob.hide_render:
        continue
    cols = [c.name for c in ob.users_collection]
    if "99_AssetSource" in cols or ob.name.startswith("PLAN_"):
        continue
    key = ("D:" + ob.data.name) if (not ob.modifiers and ob.data.users > 1) else ("O:" + ob.name)   # = export_ue.py
    insts.append((ob, key, "SM_" + sanitize(key[2:]), cols))


def is_glass(m):
    if not m or not m.use_nodes:
        return False
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    return bool(b and b.inputs["Transmission Weight"].default_value > 0.5)


def is_emissive_only(m):
    if not m or not m.use_nodes:
        return False
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    return bool(b and b.inputs["Emission Strength"].default_value > 1.0 and not b.inputs["Base Color"].is_linked
                and max(b.inputs["Base Color"].default_value[:3]) < 0.05)


def bake_target(ob, cols):
    if any(c in ("LGT_Emissive",) for c in cols):
        return False
    mats = [s.material for s in ob.material_slots if s.material]
    if not mats or all(is_glass(m) or is_emissive_only(m) for m in mats):
        return False
    return True


targets = [(ob, key, asset) for ob, key, asset, cols in insts if bake_target(ob, cols) and (not ONLY or ONLY.search(ob.name))]
log("instances", len(insts), "bake targets", len(targets), "samples", SAMPLES, "density", DENSITY)

# ------------------------------------------------------------------ lightmap UVs + FBX per unique mesh
tmp_col = bpy.data.collections.new("__lm_tmp")
sc.collection.children.link(tmp_col)
LM_MESH, RES = {}, {}


def area_world(me, mw):
    s = mw.to_scale()
    k = (abs(s.x * s.y) + abs(s.y * s.z) + abs(s.x * s.z)) / 3.0
    return sum(p.area for p in me.polygons) * k


def unwrap(me, res):
    o = bpy.data.objects.new("__unwrap", me)
    tmp_col.objects.link(o)
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    sc.tool_settings.use_uv_select_sync = True              # mesh selection = UV selection (headless, no UV editor)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, area_weight=0.0, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, scale=True, margin_method="FRACTION",
                            margin=min(0.03, 2.0 / res), shape_method="AABB")
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.data.objects.remove(o)
    # guard: if the packer overflowed the tile, scale uniformly back into 0-1 (keeps a small border)
    uv = me.uv_layers["LightmapUV"]
    a = np.empty(len(me.loops) * 2, np.float32)
    uv.data.foreach_get("uv", a)
    a = a.reshape(-1, 2)
    lo, hi = a.min(axis=0), a.max(axis=0)
    if a.size and (lo.min() < 0 or hi.max() > 1):
        b = 1.0 / res * 2
        k = (1 - 2 * b) / max(hi[0] - lo[0], hi[1] - lo[1], 1e-6)
        a = (a - lo) * k + b
        uv.data.foreach_set("uv", a.ravel())


for ob, key, asset in targets:
    if key in LM_MESH:
        continue
    eo = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, preserve_all_data_layers=True, depsgraph=dg)
    if len(me.polygons) == 0:
        continue
    while len(me.uv_layers) > 1:                    # keep the material UV as channel 0
        me.uv_layers.remove(me.uv_layers[-1])
    if len(me.uv_layers) == 0:
        me.uv_layers.new(name="UVMap")
    lm = me.uv_layers.new(name="LightmapUV")
    me.uv_layers.active = lm
    a = area_world(me, ob.matrix_world)
    res = int(max(64, min(2048, 2 ** round(math.log2(max(1.0, math.sqrt(a) * DENSITY))))))
    uv0 = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[0].data.foreach_get("uv", uv0)
    if DENSE.search(asset) and uv0.size and uv0.min() >= 0 and uv0.max() <= 1:
        res = 256          # plants / fan: thousands of tiny islands would fall below a texel; their own 0-1 UVs serve as lightmap UVs
    else:
        unwrap(me, res)
    uvs = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["LightmapUV"].data.foreach_get("uv", uvs)        # re-fetch: references go stale across edit mode
    if uvs.size and (uvs.min() < -0.01 or uvs.max() > 1.01):
        log("WARN lightmap UVs outside 0-1:", ob.name, uvs.min(), uvs.max())
    me.uv_layers[0].active_render = True                # materials sample channel 0 ...
    me.uv_layers.active = me.uv_layers["LightmapUV"]   # ... but Cycles bakes into the *active* UV map
    LM_MESH[key], RES[key] = me, res
    # FBX with both UV sets, identical options to export_ue.py
    tmp = bpy.data.objects.new(asset, me)
    tmp_col.objects.link(tmp)
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    tmp.select_set(True)
    bpy.context.view_layer.objects.active = tmp
    bpy.ops.export_scene.fbx(filepath=os.path.join(MESH_DIR, asset + ".fbx"), use_selection=True, apply_unit_scale=True,
                             global_scale=1.0, axis_forward="-Z", axis_up="Y", object_types={"MESH"},
                             use_mesh_modifiers=False, mesh_smooth_type="FACE", use_tspace=True, add_leaf_bones=False,
                             bake_anim=False, path_mode="STRIP", embed_textures=False)
    bpy.data.objects.remove(tmp)
log("unwrapped + exported", len(LM_MESH), "meshes; total lightmap texels %.1f MP" %
    (sum(RES[k] ** 2 for _, k, _ in targets if k in RES) / 1e6))

# ------------------------------------------------------------------ bake setup: swap in the UV'd meshes, per-object materials
images = {}
for ob, key, asset in targets:
    if key not in LM_MESH:
        continue
    slots_mats = [s.material for s in ob.material_slots]
    ob.modifiers.clear()
    ob.data = LM_MESH[key].copy()          # single user: Cycles does not bake linked duplicates (shared mesh data)
    res = RES[key]
    img = bpy.data.images.new("LM_" + sanitize(ob.name), res, res, alpha=False, float_buffer=True)
    images[ob.name] = (img, res, asset)
    for i, s in enumerate(ob.material_slots):
        src = slots_mats[i] if i < len(slots_mats) else s.material
        if src is None:
            continue
        m = src.copy()                                      # per-object copy: each object bakes into its own image
        s.link = "OBJECT"
        s.material = m
        m.use_nodes = True
        nt = m.node_tree
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED" and not n.inputs["Metallic"].is_linked:
                n.inputs["Metallic"].default_value = 0.0      # metals bake their diffuse light too (UE adds reflections)
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = img
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = "LightmapUV"
        nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
        for n in nt.nodes:
            n.select = False
        tn.select = True
        nt.nodes.active = tn

# ------------------------------------------------------------------ glass lets the light through
# Cycles shadow rays cannot pass refractive glass, so with real glass no direct sun reaches the rooms.
# For the bake every glass material becomes a nearly invisible transparent surface (Unreal renders the glass itself).
nglass = 0
for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED" and n.inputs["Transmission Weight"].default_value > 0.5:
            n.inputs["Transmission Weight"].default_value = 0.0
            n.inputs["Alpha"].default_value = 0.04
            nglass += 1
log("glass materials made light-transparent:", nglass)

# match the Mac (Lumen) balance: there the sun is far stronger relative to the lamps, and translucent sheer curtains
# cast no shadow. SUN_SCALE / SKY_SCALE / SHEER_ALPHA are bake-only settings (the .blend is not saved).
SUN_SCALE = float(os.environ.get("FLAT_SUN_SCALE", "3.0"))
SKY_SCALE = float(os.environ.get("FLAT_SKY_SCALE", "2.0"))
SHEER_ALPHA = float(os.environ.get("FLAT_SHEER_ALPHA", "0.25"))
for o in sc.objects:
    if o.type == "LIGHT" and o.data.type == "SUN":
        o.data.energy *= SUN_SCALE
if sc.world and sc.world.use_nodes:
    for n in sc.world.node_tree.nodes:
        if n.type == "BACKGROUND":
            n.inputs["Strength"].default_value *= SKY_SCALE
sheer = bpy.data.materials.get("M_Curtain_Sheer")
if sheer:
    for n in sheer.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Alpha"].default_value = SHEER_ALPHA
log("sun x%.1f, sky x%.1f, sheer alpha %.2f" % (SUN_SCALE, SKY_SCALE, SHEER_ALPHA))

# ------------------------------------------------------------------ bake in batches
names = list(images)
FAILED = []
BATCH = 100
for i in range(0, len(names), BATCH):
    batch = [sc.objects[n] for n in names[i:i + BATCH]]
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    for o in batch:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = batch[0]
    t = time.time()
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=MARGIN_PX, margin_type="EXTEND",
                        use_clear=True, target="IMAGE_TEXTURES")
    log("baked batch %d-%d of %d in %.0fs" % (i, i + len(batch), len(names), time.time() - t))
    for o in batch:
        img, res, asset = images[o.name]
        if len(img.pixels) != res * res * 4:
            log("WARN no pixels for", o.name, img.name, len(img.pixels), img.size[:], img.has_data)
            FAILED.append(o.name)
            continue
        px = np.empty(res * res * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        np.save(os.path.join(RAW_DIR, img.name + ".npy"), px.reshape(res, res, 4)[:, :, :3].astype(np.float16))

manifest = {n: {"tex": images[n][0].name, "res": images[n][1], "mesh": images[n][2]} for n in names if n not in FAILED}
mf = os.path.join(OUT, "lightmaps", "lightmaps.json")
if ONLY and os.path.exists(mf):
    old = json.load(open(mf))
    old.update(manifest)
    manifest = old
json.dump(manifest, open(mf, "w"), indent=1)
log("done:", len(manifest), "lightmaps; failed:", FAILED)
