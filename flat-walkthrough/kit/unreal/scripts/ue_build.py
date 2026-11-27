"""Builds the Type G flat level in Unreal from ../import/scene.json (exported by blender/scripts/export_ue.py).

UnrealEditor-Cmd FlatTypeG.uproject -run=pythonscript -script=ue_build.py
Stages: textures -> master materials -> material instances -> meshes (+collision) -> level, actors, lights, player start.
"""
import unreal, json, os, re, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
IMP = os.path.abspath(os.path.join(HERE, "..", "import"))
SCENE = json.load(open(os.path.join(IMP, "scene.json")))
ROOT = "/Game/Flat"
MAP = ROOT + "/Maps/L_FlatTypeG"
AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log_warning("FLATBUILD " + s)


def san(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def import_files(files, dest):
    tasks = []
    for f in files:
        t = unreal.AssetImportTask()
        t.filename = f
        t.destination_path = dest
        t.automated = True
        t.replace_existing = True
        t.save = True
        tasks.append(t)
    AT.import_asset_tasks(tasks)
    return tasks


# ================================================================== textures
TEX = {}


def tex_asset_path(path):
    return ROOT + "/Textures/" + san(os.path.splitext(os.path.basename(path))[0])


def import_textures():
    roles = {}
    for m in SCENE["materials"].values():
        for k in ("D", "N", "R", "M"):
            p = m.get(k)
            if p and os.path.exists(p):
                role = {"D": "color", "N": "normal", "R": "mask", "M": "mask"}[k]
                if roles.get(p) == "color":
                    continue
                roles[p] = role
    for f in os.listdir(os.path.join(IMP, "defaults")):
        p = os.path.join(IMP, "defaults", f)
        roles[p] = "normal" if "Normal" in f else ("mask" if "Mask" in f else "color")
    todo = [p for p in roles if not EAL.does_asset_exist(tex_asset_path(p))]
    # import (Interchange keeps the file stem as asset name)
    for i in range(0, len(todo), 20):
        import_files(todo[i:i + 20], ROOT + "/Textures")
    for p, role in roles.items():
        a = tex_asset_path(p)
        t = unreal.load_asset(a)
        if t is None:
            log("MISSING TEXTURE", p)
            continue
        if role == "normal":
            t.set_editor_property("srgb", False)
            t.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            t.set_editor_property("flip_green_channel", True)   # OpenGL -> DirectX normals
        elif role == "mask":
            t.set_editor_property("srgb", False)
            t.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        EAL.save_loaded_asset(t)
        TEX[p] = t
    log("textures", len(TEX))


# ================================================================== master materials
def expr(mat, cls, x, y, **props):
    e = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def new_material(name, folder=ROOT + "/Materials/Masters"):
    path = folder + "/" + name
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    return AT.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())


def tparam(mat, name, x, y, default, sampler):
    return expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y, parameter_name=name, texture=default, sampler_type=sampler)


def sparam(mat, name, x, y, v):
    return expr(mat, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=v)


def vparam(mat, name, x, y, v):
    return expr(mat, unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name, default_value=unreal.LinearColor(*v))


def build_tex_master(name, masked=False):
    m = new_material(name)
    if masked:
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        m.set_editor_property("two_sided", True)
    W = unreal.load_asset(ROOT + "/Textures/T_Default_White")
    N = unreal.load_asset(ROOT + "/Textures/T_Default_Normal")
    K = unreal.load_asset(ROOT + "/Textures/T_Default_Mask")
    tc = expr(m, unreal.MaterialExpressionTextureCoordinate, -1400, 0)
    uvs = sparam(m, "UVScale", -1400, 120, 1.0)
    uv = expr(m, unreal.MaterialExpressionMultiply, -1200, 40)
    MEL.connect_material_expressions(tc, "", uv, "A")
    MEL.connect_material_expressions(uvs, "", uv, "B")
    d = tparam(m, "BaseColorTex", -900, -300, W, unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    n = tparam(m, "NormalTex", -900, 100, N, unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    r = tparam(m, "RoughTex", -900, 450, K, unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    for t in (d, n, r):
        MEL.connect_material_expressions(uv, "", t, "UVs")
    tint = vparam(m, "Tint", -700, -450, (1, 1, 1, 1))
    bc = expr(m, unreal.MaterialExpressionMultiply, -450, -300)
    MEL.connect_material_expressions(d, "RGB", bc, "A")
    MEL.connect_material_expressions(tint, "", bc, "B")
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    # normal strength: lerp(flat, N, s)
    flat = expr(m, unreal.MaterialExpressionConstant3Vector, -700, 220, constant=unreal.LinearColor(0, 0, 1, 1))
    ns = sparam(m, "NormalStrength", -700, 300, 1.0)
    nl = expr(m, unreal.MaterialExpressionLinearInterpolate, -450, 150)
    MEL.connect_material_expressions(flat, "", nl, "A")
    MEL.connect_material_expressions(n, "RGB", nl, "B")
    MEL.connect_material_expressions(ns, "", nl, "Alpha")
    MEL.connect_material_property(nl, "", unreal.MaterialProperty.MP_NORMAL)
    # roughness: channel mask -> remap
    rm = vparam(m, "RoughMask", -700, 520, (1, 0, 0, 0))
    dot = expr(m, unreal.MaterialExpressionDotProduct, -500, 450)
    MEL.connect_material_expressions(r, "RGB", dot, "A")
    MEL.connect_material_expressions(rm, "RGB", dot, "B")
    rmin = sparam(m, "RoughMin", -500, 560, 0.0)
    rmax = sparam(m, "RoughMax", -500, 640, 1.0)
    rl = expr(m, unreal.MaterialExpressionLinearInterpolate, -300, 450)
    MEL.connect_material_expressions(rmin, "", rl, "A")
    MEL.connect_material_expressions(rmax, "", rl, "B")
    MEL.connect_material_expressions(dot, "", rl, "Alpha")
    MEL.connect_material_property(rl, "", unreal.MaterialProperty.MP_ROUGHNESS)
    met = sparam(m, "Metallic", -300, 650, 0.0)
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    if masked:
        MEL.connect_material_property(d, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_solid_master():
    m = new_material("M_FlatSolid")
    c = vparam(m, "Color", -600, -200, (0.8, 0.8, 0.8, 1))
    MEL.connect_material_property(c, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(sparam(m, "Roughness", -600, 0, 0.5), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(sparam(m, "Metallic", -600, 100, 0.0), "", unreal.MaterialProperty.MP_METALLIC)
    ec = vparam(m, "EmissiveColor", -800, 250, (0, 0, 0, 1))
    es = sparam(m, "EmissiveStrength", -800, 380, 0.0)
    mul = expr(m, unreal.MaterialExpressionMultiply, -500, 300)
    MEL.connect_material_expressions(ec, "RGB", mul, "A")
    MEL.connect_material_expressions(es, "", mul, "B")
    MEL.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_translucent_master(name, two_sided, opacity):
    m = new_material(name)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", two_sided)
    try:
        m.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    except Exception as e:
        log("translucency mode", e)
    c = vparam(m, "Color", -600, -200, (0.9, 0.95, 0.95, 1))
    MEL.connect_material_property(c, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(sparam(m, "Roughness", -600, 0, 0.05), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(sparam(m, "Opacity", -600, 100, opacity), "", unreal.MaterialProperty.MP_OPACITY)
    MEL.connect_material_property(sparam(m, "Specular", -600, 200, 0.5), "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


MASTERS = {}


def build_masters():
    MASTERS["tex"] = build_tex_master("M_FlatTex")
    MASTERS["texmasked"] = build_tex_master("M_FlatTexMasked", masked=True)
    MASTERS["solid"] = build_solid_master()
    MASTERS["glass"] = build_translucent_master("M_FlatGlass", False, 0.12)
    MASTERS["sheer"] = build_translucent_master("M_FlatSheer", True, 0.55)
    log("masters ok")


# ================================================================== material instances
MI = {}


def hex_lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def make_mi(key, d):
    name = "MI_" + san(key)
    folder = ROOT + "/Materials"
    path = folder + "/" + name
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    kind = d["kind"]
    if kind in ("gltf",) and ("glass" in key.lower() or "globe" in key.lower()):
        kind = "glass"
    parent = {"textured": MASTERS["tex"], "gltf": MASTERS["texmasked"] if d.get("masked") else MASTERS["tex"],
              "solid": MASTERS["solid"], "glass": MASTERS["glass"], "sheer": MASTERS["sheer"]}[kind]
    mi = AT.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    S = lambda n, v: MEL.set_material_instance_scalar_parameter_value(mi, n, float(v))
    V = lambda n, v: MEL.set_material_instance_vector_parameter_value(mi, n, unreal.LinearColor(v[0], v[1], v[2], 1.0))
    T = lambda n, p: MEL.set_material_instance_texture_parameter_value(mi, n, TEX[p]) if p in TEX else None
    if kind in ("textured", "gltf"):
        T("BaseColorTex", d.get("D"))
        if d.get("N"):
            T("NormalTex", d["N"])
            S("NormalStrength", d.get("normal_strength", 1.0) if kind == "textured" else 1.0)
        else:
            S("NormalStrength", 0.0)
        S("UVScale", d.get("uv_scale", 1.0))
        if d.get("R"):
            T("RoughTex", d["R"])
            ch = d.get("R_ch", "R") if kind == "gltf" else "R"
            if kind == "gltf" and "_arm_" not in os.path.basename(d["R"]):
                ch = "R"
            V("RoughMask", {"R": (1, 0, 0), "G": (0, 1, 0), "B": (0, 0, 1)}.get(ch, (1, 0, 0)))
            rr = d.get("rough_range", [0, 1])
            S("RoughMin", rr[0]); S("RoughMax", rr[1])
        else:
            V("RoughMask", (1, 0, 0)); S("RoughMin", d.get("rough", 0.5)); S("RoughMax", d.get("rough", 0.5))
        if kind == "textured" and d.get("tint", "#ffffff") != "#ffffff":
            V("Tint", hex_lin(d["tint"]))
        S("Metallic", 0.0 if kind == "textured" else (0.0 if "fan" not in key else 0.6))
    elif kind == "solid":
        V("Color", d.get("color", [0.8, 0.8, 0.8]))
        S("Roughness", d.get("roughness", 0.5))
        S("Metallic", d.get("metallic", 0.0))
        if d.get("emissive_strength", 0) > 0:
            V("EmissiveColor", d.get("emissive", [1, 1, 1]))
            S("EmissiveStrength", d["emissive_strength"] * 3.0)
    elif kind == "glass":
        S("Roughness", d.get("roughness", 0.03))
        if "globe" in key.lower() or "lamp" in key.lower():
            V("Color", (1.0, 0.95, 0.85)); S("Opacity", 0.6)
        elif d.get("roughness", 0) > 0.2:
            S("Opacity", 0.55)
    elif kind == "sheer":
        V("Color", d.get("color", [0.9, 0.88, 0.84]))
        S("Opacity", 0.5)
    EAL.save_loaded_asset(mi)
    MI[san(key)] = mi
    return mi


def build_mis():
    for k, d in SCENE["materials"].items():
        try:
            make_mi(k, d)
        except Exception as e:
            log("MI FAIL", k, e)
    log("material instances", len(MI))


# ================================================================== meshes
MESH = {}


def import_meshes():
    mdir = os.path.join(IMP, "meshes")
    files = sorted(os.path.join(mdir, f) for f in os.listdir(mdir) if f.endswith(".fbx"))
    for i in range(0, len(files), 25):
        import_files(files[i:i + 25], ROOT + "/Meshes")
    sms = unreal.EditorStaticMeshLibrary
    coll_class = {}
    for inst in SCENE["instances"]:
        c = inst["collision"]
        prev = coll_class.get(inst["mesh"])
        coll_class[inst["mesh"]] = c if prev is None else ("complex" if "complex" in (c, prev) else ("box" if "box" in (c, prev) else "none"))
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        sm = unreal.load_asset(ROOT + "/Meshes/" + name)
        if sm is None:
            log("MISSING MESH", name)
            continue
        # materials by slot name
        mats = sm.get_editor_property("static_materials")
        for i, sl in enumerate(mats):
            key = san(str(sl.material_slot_name))
            mi = MI.get(key)
            if mi is None:
                # Interchange may suffix names; try prefix match
                cand = [k for k in MI if key.startswith(k) or k.startswith(key)]
                mi = MI[cand[0]] if cand else None
            if mi:
                sm.set_material(i, mi)
            else:
                log("NO MI for slot", name, key)
        # collision
        cc = coll_class.get(name, "none")
        try:
            sms.remove_collisions(sm)
        except Exception:
            pass
        bs = sm.get_editor_property("body_setup")
        if cc == "complex" and bs:
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        elif cc == "box":
            sms.add_simple_collisions(sm, unreal.ScriptingCollisionShapeType.BOX)
        EAL.save_loaded_asset(sm)
        MESH[name] = sm
    # remove meshes no longer present in the export
    keep = {os.path.splitext(os.path.basename(f))[0] for f in files}
    for a in EAL.list_assets(ROOT + "/Meshes", recursive=False, include_folder=False):
        n = a.split("/")[-1].split(".")[0]
        if n.startswith("SM_") and n not in keep:
            EAL.delete_asset(a)
            log("deleted stale mesh", n)
    # remove auto-created materials/textures that Interchange generated next to meshes
    for a in EAL.list_assets(ROOT + "/Meshes", recursive=True, include_folder=False):
        obj = unreal.load_asset(a)
        if isinstance(obj, (unreal.Material, unreal.MaterialInstanceConstant, unreal.Texture2D)):
            EAL.delete_asset(a)
    log("meshes", len(MESH))


# ================================================================== level
def to_ue(mat):
    """Blender 4x4 world matrix (metres, RH) -> UE location (cm), rotator, scale (Y mirrored)."""
    M = mat
    loc = unreal.Vector(M[0][3] * 100, -M[1][3] * 100, M[2][3] * 100)
    cols = [[M[r][c] for r in range(3)] for c in range(3)]
    sc = [math.sqrt(sum(v * v for v in col)) for col in cols]
    # mirrored basis: S R S  -> column c of R mirrored and the Y column negated
    x = [cols[0][0] / sc[0], -cols[0][1] / sc[0], cols[0][2] / sc[0]]
    z = [cols[2][0] / sc[2], -cols[2][1] / sc[2], cols[2][2] / sc[2]]
    rot = unreal.MathLibrary.make_rot_from_xz(unreal.Vector(*x), unreal.Vector(*z))
    return loc, rot, unreal.Vector(sc[0], sc[1], sc[2])


def build_level():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if EAL.does_asset_exist(MAP):
        les.load_level(MAP)
        for a in eas.get_all_level_actors():
            if not isinstance(a, (unreal.WorldSettings, unreal.Brush)):
                eas.destroy_actor(a)
    else:
        if not les.new_level(MAP):
            raise RuntimeError("could not create " + MAP)
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    log("building into", w.get_path_name())
    if not w.get_path_name().startswith(MAP):
        raise RuntimeError("wrong world " + w.get_path_name())
    n = 0
    for inst in SCENE["instances"]:
        sm = MESH.get(inst["mesh"])
        if sm is None:
            continue
        loc, rot, scale = to_ue(inst["matrix"])
        a = eas.spawn_actor_from_object(sm, loc, rot)
        if a is None:
            continue
        a.set_actor_scale3d(scale)
        a.set_actor_label(inst["name"])
        a.set_folder_path(inst["collection"])
        comp = a.static_mesh_component
        comp.set_mobility(unreal.ComponentMobility.STATIC)
        if inst["collision"] == "none":
            comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            comp.set_collision_profile_name("NoCollision")
        if not inst.get("shadow", True):
            comp.set_cast_shadow(False)
        n += 1
    log("actors", n)
    # ---------------- lights
    for L in SCENE["lights"]:
        loc = unreal.Vector(L["loc"][0] * 100, -L["loc"][1] * 100, L["loc"][2] * 100)
        d = unreal.Vector(L["dir"][0], -L["dir"][1], L["dir"][2])
        rot = unreal.MathLibrary.make_rot_from_x(d)
        col = unreal.LinearColor(*L["color"], 1.0)
        if L["type"] == "SUN":
            a = eas.spawn_actor_from_class(unreal.DirectionalLight, loc, rot)
            lc = a.light_component
            lc.set_intensity(40000.0)
            lc.set_light_color(unreal.LinearColor(1.0, 0.95, 0.88, 1.0))
            lc.set_editor_property("atmosphere_sun_light", True)
            lc.set_editor_property("light_source_angle", 0.6)
        elif L["type"] == "SPOT":
            a = eas.spawn_actor_from_class(unreal.SpotLight, loc, rot)
            lc = a.light_component
            lc.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
            lc.set_intensity(L["energy"] * 28.0)
            lc.set_editor_property("outer_cone_angle", min(80.0, L["spot_size"] / 2))
            lc.set_editor_property("inner_cone_angle", min(60.0, L["spot_size"] / 2 * (1 - L["spot_blend"])))
            lc.set_editor_property("attenuation_radius", 650.0)
            lc.set_editor_property("source_radius", 3.0)
            lc.set_editor_property("use_temperature", True)
            lc.set_editor_property("temperature", 3200.0)
        else:
            a = eas.spawn_actor_from_class(unreal.PointLight, loc, rot)
            lc = a.light_component
            lc.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
            lc.set_intensity(L["energy"] * 22.0)
            lc.set_editor_property("attenuation_radius", 500.0)
            lc.set_editor_property("source_radius", max(1.0, L["radius"] * 100))
            lc.set_editor_property("use_temperature", True)
            lc.set_editor_property("temperature", 3000.0)
            if "Passage" in L["name"]:
                lc.set_cast_shadows(False)
        a.set_actor_label(L["name"])
        a.set_folder_path("03_Lighting")
        lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    # ---------------- sky, fog, sky light, post process
    sky = eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    sky.set_folder_path("03_Lighting")
    sl = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(800, -270, 600), unreal.Rotator(0, 0, 0))
    slc = sl.light_component
    slc.set_mobility(unreal.ComponentMobility.MOVABLE)
    slc.set_editor_property("real_time_capture", True)
    slc.set_intensity(1.0)
    sl.set_folder_path("03_Lighting")
    fog = eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, -3000), unreal.Rotator(0, 0, 0))
    fc = fog.component
    fc.set_editor_property("fog_density", 0.004)
    fog.set_folder_path("03_Lighting")
    try:
        vc = eas.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        vc.set_folder_path("03_Lighting")
    except Exception as e:
        log("cloud", e)
    pp = eas.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(800, -270, 140), unreal.Rotator(0, 0, 0))
    pp.set_editor_property("unbound", True)
    s = pp.settings
    for prop, val in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM),
                      ("override_auto_exposure_min_brightness", True), ("auto_exposure_min_brightness", 4.0),
                      ("override_auto_exposure_max_brightness", True), ("auto_exposure_max_brightness", 11.0),
                      ("override_auto_exposure_bias", True), ("auto_exposure_bias", 0.6),
                      ("override_auto_exposure_speed_up", True), ("auto_exposure_speed_up", 2.0),
                      ("override_auto_exposure_speed_down", True), ("auto_exposure_speed_down", 1.5),
                      ("override_bloom_intensity", True), ("bloom_intensity", 0.25),
                      ("override_vignette_intensity", True), ("vignette_intensity", 0.25),
                      ("override_lumen_final_gather_quality", True), ("lumen_final_gather_quality", 2.0),
                      ("override_lumen_scene_detail", True), ("lumen_scene_detail", 2.0),
                      ("override_lumen_reflection_quality", True), ("lumen_reflection_quality", 1.0),
                      ("override_white_temp", True), ("white_temp", 5600.0)):
        try:
            s.set_editor_property(prop, val)
        except Exception as e:
            log("pp", prop, e)
    pp.set_editor_property("settings", s)
    pp.set_folder_path("03_Lighting")
    # ---------------- player start + nav bounds
    sp = SCENE["markers"].get("PlayerStart_Marker", {"loc": [15.2, 0.6, 0.9], "yaw": 90})
    ps = eas.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(sp["loc"][0] * 100, -sp["loc"][1] * 100, 100),
                                    unreal.Rotator(0, 0, -sp["yaw"]))
    ps.set_actor_label("PlayerStart_Entrance")
    nb = eas.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(800, -270, 140), unreal.Rotator(0, 0, 0))
    nb.set_actor_scale3d(unreal.Vector(10, 5, 2))
    nb.set_folder_path("04_Gameplay")
    les.save_current_level()
    log("level saved", MAP)


def main():
    t0 = time.time()
    stages = os.environ.get("FLAT_STAGES", "assets,level").split(",")
    if "assets" in stages:
        import_textures()
        build_masters()
        build_mis()
        import_meshes()
    if "level" in stages:
        for k, d in SCENE["materials"].items():
            mi = unreal.load_asset(ROOT + "/Materials/MI_" + san(k))
            if mi:
                MI[san(k)] = mi
        for f in os.listdir(os.path.join(IMP, "meshes")):
            n = os.path.splitext(f)[0]
            sm = unreal.load_asset(ROOT + "/Meshes/" + n)
            if sm:
                MESH[n] = sm
        build_level()
    log("done in %.0fs" % (time.time() - t0))
    open(os.path.join(HERE, "ue_build_report_%s.txt" % "_".join(stages)), "w").write("\n".join(LOG))
    if os.environ.get("FLAT_QUIT") == "1":
        unreal.SystemLibrary.quit_editor()


main()
