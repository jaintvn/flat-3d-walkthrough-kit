"""Adds the geo-referenced exterior (blender/environment.blend -> env_export.py -> unreal/import_env) to the Mac
level L_FlatTypeG.  The interior actors, lights, post process and player start are not touched; only the four
placeholder context actors (CTX_Ground, CTX_Buildings, CTX_Trees, CTX_Facade) are removed.

FLAT_RUN=<abs path>/ue_environment.py FLAT_STAGES=assets,level FLAT_QUIT=1 UnrealEditor FlatTypeG.uproject
Stages: assets (masters, material instances, FBX import, Nanite)  |  level (actors + instanced vegetation, save)
Re-running is safe: previous environment actors are replaced.  Run it again after ue_build.py's level stage,
because that stage rebuilds the level from the interior export (which still contains the placeholders).
"""
import unreal, json, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
IMP = os.path.abspath(os.path.join(HERE, "..", "import_env"))
SCENE = json.load(open(os.path.join(IMP, "env_scene.json")))
ROOT = "/Game/Flat/Environment"
MAP = "/Game/Flat/Maps/L_FlatTypeG"
AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
PLACEHOLDERS = ("CTX_Ground", "CTX_Buildings", "CTX_Trees", "CTX_Facade")
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log_warning("FLATENV " + s)


def san(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


# ------------------------------------------------------------------ materials
def expr(m, cls, x, y):
    return MEL.create_material_expression(m, cls, x, y)


def vparam(m, name, x, y, v):
    e = expr(m, unreal.MaterialExpressionVectorParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", unreal.LinearColor(*v))
    return e


def sparam(m, name, x, y, v):
    e = expr(m, unreal.MaterialExpressionScalarParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", v)
    return e


def build_master(name, foliage):
    path = ROOT + "/Materials/" + name
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    m = AT.create_asset(name, ROOT + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("two_sided", True)
    m.set_editor_property("used_with_instanced_static_meshes", True)
    try:
        m.set_editor_property("used_with_nanite", True)
    except Exception:
        pass
    if foliage:
        m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    # base = lerp(Color, ColorB, PerInstanceRandom) * VertexColor * Gain   (Gain compensates FBX vertex-colour encoding)
    a = vparam(m, "Color", -900, -300, (0.5, 0.5, 0.5, 1))
    b = vparam(m, "ColorB", -900, -150, (0.5, 0.5, 0.5, 1))
    pir = expr(m, unreal.MaterialExpressionPerInstanceRandom, -900, 0)
    lerp = expr(m, unreal.MaterialExpressionLinearInterpolate, -650, -200)
    MEL.connect_material_expressions(a, "", lerp, "A")
    MEL.connect_material_expressions(b, "", lerp, "B")
    MEL.connect_material_expressions(pir, "", lerp, "Alpha")
    vc = expr(m, unreal.MaterialExpressionVertexColor, -900, 150)
    mul = expr(m, unreal.MaterialExpressionMultiply, -450, -100)
    MEL.connect_material_expressions(lerp, "", mul, "A")
    MEL.connect_material_expressions(vc, "", mul, "B")
    gain = sparam(m, "VColGain", -650, 250, 1.0)
    mul2 = expr(m, unreal.MaterialExpressionMultiply, -300, -50)
    MEL.connect_material_expressions(mul, "", mul2, "A")
    MEL.connect_material_expressions(gain, "", mul2, "B")
    MEL.connect_material_property(mul2, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(sparam(m, "Roughness", -450, 200, 0.8), "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(sparam(m, "Metallic", -450, 300, 0.0), "", unreal.MaterialProperty.MP_METALLIC)
    MEL.connect_material_property(sparam(m, "Specular", -450, 400, 0.5), "", unreal.MaterialProperty.MP_SPECULAR)
    if foliage:
        sub = expr(m, unreal.MaterialExpressionMultiply, -300, 100)
        MEL.connect_material_expressions(mul2, "", sub, "A")
        MEL.connect_material_expressions(sparam(m, "Translucency", -450, 500, 0.7), "", sub, "B")
        MEL.connect_material_property(sub, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def build_mis(masters):
    MI = {}
    for name, d in SCENE["materials"].items():
        mi_name = "MI_" + san(name)
        path = ROOT + "/Materials/" + mi_name
        mi = unreal.load_asset(path) if EAL.does_asset_exist(path) else \
            AT.create_asset(mi_name, ROOT + "/Materials", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, masters["foliage" if d["foliage"] else "surface"])
        MEL.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(*d["color"], 1))
        MEL.set_material_instance_vector_parameter_value(mi, "ColorB", unreal.LinearColor(*d["color_b"], 1))
        MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", d["roughness"])
        MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", d["metallic"])
        MEL.set_material_instance_scalar_parameter_value(mi, "Specular", min(1.0, d["specular"]))
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi)
        MI[san(name)] = mi
    return MI


# ------------------------------------------------------------------ meshes
def import_meshes(MI):
    md = os.path.join(IMP, "meshes")
    files = sorted(os.path.join(md, f) for f in os.listdir(md) if f.endswith(".fbx"))
    for i in range(0, len(files), 20):
        tasks = []
        for f in files[i:i + 20]:
            t = unreal.AssetImportTask()
            t.filename = f
            t.destination_path = ROOT + "/Meshes"
            t.automated = True
            t.replace_existing = True
            t.save = True
            tasks.append(t)
        AT.import_asset_tasks(tasks)
    n = 0
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        sm = unreal.load_asset(ROOT + "/Meshes/" + name)
        if sm is None:
            log("MISSING", name)
            continue
        for i, sl in enumerate(sm.get_editor_property("static_materials")):
            key = san(str(sl.material_slot_name))
            mi = MI.get(key) or next((v for k, v in MI.items() if key.startswith(k) or k.startswith(key)), None)
            if mi:
                sm.set_material(i, mi)
            else:
                log("no MI for", name, key)
        try:
            unreal.EditorStaticMeshLibrary.remove_collisions(sm)
        except Exception:
            pass
        ns = sm.get_editor_property("nanite_settings")
        ns.set_editor_property("enabled", True)
        if name.startswith("SM_TREE_") or "Wires" in name:
            # leaflets / leaves are thin disconnected quads: without Preserve Area Nanite simplifies them away
            # at distance and the trees turn into bare trunks
            # UE 5.8: NaniteShapePreservation (PRESERVE_AREA keeps foliage area as it simplifies)
            try:
                ns.set_editor_property("shape_preservation", unreal.NaniteShapePreservation.PRESERVE_AREA)
            except Exception as e:
                log("shape_preservation not available", e)
        sm.set_editor_property("nanite_settings", ns)
        EAL.save_loaded_asset(sm)
        n += 1
    # Interchange may create materials/textures next to the meshes: remove them
    for a in EAL.list_assets(ROOT + "/Meshes", recursive=True, include_folder=False):
        obj = unreal.load_asset(a)
        if isinstance(obj, (unreal.Material, unreal.MaterialInstanceConstant, unreal.Texture2D)):
            EAL.delete_asset(a)
    log("meshes imported", n)


# ------------------------------------------------------------------ level
def add_hism(actor, sm):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = sds.k2_gather_subobject_data_for_instance(actor)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.HierarchicalInstancedStaticMeshComponent,
                                          blueprint_context=None)
    h, fail = sds.add_new_subobject(params)
    if not fail.is_empty():
        raise RuntimeError(str(fail))
    comp = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(sds.k2_find_subobject_data_from_handle(h))
    comp.set_static_mesh(sm)
    return comp


FOG_DENSITY = float(os.environ.get("FLAT_FOG", "0.0006"))


def tune_atmosphere(eas):
    """The height fog was tuned for the old placeholder ground plane (density 0.004 at -30 m). Over kilometres of
    real terrain that turns the whole view white. Put the fog base on the plot's ground (-34.8 m) and thin it to a
    Kerala-morning haze (~10 km visibility). Sun, sky light, sky atmosphere and post process are unchanged."""
    for a in eas.get_all_level_actors():
        if isinstance(a, unreal.ExponentialHeightFog):
            a.set_actor_location(unreal.Vector(0, 0, -3480), False, False)
            fc = a.component
            fc.set_editor_property("fog_density", FOG_DENSITY)
            fc.set_editor_property("fog_height_falloff", 0.05)
            log("fog", FOG_DENSITY)


def build_level():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    les.load_level(MAP)
    removed = 0
    for a in eas.get_all_level_actors():
        lab = a.get_actor_label()
        if lab in PLACEHOLDERS or lab.startswith("ENV_") or str(a.get_folder_path()).startswith("06_Environment"):
            eas.destroy_actor(a)
            removed += 1
    log("removed", removed, "placeholder/old environment actors")
    for m in SCENE["meshes"]:
        sm = unreal.load_asset(ROOT + "/Meshes/" + m["asset"])
        if sm is None:
            log("missing mesh", m["asset"])
            continue
        a = eas.spawn_actor_from_object(sm, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        a.set_actor_label(m["asset"][3:])
        a.set_folder_path("06_Environment/" + ("Terrain" if "Terrain" in m["asset"] or "Horizon" in m["asset"] else
                                               "Buildings" if any(k in m["asset"] for k in ("House", "Tower", "Plot")) else "Streets"))
        c = a.static_mesh_component
        c.set_mobility(unreal.ComponentMobility.STATIC)
        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        if "Horizon" in m["asset"] or "Wires" in m["asset"]:
            c.set_cast_shadow(False)
    veg = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    veg.set_actor_label("ENV_Vegetation")
    veg.set_folder_path("06_Environment/Vegetation")
    veg.static_mesh_component.set_mobility(unreal.ComponentMobility.STATIC)
    total = 0
    for name, pts in SCENE["trees"].items():
        sm = unreal.load_asset(ROOT + "/Meshes/" + SCENE["tree_assets"][name]["asset"])
        if sm is None:
            log("missing tree", name)
            continue
        comp = add_hism(veg, sm)
        comp.set_mobility(unreal.ComponentMobility.STATIC)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        xf = []
        for x, y, z, r, s in pts:
            xf.append(unreal.Transform(unreal.Vector(x * 100, -y * 100, z * 100),
                                       unreal.Rotator(0, 0, -r * 57.29578), unreal.Vector(s, s, s)))
        comp.add_instances(xf, False, False)
        total += len(xf)
        log("trees", name, len(xf))
    log("vegetation instances", total)
    tune_atmosphere(eas)
    les.save_current_level()
    log("level saved")


def main():
    t0 = time.time()
    stages = os.environ.get("FLAT_STAGES", "assets,level").split(",")
    try:
        if "assets" in stages:
            masters = {"surface": build_master("M_EnvSurface", False), "foliage": build_master("M_EnvFoliage", True)}
            MI = build_mis(masters)
            import_meshes(MI)
        if "level" in stages:
            build_level()
    except Exception as e:
        import traceback
        log("ERROR", e, traceback.format_exc())
    log("done in %.0fs" % (time.time() - t0))
    open(os.path.join(HERE, "ue_environment_report.txt"), "w").write("\n".join(LOG))
    if os.environ.get("FLAT_QUIT") == "1":
        unreal.SystemLibrary.quit_editor()


main()
