"""Saves a furnishing variant of the flat's .blend (for the Android light bake of that variant).

Blender -b blender/flat_typeG.blend -P blender_variant.py -- <Variant> <variants.json> <out.blend>

Removes the same objects as unreal/scripts/ue_variant.py (Blender 'flat_cat' in remove_cats, or the object name
matching remove_patterns), then saves <out.blend>. The source .blend is not saved. Bake the result with
bake_lightmaps.py into unreal/import_<variant> (lower case).
"""
import bpy, sys, re, json

argv = sys.argv[sys.argv.index("--") + 1:]
VARIANT, CFG, OUT = argv[0], argv[1], argv[2]
V = json.load(open(CFG))["variants"][VARIANT]
PAT = re.compile("|".join("(?:%s)" % p for p in V.get("remove_patterns", []))) if V.get("remove_patterns") else None
CATS = set(V.get("remove_cats", []))
gone = []
for ob in list(bpy.data.objects):
    if any(c.name.startswith("06_Environment") for c in ob.users_collection):
        continue
    if ob.get("flat_cat", "") in CATS or (PAT is not None and PAT.search(ob.name)):
        gone.append(ob.name)
        bpy.data.objects.remove(ob, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, copy=True)
print("BLENDER_VARIANT %s removed %d objects -> %s" % (VARIANT, len(gone), OUT))
