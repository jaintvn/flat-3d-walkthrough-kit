"""Mobile (Android) variant of the Type G level with lighting baked in Blender Cycles.

Lightmass does not run on this Mac (UE 5.8 installed build), so the lighting is baked by
blender/scripts/bake_lightmaps.py + denoise_lightmaps.py into one RGBM lightmap per object (UV channel 1).
On mobile every baked surface is shaded as  emissive = albedo x lightmap  (no runtime lights at all), plus
specular reflections from per-room reflection captures. Glass and LED strips keep their normal materials.

Stages (env FLAT_STAGES, comma separated):
  meshfix    Nanite off on all meshes, lightmap UV = channel 1 (from Blender), no UE-generated lightmap UVs
  lightmaps  import ../import/lightmaps/png/*.png -> /Game/Flat/Lightmaps
  materials  baked masters + baked copies of every slot material instance
  skycap     on the Lumen level: six sky-only HDR views -> ../import/lightmaps/sky_*.exr (GUI; own session);
             blender/scripts/sky_panorama.py stitches them into sky_panorama.png, imported by the lightmaps stage
  copy       L_FlatTypeG -> L_FlatTypeG_Mobile (Save As; run in its own session)
  level      on L_FlatTypeG_Mobile: per-actor lightmap MIs, no lights, reflection captures, exposure
  shots      game-view screenshots of the mobile level -> previews/mobile_editor/ (run in a later session)
Commandlet is fine for meshfix/lightmaps/materials; copy and level need the GUI editor (init_unreal.py hook).
Env FLAT_BAKED_SCALE (default 1.0) multiplies the decoded lightmaps; FLAT_EXPOSURE_BIAS (default 0.35, = Blender).
"""
import unreal, os, math, json, time, re

HERE = os.path.dirname(os.path.abspath(__file__))
# FLAT_VARIANT (e.g. SemiFurnished, Unfurnished; empty = furnished) selects the Lumen source level
# L_FlatTypeG[_<Variant>], the mobile level L_FlatTypeG[_<Variant>]_Mobile, the import dir import[_<variant>]
# (baked from that variant's .blend) and its own lightmap / per-actor material folders, so variants never overwrite
# each other. Meshes, textures and the baked master materials are shared.
VARIANT = os.environ.get("FLAT_VARIANT", "").strip()
_SFX = ("_" + VARIANT) if VARIANT else ""
IMP = os.path.abspath(os.path.join(HERE, "..", "import" + _SFX.lower()))
ROOT = "/Game/Flat"
MAP = ROOT + "/Maps/L_FlatTypeG" + _SFX
MAP_M = ROOT + "/Maps/L_FlatTypeG" + _SFX + "_Mobile"
LM_FOLDER = ROOT + "/Lightmaps" + _SFX
BAKED_FOLDER = ROOT + "/Materials/Baked"
ACTOR_FOLDER = ROOT + "/Materials/PerActor" + _SFX
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
LOG = []
STAGES = os.environ.get("FLAT_STAGES", "meshfix,lightmaps,materials").split(",")
RANGE = 4.0                                            # lightmap range used by denoise_lightmaps.py (sRGB, L / RANGE)
BAKED_SCALE = float(os.environ.get("FLAT_BAKED_SCALE", "1.0"))
EXPOSURE_BIAS = float(os.environ.get("FLAT_EXPOSURE_BIAS", "-0.3"))
# Mac (Lumen) look: warm 3000-3200 K lamps + warm bounce, deeper shadows. Interior lightmaps get a warm tint (sky and
# outdoor context stay neutral); post-process contrast/saturation like the Lumen frames. Measured at the spawn view.
INTERIOR_TINT = tuple(float(x) for x in os.environ.get("FLAT_INTERIOR_TINT", "1.13,0.98,0.84").split(","))
CONTRAST = float(os.environ.get("FLAT_CONTRAST", "1.3"))
SATURATION = float(os.environ.get("FLAT_SATURATION", "1.08"))
# fixed exposure: on the mobile renderer auto exposure locks onto the bright windows/sky and the rooms go black.
# 1.2 EV ~ the per-room average of the Lumen (auto-exposed) Mac build over the range of the baked values (Blender units, ~0.05-2)
AE = (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
      ("override_auto_exposure_apply_physical_camera_exposure", True), ("auto_exposure_apply_physical_camera_exposure", False),
      ("override_auto_exposure_min_brightness", True), ("auto_exposure_min_brightness", -3.0),
      ("override_auto_exposure_max_brightness", True), ("auto_exposure_max_brightness", 3.0),
      ("override_auto_exposure_bias", True), ("auto_exposure_bias", EXPOSURE_BIAS),
      ("override_auto_exposure_speed_up", True), ("auto_exposure_speed_up", 2.0),
      ("override_auto_exposure_speed_down", True), ("auto_exposure_speed_down", 1.5))
SKY_SUN_LUX = float(os.environ.get("FLAT_SKY_SUN", "6.0"))
# the downlights/pendants stay in the mobile level as movable *specular-only* lights (diffuse is baked): Mac-like
# highlights on marble, quartz and lacquer. Their Lumen-level intensities are scaled down to the mobile exposure.
SPEC_LIGHT_SCALE = float(os.environ.get("FLAT_SPEC_LIGHT_SCALE", "0.035"))
SKY_PANO = LM_FOLDER + "/T_MacSkyPanorama"             # the Mac build's sky (atmosphere + clouds): skycap stage + sky_panorama.py
SKY_TARGET = float(os.environ.get("FLAT_SKY_TARGET", "1.2"))   # mean sky brightness in mobile units
FOG_COLOR = tuple(float(x) for x in os.environ.get("FLAT_FOG_COLOR", "1.25,1.4,1.65").split(","))
FOG_DENSITY = float(os.environ.get("FLAT_FOG_DENSITY", "0.02"))
# per-room exposure (EV on top of EXPOSURE_BIAS): the Mac build's auto exposure brightens the smaller rooms relative to
# the living/dining hall (measured from same-viewpoint Lumen vs baked frames); blended post-process volumes reproduce it.
ROOM_EV = {"Kitchen": 1.0, "Foyer": 1.1, "Bed1Entry": 0.9, "Bed1": 0.8, "Bed2": 0.8, "Toilet1": 0.9, "Toilet2": 0.9, "Vanity": 0.7}
_mf = os.path.join(IMP, "lightmaps", "lightmaps.json")
MANIFEST = json.load(open(_mf)) if os.path.exists(_mf) else {}


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log_warning("FLATMOBILE " + s)


def san(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


# ================================================================== meshes
def meshfix():
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if not sub:
        raise RuntimeError("meshfix needs the GUI editor (StaticMeshEditorSubsystem); the commandlet cannot rebuild meshes")
    lib = sub
    n = 0
    for a in EAL.list_assets(ROOT + "/Meshes", recursive=False, include_folder=False):
        sm = unreal.load_asset(a)
        if not isinstance(sm, unreal.StaticMesh):
            continue
        ns = sm.get_editor_property("nanite_settings")      # no Nanite on mobile; ~1M tris needs none on Mac either
        if ns.get_editor_property("enabled"):
            ns.set_editor_property("enabled", False)
            if sub:
                sub.set_nanite_settings(sm, ns, apply_changes=True)
            else:
                sm.set_editor_property("nanite_settings", ns)
        bs = lib.get_lod_build_settings(sm, 0)
        # UE would overwrite the Blender lightmap UVs in channel 1 (an early Lightmass-era step set dst=1, and UE keeps
        # build settings across re-imports). Turn generation off AND aim it at an unused channel, so channel 1 is safe
        # even if the flag comes back.
        if bs.get_editor_property("generate_lightmap_u_vs") or bs.get_editor_property("dst_lightmap_index") != 3:
            bs.set_editor_property("generate_lightmap_u_vs", False)
            bs.set_editor_property("dst_lightmap_index", 3)
            lib.set_lod_build_settings(sm, 0, bs)
        sm.set_editor_property("light_map_coordinate_index", 1)
        EAL.save_loaded_asset(sm, only_if_is_dirty=False)
        n += 1
    bad = [a.split("/")[-1].split(".")[0] for a in EAL.list_assets(ROOT + "/Meshes", recursive=False, include_folder=False)
           if isinstance(unreal.load_asset(a), unreal.StaticMesh)
           and lib.get_lod_build_settings(unreal.load_asset(a), 0).get_editor_property("generate_lightmap_u_vs")]
    log("meshfix", n, "still generating lightmap UVs:", len(bad), bad[:5])


# ================================================================== lightmap textures
def import_lightmaps():
    pdir = os.path.join(IMP, "lightmaps", "png")
    files = sorted(os.path.join(pdir, f) for f in os.listdir(pdir) if f.endswith(".png"))
    for i in range(0, len(files), 40):
        tasks = []
        for f in files[i:i + 40]:
            t = unreal.AssetImportTask()
            t.filename, t.destination_path = f, LM_FOLDER
            t.automated, t.replace_existing, t.save = True, True, True
            tasks.append(t)
        AT.import_asset_tasks(tasks)
    n = 0
    for f in files:
        t = unreal.load_asset(LM_FOLDER + "/" + os.path.splitext(os.path.basename(f))[0])
        if not t:
            log("MISSING LIGHTMAP", f)
            continue
        t.set_editor_property("srgb", True)                 # sRGB colour of L / RANGE
        t.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
        t.set_editor_property("compression_quality", unreal.TextureCompressionQuality.TCQ_HIGHEST)
        t.set_editor_property("compression_no_alpha", True)
        t.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
        t.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
        t.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
        # no mipmaps: the lower mips blend the black space between packed UV islands into thin floor strips, which
        # showed as black, view-dependent bands on floors seen at a grazing angle (bedrooms). Lighting is smooth anyway.
        t.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        EAL.save_loaded_asset(t)
        n += 1
    log("lightmaps imported", n)
    pano = os.path.join(IMP, "lightmaps", "sky_panorama.png")
    if os.path.exists(pano):
        t = unreal.AssetImportTask()
        t.filename, t.destination_path = pano, LM_FOLDER
        t.destination_name = SKY_PANO.split("/")[-1]           # re-import in place (the sky material references it)
        t.automated, t.replace_existing, t.save = True, True, True
        AT.import_asset_tasks([t])
        if EAL.does_asset_exist(LM_FOLDER + "/sky_panorama"):
            EAL.delete_asset(LM_FOLDER + "/sky_panorama")     # stray copy from an earlier version of this script
        tex = unreal.load_asset(SKY_PANO)
        if tex:
            tex.set_editor_property("srgb", True)
            tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)   # no seam at u = 0/1
            tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_SKYBOX)
            tex.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
            tex.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
            EAL.save_loaded_asset(tex)
            log("sky panorama imported")


# ================================================================== baked materials
def expr(mat, cls, x, y, **props):
    e = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def sparam(m, name, x, y, v):
    return expr(m, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=v)


def vparam(m, name, x, y, v):
    return expr(m, unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name, default_value=unreal.LinearColor(*v))


def tparam(m, name, x, y, default, sampler):
    return expr(m, unreal.MaterialExpressionTextureSampleParameter2D, x, y, parameter_name=name, texture=default, sampler_type=sampler)


def new_material(name):
    path = BAKED_FOLDER + "/" + name
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    return AT.create_asset(name, BAKED_FOLDER, unreal.Material, unreal.MaterialFactoryNew())


def lightmap_nodes(m, x, y):
    """Lightmap (UV1, sRGB texture of L / RANGE) * BakedScale -> returns the expression."""
    # default must match the sampler type (sRGB colour, TC_Default): use one of the imported lightmaps
    first = sorted(a for a in EAL.list_assets(LM_FOLDER, recursive=False, include_folder=False))
    black = unreal.load_asset(first[0]) if first else None
    tc1 = expr(m, unreal.MaterialExpressionTextureCoordinate, x - 400, y, coordinate_index=1)
    lm = tparam(m, "LightmapTex", x - 200, y, black, unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    MEL.connect_material_expressions(tc1, "", lm, "UVs")
    sc = sparam(m, "BakedScale", x + 220, y + 140, BAKED_SCALE * RANGE)
    ms = expr(m, unreal.MaterialExpressionMultiply, x + 400, y)
    MEL.connect_material_expressions(lm, "RGB", ms, "A")
    MEL.connect_material_expressions(sc, "", ms, "B")
    tint = vparam(m, "BakedTint", x + 400, y + 140, (1, 1, 1, 1))   # warm interior light (set per actor)
    mt = expr(m, unreal.MaterialExpressionMultiply, x + 580, y)
    MEL.connect_material_expressions(ms, "", mt, "A")
    MEL.connect_material_expressions(tint, "RGB", mt, "B")
    return mt


def min_rough(m, rough, x, y):
    """max(roughness, MinRoughness): with the specular-only downlights, near-mirror surfaces (marble) produce a specular
    peak above the 16-bit float range of phone GPUs -> Inf/NaN -> black patches smeared by TAA. 0.25 caps the peak."""
    mr = sparam(m, "MinRoughness", x, y + 120, 0.25)
    mx = expr(m, unreal.MaterialExpressionMax, x + 150, y)
    MEL.connect_material_expressions(rough, "", mx, "A")
    MEL.connect_material_expressions(mr, "", mx, "B")
    return mx


def baked_outputs(m, albedo, albedo_pin, metallic, lmv, extra_emissive=None):
    """emissive = albedo * lm * (1 - 0.7 metallic) [+ extra];  base color = albedo * metallic (metals keep tinted reflections)."""
    # metals keep 30% of the baked light (1 - 0.7 * metallic): reflections alone leave them black where captures are dark
    met_k = expr(m, unreal.MaterialExpressionMultiply, 60, 500, const_b=0.7)
    MEL.connect_material_expressions(metallic, "", met_k, "A")
    one_m = expr(m, unreal.MaterialExpressionOneMinus, 200, 500)
    MEL.connect_material_expressions(met_k, "", one_m, "")
    e1 = expr(m, unreal.MaterialExpressionMultiply, 400, 300)
    MEL.connect_material_expressions(albedo, albedo_pin, e1, "A")
    MEL.connect_material_expressions(lmv, "", e1, "B")
    e2 = expr(m, unreal.MaterialExpressionMultiply, 600, 300)
    MEL.connect_material_expressions(e1, "", e2, "A")
    MEL.connect_material_expressions(one_m, "", e2, "B")
    em = e2
    if extra_emissive is not None:
        em = expr(m, unreal.MaterialExpressionAdd, 800, 300)
        MEL.connect_material_expressions(e2, "", em, "A")
        MEL.connect_material_expressions(extra_emissive, "", em, "B")
    MEL.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    bc = expr(m, unreal.MaterialExpressionMultiply, 400, -100)
    MEL.connect_material_expressions(albedo, albedo_pin, bc, "A")
    MEL.connect_material_expressions(metallic, "", bc, "B")
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(metallic, "", unreal.MaterialProperty.MP_METALLIC)


def build_tex_baked(name, masked=False):
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
    alb = expr(m, unreal.MaterialExpressionMultiply, -450, -300)
    MEL.connect_material_expressions(d, "RGB", alb, "A")
    MEL.connect_material_expressions(tint, "", alb, "B")
    flat = expr(m, unreal.MaterialExpressionConstant3Vector, -700, 220, constant=unreal.LinearColor(0, 0, 1, 1))
    ns = sparam(m, "NormalStrength", -700, 300, 1.0)
    nl = expr(m, unreal.MaterialExpressionLinearInterpolate, -450, 150)
    MEL.connect_material_expressions(flat, "", nl, "A")
    MEL.connect_material_expressions(n, "RGB", nl, "B")
    MEL.connect_material_expressions(ns, "", nl, "Alpha")
    MEL.connect_material_property(nl, "", unreal.MaterialProperty.MP_NORMAL)
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
    MEL.connect_material_property(min_rough(m, rl, -150, 450), "", unreal.MaterialProperty.MP_ROUGHNESS)
    met = sparam(m, "Metallic", -300, 650, 0.0)
    baked_outputs(m, alb, "", met, lightmap_nodes(m, -300, 900))
    if masked:
        MEL.connect_material_property(d, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_solid_baked():
    m = new_material("M_FlatSolidBaked")
    c = vparam(m, "Color", -600, -200, (0.8, 0.8, 0.8, 1))
    MEL.connect_material_property(min_rough(m, sparam(m, "Roughness", -600, 0, 0.5), -450, 0), "", unreal.MaterialProperty.MP_ROUGHNESS)
    met = sparam(m, "Metallic", -600, 100, 0.0)
    ec = vparam(m, "EmissiveColor", -800, 250, (0, 0, 0, 1))
    es = sparam(m, "EmissiveStrength", -800, 380, 0.0)
    own = expr(m, unreal.MaterialExpressionMultiply, -500, 300)
    MEL.connect_material_expressions(ec, "RGB", own, "A")
    MEL.connect_material_expressions(es, "", own, "B")
    baked_outputs(m, c, "RGB", met, lightmap_nodes(m, -300, 700), extra_emissive=own)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_sheer_baked():
    m = new_material("M_FlatSheerBaked")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    c = vparam(m, "Color", -600, -200, (0.9, 0.88, 0.84, 1))
    lmv = lightmap_nodes(m, -300, 300)
    e = expr(m, unreal.MaterialExpressionMultiply, 200, 0)
    MEL.connect_material_expressions(c, "RGB", e, "A")
    MEL.connect_material_expressions(lmv, "", e, "B")
    MEL.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(sparam(m, "Opacity", -600, 100, 0.5), "", unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def materials():
    masters = {"M_FlatTex": build_tex_baked("M_FlatTexBaked"),
               "M_FlatTexMasked": build_tex_baked("M_FlatTexMaskedBaked", masked=True),
               "M_FlatSolid": build_solid_baked(),
               "M_FlatSheer": build_sheer_baked()}
    n = 0
    for a in EAL.list_assets(ROOT + "/Materials", recursive=False, include_folder=False):
        mi = unreal.load_asset(a)
        if not isinstance(mi, unreal.MaterialInstanceConstant):
            continue
        parent = mi.get_editor_property("parent")
        pname = parent.get_name() if parent else ""
        if pname not in masters:
            continue                                         # glass keeps its own material
        dst = BAKED_FOLDER + "/" + mi.get_name() + "_Baked"
        if EAL.does_asset_exist(dst):
            EAL.delete_asset(dst)
        b = EAL.duplicate_asset(a, dst)
        MEL.set_material_instance_parent(b, masters[pname])   # same parameter names -> overrides carry over
        EAL.save_loaded_asset(b)
        n += 1
    log("baked masters", list(masters), "baked MIs", n)


# ================================================================== levels
def strip_test_shapes():
    """Removes stray engine test shapes (a 10 m Plane at floor height and a Cube left at the origin by a Lightmass test).
    The plane z-fights with the floor in both bedrooms and, having no baked lighting, shows as black jagged patches."""
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    n = 0
    for a in eas.get_all_level_actors():
        if not isinstance(a, unreal.StaticMeshActor):
            continue
        sm = a.static_mesh_component.static_mesh
        if sm and sm.get_path_name().split(".")[0] in ("/Engine/BasicShapes/Plane", "/Engine/BasicShapes/Cube"):
            eas.destroy_actor(a)
            n += 1
    return n


def strip_environment():
    """The Nanite geo environment (flat-environment skill) is Mac-only: phones can't draw ~190k trees. Removes it from
    the mobile copy: actors in folder 06_Environment or using /Game/Flat/Environment meshes. Never saved to MAP."""
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    n = 0
    for a in eas.get_all_level_actors():
        env = str(a.get_folder_path()).startswith("06_Environment")
        if not env and isinstance(a, unreal.StaticMeshActor):
            sm = a.static_mesh_component.static_mesh
            env = bool(sm and sm.get_path_name().startswith("/Game/Flat/Environment"))
        if env:
            eas.destroy_actor(a)
            n += 1
    return n


def copy_level():
    """L_FlatTypeG[_Variant] -> ..._Mobile on disk (Save As). Run in its own session, then quit."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    for p in (MAP_M + "_BuiltData", MAP_M):
        if EAL.does_asset_exist(p):
            EAL.delete_asset(p)
    les.load_level(MAP)
    if strip_test_shapes():
        les.save_current_level()            # fixes the source level too
    n_env = strip_environment()             # mobile copy only (MAP is not saved after this)
    ok = unreal.EditorLoadingAndSavingUtils.save_map(world(), MAP_M)
    log("copied", MAP, "->", MAP_M, ok, "environment actors left out:", n_env)


ROOMS = {  # plan cm rects (x0, x1, y0, y1) -> one reflection capture per space
    "Living": (1206, 1589, 0, 300), "Dining": (906, 1217, 0, 413), "Kitchen": (1229, 1589, 312, 552),
    "Bed1": (0, 390, 0, 390), "Bed2": (402, 732, 162, 552), "Foyer": (546, 906, 0, 150),
    "Toilet1": (150, 390, 402, 552), "Toilet2": (744, 894, 217, 457), "Balcony1": (-20, 138, 325, 572),
    "Balcony2": (906, 1217, 425, 572), "Vanity": (744, 894, 150, 205), "Bed1Entry": (402, 534, 0, 150),
}


def ue(x, y, z=0.0):
    return unreal.Vector(x, -y, z)


def sky_material():
    """Unlit sky for the mobile level (SkyAtmosphere needs an IsSky mesh on mobile anyway): the Mac build's sky
    captured into a cubemap (skycap stage), or a plain gradient if no capture exists."""
    pano = unreal.load_asset(SKY_PANO) if EAL.does_asset_exist(SKY_PANO) else None
    if pano:
        info = json.load(open(os.path.join(IMP, "lightmaps", "sky_panorama.json")))
        m = new_material("M_MobileSky")
        m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        m.set_editor_property("two_sided", True)
        m.set_editor_property("is_sky", True)
        # direction d = -CameraVectorWS ; u = atan2(d.y, d.x) / 2pi + 0.5 ; v = acos(d.z) / pi
        cv = expr(m, unreal.MaterialExpressionCameraVectorWS, -1600, 0)
        d = expr(m, unreal.MaterialExpressionMultiply, -1450, 0, const_b=-1.0)
        MEL.connect_material_expressions(cv, "", d, "A")
        dx = expr(m, unreal.MaterialExpressionComponentMask, -1250, -150, r=True, g=False, b=False, a=False)
        dy = expr(m, unreal.MaterialExpressionComponentMask, -1250, 0, r=False, g=True, b=False, a=False)
        dz = expr(m, unreal.MaterialExpressionComponentMask, -1250, 150, r=False, g=False, b=True, a=False)
        for c in (dx, dy, dz):
            MEL.connect_material_expressions(d, "", c, "")
        at = expr(m, unreal.MaterialExpressionArctangent2Fast, -1050, -80)
        MEL.connect_material_expressions(dy, "", at, "Y")
        MEL.connect_material_expressions(dx, "", at, "X")
        u1 = expr(m, unreal.MaterialExpressionMultiply, -880, -80, const_b=1.0 / (2 * math.pi))
        MEL.connect_material_expressions(at, "", u1, "A")
        u = expr(m, unreal.MaterialExpressionAdd, -720, -80, const_b=0.5)
        MEL.connect_material_expressions(u1, "", u, "A")
        cz = expr(m, unreal.MaterialExpressionClamp, -1050, 150, min_default=-1.0, max_default=1.0)
        MEL.connect_material_expressions(dz, "", cz, "")
        ac = expr(m, unreal.MaterialExpressionArccosineFast, -880, 150)
        MEL.connect_material_expressions(cz, "", ac, "")
        v = expr(m, unreal.MaterialExpressionMultiply, -720, 150, const_b=1.0 / math.pi)
        MEL.connect_material_expressions(ac, "", v, "A")
        uv = expr(m, unreal.MaterialExpressionAppendVector, -560, 0)
        MEL.connect_material_expressions(u, "", uv, "A")
        MEL.connect_material_expressions(v, "", uv, "B")
        t = tparam(m, "SkyPano", -380, 0, pano, unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
        MEL.connect_material_expressions(uv, "", t, "UVs")
        k = sparam(m, "SkyScale", -380, 250, SKY_TARGET * info["scale"] / max(info["mean"], 1e-6))
        e = expr(m, unreal.MaterialExpressionMultiply, -150, 0)
        MEL.connect_material_expressions(t, "RGB", e, "A")
        MEL.connect_material_expressions(k, "", e, "B")
        MEL.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        MEL.recompile_material(m)
        EAL.save_loaded_asset(m)
        log("sky: Mac panorama, scale", SKY_TARGET * info["scale"] / max(info["mean"], 1e-6))
        return m
    m = new_material("M_MobileSky")
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    try:
        m.set_editor_property("is_sky", True)
    except Exception as e:
        log("is_sky", e)
    cv = expr(m, unreal.MaterialExpressionCameraVectorWS, -900, 0)
    mz = expr(m, unreal.MaterialExpressionComponentMask, -700, 0, r=False, g=False, b=True, a=False)
    MEL.connect_material_expressions(cv, "", mz, "")
    neg = expr(m, unreal.MaterialExpressionMultiply, -550, 0, const_b=-1.0)
    MEL.connect_material_expressions(mz, "", neg, "A")
    up = expr(m, unreal.MaterialExpressionSaturate, -400, 0)
    MEL.connect_material_expressions(neg, "", up, "")
    pw = expr(m, unreal.MaterialExpressionPower, -250, 0, const_exponent=0.5)
    MEL.connect_material_expressions(up, "", pw, "Base")
    hor = vparam(m, "Horizon", -400, -250, (3.6, 3.8, 4.2, 1))
    zen = vparam(m, "Zenith", -400, 250, (0.9, 1.5, 3.2, 1))
    lp = expr(m, unreal.MaterialExpressionLinearInterpolate, 0, 0)
    MEL.connect_material_expressions(hor, "", lp, "A")
    MEL.connect_material_expressions(zen, "", lp, "B")
    MEL.connect_material_expressions(pw, "", lp, "Alpha")
    MEL.connect_material_property(lp, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


SKY_FOV = 110.0
SKY_FACES = {  # name: (pitch, yaw) of a SKY_FOV-degree SceneCapture2D; Blender stitches them (blender/scripts/sky_panorama.py)
    "px": (0, 0), "nx": (0, 180), "py": (0, 90), "ny": (0, -90), "pz": (90, 0), "nz": (-90, 0)}


def sky_capture():
    """On the Lumen (Mac) level: six overlapping HDR views of the sky only (all meshes hidden) -> lightmaps/sky_*.exr."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    les.load_level(MAP)
    hide = [a for a in eas.get_all_level_actors() if isinstance(a, unreal.StaticMeshActor)]
    cap = eas.spawn_actor_from_class(unreal.SceneCapture2D, ue(800, 270, 150), unreal.Rotator(0, 0, 0))
    c2 = cap.capture_component2d
    rt = unreal.RenderingLibrary.create_render_target2d(world(), 512, 512, unreal.TextureRenderTargetFormat.RTF_RGBA16F)
    c2.set_editor_property("texture_target", rt)
    c2.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR)
    c2.set_editor_property("fov_angle", SKY_FOV)         # wider than 90: neighbouring views overlap for feathering
    c2.set_editor_property("capture_every_frame", False)
    for h in hide:
        c2.hide_actor_components(h)
    S["cap"] = (cap, c2, rt)
    S["faces"] = list(SKY_FACES.items())
    S["phase"], S["k"] = "skycap", 0


def sky_capture_tick():
    cap, c2, rt = S["cap"]
    S["k"] += 1
    if S["k"] == 1:
        if not S["faces"]:
            unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(cap)
            log("sky faces captured")
            finish()                                         # the Lumen level is not saved
            return
        S["face"] = S["faces"].pop(0)
        name, (pitch, yaw) = S["face"]
        cap.set_actor_rotation(unreal.Rotator(0, pitch, yaw), False)   # (roll, pitch, yaw)
    if S["k"] in (2, 10, 20):
        c2.capture_scene()                                   # repeat: atmosphere / clouds settle
    elif S["k"] == 30:
        unreal.RenderingLibrary.export_render_target(world(), rt, os.path.join(IMP, "lightmaps"), "sky_%s.exr" % S["face"][0])
        S["k"] = 0


def build_mobile_level():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    les.load_level(MAP_M)
    if not world().get_path_name().startswith(MAP_M):
        raise RuntimeError("wrong world " + world().get_path_name())
    if EAL.does_directory_exist(ACTOR_FOLDER):
        EAL.delete_directory(ACTOR_FOLDER)
    counts = {"baked_actors": 0, "baked_slots": 0, "kept_slots": 0, "no_lightmap": 0, "lights_removed": 0}
    for a in eas.get_all_level_actors():
        label = a.get_actor_label()
        if isinstance(a, (unreal.SpotLight, unreal.PointLight)):
            if a.get_editor_property("tags") and "SpecOnly" in [str(t) for t in a.get_editor_property("tags")]:
                continue                                    # already converted (re-run)
            lc = a.light_component
            lc.set_mobility(unreal.ComponentMobility.MOVABLE)
            lc.set_diffuse_scale(0.0)                       # diffuse light is in the lightmaps
            lc.set_specular_scale(1.0)
            lc.set_cast_shadows(False)
            lc.set_intensity(lc.intensity * SPEC_LIGHT_SCALE)
            lc.set_editor_property("attenuation_radius", min(lc.attenuation_radius, 380.0))   # cheaper on phones
            a.set_editor_property("tags", [unreal.Name("SpecOnly")])
            counts["spec_lights"] = counts.get("spec_lights", 0) + 1
        elif isinstance(a, unreal.ExponentialHeightFog):
            # the Mac build's distance haze, re-expressed in mobile (baked) units; starts 10 m out so rooms stay clear
            fc = a.component
            fc.set_editor_property("start_distance", 1000.0)
            fc.set_editor_property("fog_density", FOG_DENSITY)   # the Mac haze is mostly aerial perspective (no SkyAtmosphere here)
            fc.set_editor_property("fog_max_opacity", 0.85)
            for prop in ("fog_inscattering_luminance", "fog_inscattering_color"):
                try:
                    fc.set_editor_property(prop, unreal.LinearColor(*FOG_COLOR, 1.0))
                    break
                except Exception:
                    pass
            for prop in ("directional_inscattering_luminance", "directional_inscattering_color"):
                try:
                    fc.set_editor_property(prop, unreal.LinearColor(0, 0, 0, 1))
                    break
                except Exception:
                    pass
            counts["fog"] = 1
        elif isinstance(a, (unreal.RectLight, unreal.SkyLight, unreal.VolumetricCloud,
                            unreal.SkyAtmosphere, unreal.DirectionalLight)) \
                or label.startswith(("RC_", "SKY_")):
            eas.destroy_actor(a)
            counts["lights_removed"] += 1
        elif isinstance(a, unreal.DirectionalLight):
            # keeps the sky (SkyAtmosphere needs a sun) but lights nothing: lighting channel 2 only, no shadows
            lc = a.light_component
            lc.set_editor_property("lighting_channels", unreal.LightingChannels(False, False, True))
            lc.set_cast_shadows(False)
            lc.set_intensity(SKY_SUN_LUX)      # only drives the sky seen through the windows (manual exposure)
        elif isinstance(a, unreal.StaticMeshActor):
            info = MANIFEST.get(label)
            comp = a.static_mesh_component
            if not info:
                counts["no_lightmap"] += 1
                continue
            tex = unreal.load_asset(LM_FOLDER + "/" + info["tex"])
            if not tex:
                counts["no_lightmap"] += 1
                continue
            sm = comp.static_mesh
            for i in range(comp.get_num_materials()):
                base = sm.get_material(i)
                bpath = BAKED_FOLDER + "/" + (base.get_name() if base else "") + "_Baked"
                if not base or not EAL.does_asset_exist(bpath):
                    counts["kept_slots"] += 1
                    continue
                name = "MIA_%s_%d" % (san(label), i)
                mi = AT.create_asset(name, ACTOR_FOLDER, unreal.MaterialInstanceConstant,
                                     unreal.MaterialInstanceConstantFactoryNew())
                MEL.set_material_instance_parent(mi, unreal.load_asset(bpath))
                MEL.set_material_instance_texture_parameter_value(mi, "LightmapTex", tex)
                if not label.startswith("CTX_"):
                    MEL.set_material_instance_vector_parameter_value(mi, "BakedTint", unreal.LinearColor(*INTERIOR_TINT, 1.0))
                EAL.save_loaded_asset(mi)
                comp.set_material(i, mi)
                counts["baked_slots"] += 1
            comp.set_cast_shadow(False)
            counts["baked_actors"] += 1
    log("converted", counts)
    sky = eas.spawn_actor_from_object(unreal.load_asset("/Engine/BasicShapes/Sphere"), ue(800, 270, 0), unreal.Rotator(0, 0, 0))
    sky.set_actor_label("SKY_Dome")
    sky.set_folder_path("03_Lighting")
    sky.set_actor_scale3d(unreal.Vector(3000, 3000, 3000))     # 150 m radius
    sc = sky.static_mesh_component
    sc.set_material(0, sky_material())
    sc.set_cast_shadow(False)
    sc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    sc.set_collision_profile_name("NoCollision")     # otherwise the 150 m sphere encloses the PlayerStart and the spawn fails
    sc.set_editor_property("generate_overlap_events", False)
    for name, (x0, x1, y0, y1) in ROOMS.items():
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rc = eas.spawn_actor_from_class(unreal.SphereReflectionCapture, ue(cx, cy, 150), unreal.Rotator(0, 0, 0))
        rc.set_actor_label("RC_" + name)
        rc.set_folder_path("03_Lighting/ReflectionCaptures")
        rc.get_component_by_class(unreal.SphereReflectionCaptureComponent).set_editor_property(
            "influence_radius", 0.5 * math.hypot(x1 - x0, y1 - y0) + 60)
    for a in eas.get_all_level_actors():
        if isinstance(a, unreal.PostProcessVolume):
            s = a.settings
            for prop, val in (("override_dynamic_global_illumination_method", True),
                              ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.NONE),
                              ("override_reflection_method", True), ("reflection_method", unreal.ReflectionMethod.NONE),
                              ("override_ambient_occlusion_intensity", True), ("ambient_occlusion_intensity", 0.0),
                              ("override_bloom_intensity", True), ("bloom_intensity", 0.3),
                              ("override_color_contrast", True), ("color_contrast", unreal.Vector4(CONTRAST, CONTRAST, CONTRAST, 1.0)),
                              ("override_color_saturation", True), ("color_saturation", unreal.Vector4(SATURATION, SATURATION, SATURATION, 1.0))) + AE:
                try:
                    s.set_editor_property(prop, val)
                except Exception as e:
                    log("pp", prop, e)
            a.set_editor_property("settings", s)
    for a in eas.get_all_level_actors():
        if a.get_actor_label().startswith("PPV_Room_"):
            eas.destroy_actor(a)
    for name, ev in ROOM_EV.items():
        x0, x1, y0, y1 = ROOMS[name]
        v = eas.spawn_actor_from_class(unreal.PostProcessVolume, ue((x0 + x1) / 2, (y0 + y1) / 2, 142), unreal.Rotator(0, 0, 0))
        v.set_actor_label("PPV_Room_" + name)
        v.set_folder_path("03_Lighting/RoomExposure")
        v.set_actor_scale3d(unreal.Vector((x1 - x0) / 200.0, (y1 - y0) / 200.0, 285 / 200.0))   # default brush: 200 cm cube
        v.set_editor_property("unbound", False)
        v.set_editor_property("priority", 1.0)
        v.set_editor_property("blend_radius", 90.0)
        st = v.settings
        for prop, val in (("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                          ("override_auto_exposure_apply_physical_camera_exposure", True),
                          ("auto_exposure_apply_physical_camera_exposure", False),
                          ("override_auto_exposure_bias", True), ("auto_exposure_bias", EXPOSURE_BIAS + ev)):
            st.set_editor_property(prop, val)
        v.set_editor_property("settings", st)
    log("room exposure volumes", len(ROOM_EV))
    unreal.SystemLibrary.execute_console_command(world(), "BuildReflectionCaptures")
    les.save_current_level()
    log("mobile level saved")


SHOTS = [  # same viewpoints as ue_verify.py so the Lumen and baked versions can be compared
    ("mob_spawn_view", (1525, 40, 165), (1300, 260, 130)), ("mob_living", (880, 55, 160), (1589, 210, 120)),
    ("mob_dining", (1540, 90, 160), (930, 360, 120)), ("mob_kitchen", (1505, 398, 160), (1250, 545, 110)),
    ("mob_foyer", (560, 100, 160), (1500, 60, 120)), ("mob_bed1", (322, 300, 160), (110, 20, 95)),
    ("mob_bed2", (425, 262, 160), (732, 460, 100)), ("mob_toilet1", (175, 412, 150), (330, 552, 100)),
    ("mob_vanity", (840, 20, 150), (819, 205, 120)), ("mob_balcony2", (1060, 300, 160), (1060, 572, 110)),
]
S = {"phase": "warmup", "t": 0, "shots": list(SHOTS), "done": []}
SHOT_DIR = os.path.join(HERE, "..", "FlatTypeG", "Saved", "Screenshots", "MacEditor")
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "previews", "mobile_editor" + _SFX.lower()))


def compiling():
    try:
        return unreal.ShaderCompilingManager.get_num_remaining_jobs() > 0 if hasattr(unreal, "ShaderCompilingManager") else False
    except Exception:
        return False


def newest_shot():
    try:
        fs = [os.path.join(SHOT_DIR, f) for f in os.listdir(SHOT_DIR) if f.endswith(".png")]
        return max(fs, key=os.path.getmtime) if fs else None
    except Exception:
        return None


def look_rot(eye, tgt):
    return unreal.MathLibrary.make_rot_from_x(unreal.Vector(tgt[0] - eye[0], -(tgt[1] - eye[1]), tgt[2] - eye[2]))


def make_capture():
    """Off-screen SceneCapture2D -> render target (works with the editor window hidden), same exposure as the level."""
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rt = unreal.RenderingLibrary.create_render_target2d(world(), 1600, 900, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cap = eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    cc = cap.capture_component2d
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    cc.set_editor_property("fov_angle", 90.0)
    cc.set_editor_property("capture_every_frame", False)
    pp = cc.get_editor_property("post_process_settings")
    for prop, val in AE + (("override_auto_exposure_speed_up", True), ("auto_exposure_speed_up", 20.0),
                           ("override_auto_exposure_speed_down", True), ("auto_exposure_speed_down", 20.0)):
        pp.set_editor_property(prop, val)
    cc.set_editor_property("post_process_settings", pp)
    cc.set_editor_property("post_process_blend_weight", 1.0)
    return cap, cc, rt


def tick(dt):
    s = S
    try:
        if s["phase"] == "skycap":
            if time.time() - s.get("t0", 0) > 30:
                sky_capture_tick()
            return
        if s["phase"] == "warmup" and time.time() - s["t0"] > float(os.environ.get("FLAT_WARMUP_S", "90")):
            unreal.SystemLibrary.execute_console_command(world(), "BuildReflectionCaptures")
            s["phase"], s["t0"] = "settle", time.time()
        elif s["phase"] == "settle" and time.time() - s["t0"] > 15:
            s["cap"], s["cc"], s["rt"] = make_capture()
            os.makedirs(OUT_DIR, exist_ok=True)
            s["phase"], s["k"] = "shots", 0
        elif s["phase"] == "shots":
            # one step per tick: place+capture, wait 3 ticks, export (the readback lags the capture)
            s["k"] += 1
            if s["k"] == 1:
                if not s["shots"]:
                    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(s["cap"])
                    finish()
                    return
                s["cur"] = s["shots"].pop(0)
                name, eye, tgt = s["cur"]
                s["cap"].set_actor_location_and_rotation(ue(*eye), look_rot(eye, tgt), False, False)
                s["cc"].capture_scene()
            elif s["k"] < 12:
                s["cc"].capture_scene()                       # let auto exposure settle
            elif s["k"] == 15:
                unreal.RenderingLibrary.export_render_target(world(), s["rt"], OUT_DIR, s["cur"][0] + ".png")
                log("shot", s["cur"][0])
                s["k"] = 0
    except Exception as e:
        log("tick error", e)
        finish()


def finish():
    S["phase"] = "done"
    try:
        unreal.unregister_slate_post_tick_callback(HANDLE)
    except Exception:
        pass
    open(os.path.join(HERE, "ue_mobile_report.txt"), "w").write("\n".join(LOG))
    if os.environ.get("FLAT_QUIT") == "1":
        unreal.SystemLibrary.quit_editor()


HANDLE = None
try:
    if "meshfix" in STAGES:
        meshfix()
    if "lightmaps" in STAGES:
        import_lightmaps()
    if "materials" in STAGES:
        materials()
    if "skycap" in STAGES:
        sky_capture()
        S["t0"] = time.time()
        HANDLE = unreal.register_slate_post_tick_callback(tick)
    if "check" in STAGES:
        sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        for n in ("SM_ARCH_FloorFinish", "SM_ARCH_CeilingSlab", "SM_LIV_Sofa_Base"):
            sm = unreal.load_asset(ROOT + "/Meshes/" + n)
            bs = sub.get_lod_build_settings(sm, 0)
            log("check", n, "generate", bs.get_editor_property("generate_lightmap_u_vs"), "dst", bs.get_editor_property("dst_lightmap_index"),
                "uv channels", sub.get_num_uv_channels(sm, 0))
        bad = [a.split("/")[-1].split(".")[0] for a in EAL.list_assets(ROOT + "/Meshes", recursive=False, include_folder=False)
               if isinstance(unreal.load_asset(a), unreal.StaticMesh)
               and sub.get_lod_build_settings(unreal.load_asset(a), 0).get_editor_property("dst_lightmap_index") == 1
               and sub.get_lod_build_settings(unreal.load_asset(a), 0).get_editor_property("generate_lightmap_u_vs")]
        log("check: meshes that would overwrite UV1:", len(bad), bad[:6])
    if "copy" in STAGES:
        copy_level()
    if "level" in STAGES:
        build_mobile_level()
    if "shots" in STAGES:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        les.load_level(MAP_M)
        try:
            les.editor_set_game_view(True)                 # hide editor icons
        except Exception as e:
            log("game view", e)
        S["t0"] = time.time()
        HANDLE = unreal.register_slate_post_tick_callback(tick)
    elif "level" in STAGES:
        finish()
    elif not any(x in STAGES for x in ("level", "shots", "skycap")):   # (meshfix/check/copy also finish here)
        finish()
except Exception as e:
    import traceback
    log("ERROR", e, traceback.format_exc())
    finish()
