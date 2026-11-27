"""Exports blender/environment.blend for Unreal (same FBX convention as export_ue.py: mesh in local space,
-Z forward / Y up, Unreal location = (x, -y, z) * 100).

Blender -b blender/environment.blend -P env_export.py -- <unreal/import_env dir>

writes  meshes/SM_ENV_*.fbx      merged environment meshes (identity transform, placed at the origin)
        meshes/SM_TREE_*.fbx     vegetation assets (origin at the trunk base)
        env_scene.json           {"meshes": [...], "trees": {asset: [[x, y, z, yaw_rad, scale], ...]}, "materials": {...}}
"""
import bpy, os, sys, json, re

OUT = sys.argv[sys.argv.index("--") + 1]
MD = os.path.join(OUT, "meshes")
os.makedirs(MD, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "env_data")
FOLIAGE = {"M_Env_PalmFrond", "M_Env_PalmFrondDry", "M_Env_ArecaLeaf", "M_Env_BananaLeaf", "M_Env_Leaf"}


def san(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def describe(m):
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    I = b.inputs
    col = list(I["Base Color"].default_value)[:3]
    col_b = None
    vcol = False
    for n in m.node_tree.nodes:
        if n.type == "MIX" and getattr(n, "data_type", "") == "RGBA":
            if n.blend_type == "MULTIPLY":
                vcol = True
                if not n.inputs["A"].is_linked:
                    col = list(n.inputs["A"].default_value)[:3]
            else:
                col = list(n.inputs["A"].default_value)[:3]
                col_b = list(n.inputs["B"].default_value)[:3]
        if n.type == "VERTEX_COLOR":
            vcol = True
    try:
        spec = I["Specular IOR Level"].default_value
    except KeyError:
        spec = 0.5
    return {"color": [round(c, 4) for c in col], "color_b": [round(c, 4) for c in (col_b or col)],
            "roughness": round(I["Roughness"].default_value, 3), "metallic": round(I["Metallic"].default_value, 3),
            "specular": round(spec, 3), "vcol": vcol, "foliage": m.name in FOLIAGE}


def export(ob, asset):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.hide_set(False)
    ob.hide_viewport = False
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(MD, asset + ".fbx"), use_selection=True, apply_unit_scale=True,
                             global_scale=1.0, axis_forward="-Z", axis_up="Y", object_types={"MESH"},
                             use_mesh_modifiers=False, mesh_smooth_type="FACE", use_tspace=False, add_leaf_bones=False,
                             bake_anim=False, path_mode="STRIP", embed_textures=False, colors_type="LINEAR")


meshes, mats = [], {}
assets = bpy.data.collections["ENV_TreeAssets"].objects
for ob in list(bpy.data.collections["06_Environment"].all_objects):
    if ob.type != "MESH" or ob.name.startswith("ENV_Trees_") or ob.name in assets:
        continue
    if len(ob.data.polygons) == 0:
        continue
    asset = "SM_" + san(ob.name)
    export(ob, asset)
    meshes.append({"asset": asset, "slots": [s.material.name for s in ob.material_slots],
                   "tris": sum(len(p.vertices) - 2 for p in ob.data.polygons)})
    for s in ob.material_slots:
        mats.setdefault(s.material.name, describe(s.material))
trees = {}
for ob in assets:
    asset = "SM_TREE_" + san(ob.name)
    export(ob, asset)
    for s in ob.material_slots:
        mats.setdefault(s.material.name, describe(s.material))
    trees[ob.name] = {"asset": asset, "tris": sum(len(p.vertices) - 2 for p in ob.data.polygons)}
inst = json.load(open(os.path.join(DATA, "tree_instances_flat.json")))
json.dump({"meshes": meshes, "tree_assets": trees, "trees": inst, "materials": mats},
          open(os.path.join(OUT, "env_scene.json"), "w"))
print("ENV_EXPORT meshes %d tree assets %d instances %d materials %d" % (len(meshes), len(trees), sum(len(v) for v in inst.values()), len(mats)))
