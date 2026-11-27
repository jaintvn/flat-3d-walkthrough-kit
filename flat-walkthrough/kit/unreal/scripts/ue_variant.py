"""Makes a furnishing variant of the Mac level: a copy of L_FlatTypeG with the objects of variants.json removed.

FLAT_VARIANT=SemiFurnished FLAT_RUN=<abs path>/unreal/scripts/ue_variant.py UnrealEditor unreal/FlatTypeG/FlatTypeG.uproject
Writes /Game/Flat/Maps/L_FlatTypeG_<Variant> and ue_variant_<variant>_report.txt next to this script. The source
level is loaded and stripped in memory, then saved under the new name; L_FlatTypeG on disk is never saved here.

An actor goes when its label matches remove_patterns, or when its category (scene.json 'cat', written by
export_ue.py from the Blender 'flat_cat' property) is in remove_cats. Environment actors (folder 06_Environment or
/Game/Flat/Environment meshes) are never touched, so run this after ue_environment.py and the variant keeps the view.
Stray /Engine/BasicShapes Plane/Cube actors are always removed (they z-fight with floors; see flat-android skill).
"""
import os, re, json
import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANT = os.environ.get("FLAT_VARIANT", "").strip()
CFG = json.load(open(os.path.join(HERE, "variants.json")))["variants"]
if VARIANT not in CFG:
    raise RuntimeError("FLAT_VARIANT must be one of %s" % list(CFG))
V = CFG[VARIANT]
SRC = "/Game/Flat/Maps/L_FlatTypeG"
DST = SRC + "_" + VARIANT
REPORT = os.path.join(HERE, "ue_variant_%s_report.txt" % VARIANT.lower())
PAT = re.compile("|".join("(?:%s)" % p for p in V.get("remove_patterns", []))) if V.get("remove_patterns") else None
CATS = set(V.get("remove_cats", []))
_scene = os.path.join(HERE, "..", "import", "scene.json")
CAT = {}
if os.path.exists(_scene):
    sc = json.load(open(_scene))
    for rec in sc.get("instances", []) + sc.get("lights", []):
        if rec.get("cat"):
            CAT[rec["name"]] = rec["cat"]


def is_env(a):
    if str(a.get_folder_path()).startswith("06_Environment"):
        return True
    if isinstance(a, unreal.StaticMeshActor):
        sm = a.static_mesh_component.static_mesh
        return bool(sm and sm.get_path_name().startswith("/Game/Flat/Environment"))
    return False


def main():
    EAL = unreal.EditorAssetLibrary
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for p in (DST + "_BuiltData", DST):
        if EAL.does_asset_exist(p):
            EAL.delete_asset(p)
    if not les.load_level(SRC):
        raise RuntimeError("could not load " + SRC)
    removed, kept = [], []
    for a in eas.get_all_level_actors():
        label = a.get_actor_label()
        if is_env(a):
            continue
        if isinstance(a, unreal.StaticMeshActor):
            sm = a.static_mesh_component.static_mesh
            if sm and sm.get_path_name().split(".")[0] in ("/Engine/BasicShapes/Plane", "/Engine/BasicShapes/Cube"):
                removed.append(label + " (stray test shape)")
                eas.destroy_actor(a)
                continue
        if not isinstance(a, (unreal.StaticMeshActor, unreal.Light)):
            continue
        hit = (CAT.get(label) in CATS) or (PAT is not None and PAT.search(label) is not None)
        if hit:
            removed.append(label)
            eas.destroy_actor(a)
        elif str(a.get_folder_path()).startswith("INT_"):
            kept.append(label)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, DST):
        raise RuntimeError("could not save " + DST)
    with open(REPORT, "w") as f:
        f.write("VARIANT %s -> %s (%s)\nremoved %d actors:\n  %s\n\nkept interior actors (%d):\n  %s\n"
                % (VARIANT, DST, V.get("title", ""), len(removed), "\n  ".join(sorted(removed)), len(kept),
                   "\n  ".join(sorted(kept))))
    unreal.log("VARIANT %s removed %d, kept %d interior" % (VARIANT, len(removed), len(kept)))


try:
    main()
finally:
    if os.environ.get("FLAT_QUIT", "1") == "1":
        unreal.SystemLibrary.quit_editor()
