"""Exports flat_typeG.blend for Unreal: one FBX per unique mesh (modifiers applied, local space)
plus scene.json (instances, materials, lights, collision classes).

Blender -b flat_typeG.blend -P export_ue.py -- <out_dir>
"""
import bpy, json, os, re, sys, math
from mathutils import Matrix

OUT = sys.argv[sys.argv.index("--") + 1]
MESH_DIR = os.path.join(OUT, "meshes")
os.makedirs(MESH_DIR, exist_ok=True)
BLEND_DIR = os.path.dirname(bpy.data.filepath)

NO_COLLISION = re.compile(r"Curtain|Rug|Runner|Pendant|CeilingFan|Sconce|Vase|Books|Photo|Plant|Herb|LED|Moulding|Painting|_Art|"
                          r"Pillow|Cushion_|Lumbar|Throw|Towel|Jar|Board|Tap|Spout|Lamp|Mirror|Switch|Shower|FlushPlate|Hinge|"
                          r"Downlight|Globe|_Rod|Accessories|Reveal|Pull|Split|Handle|Shade|Screen|DuvetFold|Skirting|"
                          r"FalseCeiling|FC_|Plaque|CTX_|LGT_|WM_Door|WM_Panel|Hob|Sink|UnderCabinet|Runner|Head_\d", re.I)
COMPLEX = re.compile(r"^(WALL_|EXT_|INT_|CTX_Passage|ARCH_|WIN_|SLD_|DOOR_.*_Frame)", re.I)


def sanitize(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def collision_class(ob):
    cols = [c.name for c in ob.users_collection]
    n = ob.name
    if any(c.startswith("05_Context") for c in cols) and not n.startswith("CTX_Passage"):
        return "none"
    if any(c in ("ARCH_FalseCeiling", "LGT_Emissive", "LGT_Fixtures", "ARCH_Trim") for c in cols):
        return "none"
    if n == "DOOR_Bed2":
        return "none"
    if any(c.startswith("ARCH_") for c in cols):
        return "complex"
    if COMPLEX.match(n) or n.startswith("ARCH_") or re.match(r"^(EXT|INT)_", n):
        return "complex"
    if NO_COLLISION.search(n) or n == "DOOR_Bed2":
        return "none"
    return "complex"   # per-polygon collision: exact for L-shaped counters, sofas and chairs


# ------------------------------------------------------------------ material description
def upstream_image(sock, depth=0):
    """Follow links back to an image texture; returns (image, channel) where channel in RGB/R/G/B/A."""
    if not sock.is_linked or depth > 6:
        return None, None
    l = sock.links[0]
    n = l.from_node
    if n.type == "TEX_IMAGE" and n.image:
        return n.image, ("A" if l.from_socket.name == "Alpha" else "RGB")
    if n.type in ("SEPARATE_COLOR", "SEPRGB", "SEPARATE_RGB"):
        ch = {"Red": "R", "Green": "G", "Blue": "B", "R": "R", "G": "G", "B": "B"}[l.from_socket.name]
        img, _ = upstream_image(n.inputs[0], depth + 1)
        return img, ch
    if n.type == "NORMAL_MAP":
        return upstream_image(n.inputs["Color"], depth + 1)
    for inp in n.inputs:
        if inp.is_linked and inp.type in ("RGBA", "VECTOR", "VALUE"):
            img, ch = upstream_image(inp, depth + 1)
            if img:
                return img, ch
    return None, None


def img_path(img):
    return os.path.normpath(bpy.path.abspath(img.filepath, library=img.library)) if img else None


def lin(c):
    return [round(float(x), 5) for x in c[:3]]


def describe(m):
    d = {"name": m.name}
    if not m.use_nodes or "Principled BSDF" not in [n.name for n in m.node_tree.nodes] and not any(n.type == "BSDF_PRINCIPLED" for n in m.node_tree.nodes):
        d.update(kind="solid", color=lin(m.diffuse_color), roughness=0.6, metallic=0.0)
        return d
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    I = b.inputs
    if "texset" in m.keys():
        man = json.load(open(os.path.join(BLEND_DIR, "textures", "derived", "manifest.json")))[m["texset"]]
        d.update(kind="textured", D=os.path.join(BLEND_DIR, man["D"]), N=os.path.join(BLEND_DIR, man["N"]) if man.get("N") else None,
                 R=os.path.join(BLEND_DIR, man["R"]) if man.get("R") else None, uv_scale=1.0 / man["size_m"],
                 rough_range=list(m.get("rough_range", [0, 1])), rough=I["Roughness"].default_value,
                 normal_strength=m.get("normal_strength", 1.0), tint=m.get("tint", "#ffffff"), metallic=0.0,
                 two_sided=False)
        return d
    bc_img, _ = upstream_image(I["Base Color"])
    if bc_img:  # imported glTF style material
        r_img, r_ch = upstream_image(I["Roughness"])
        m_img, m_ch = upstream_image(I["Metallic"])
        n_img, _ = upstream_image(I["Normal"])
        a_img, a_ch = upstream_image(I["Alpha"])
        d.update(kind="gltf", D=img_path(bc_img), N=img_path(n_img), R=img_path(r_img), R_ch=r_ch or "G",
                 M=img_path(m_img), M_ch=m_ch or "B", masked=a_img is not None, uv_scale=1.0,
                 rough=I["Roughness"].default_value, metallic=I["Metallic"].default_value,
                 two_sided=a_img is not None)
        return d
    es = I["Emission Strength"].default_value
    d.update(kind="solid", color=lin(I["Base Color"].default_value) if not I["Base Color"].is_linked else lin(m.diffuse_color),
             roughness=round(I["Roughness"].default_value, 3), metallic=round(I["Metallic"].default_value, 3),
             emissive=lin(I["Emission Color"].default_value) if es > 0 else [0, 0, 0], emissive_strength=es,
             transmission=I["Transmission Weight"].default_value, alpha=I["Alpha"].default_value,
             coat=I["Coat Weight"].default_value)
    if d["transmission"] > 0.5:
        d["kind"] = "glass"
        d["roughness"] = I["Roughness"].default_value
    elif d["alpha"] < 0.99:
        d["kind"] = "sheer"
    return d


# ------------------------------------------------------------------ export
scene = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
tmp_col = bpy.data.collections.new("__export_tmp")
scene.collection.children.link(tmp_col)
exported, instances, mats = {}, [], {}
for ob in list(scene.objects):
    if ob.type != "MESH" or ob.hide_render:
        continue
    cols = [c.name for c in ob.users_collection]
    if "99_AssetSource" in cols or "__export_tmp" in cols or ob.name.startswith("PLAN_"):
        continue
    key = ("D:" + ob.data.name) if (not ob.modifiers and ob.data.users > 1) else ("O:" + ob.name)
    asset = "SM_" + sanitize(key[2:])
    if key not in exported:
        eo = ob.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(eo, preserve_all_data_layers=True, depsgraph=dg)
        if len(me.polygons) == 0:
            continue
        tmp = bpy.data.objects.new(asset, me)
        tmp_col.objects.link(tmp)
        for o in scene.objects:
            o.select_set(False)
        tmp.select_set(True)
        bpy.context.view_layer.objects.active = tmp
        path = os.path.join(MESH_DIR, asset + ".fbx")
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, global_scale=1.0,
                                 axis_forward="-Z", axis_up="Y", object_types={"MESH"}, use_mesh_modifiers=False,
                                 mesh_smooth_type="FACE", use_tspace=True, add_leaf_bones=False, bake_anim=False,
                                 path_mode="STRIP", embed_textures=False)
        exported[key] = dict(asset=asset, slots=[s.material.name if s.material else "None" for s in tmp.material_slots],
                             tris=sum(len(p.vertices) - 2 for p in me.polygons))
        for s in tmp.material_slots:
            if s.material and s.material.name not in mats:
                mats[s.material.name] = describe(s.material)
        bpy.data.objects.remove(tmp)
    if key not in exported:
        continue
    mw = ob.matrix_world
    instances.append(dict(name=ob.name, mesh=exported[key]["asset"], matrix=[list(map(float, r)) for r in mw],
                          collection=cols[0] if cols else "", collision=collision_class(ob),
                          shadow=not any(c in ("LGT_Emissive",) for c in cols),
                          cat=ob.get("flat_cat", "")))      # furnishing category (see flat-furnishing skill)

lights = []
for ob in scene.objects:
    if ob.type != "LIGHT" or ob.hide_render:
        continue
    L = ob.data
    fwd = (ob.matrix_world.to_3x3() @ __import__("mathutils").Vector((0, 0, -1))).normalized()
    lights.append(dict(name=ob.name, type=L.type, loc=list(ob.matrix_world.translation), dir=list(fwd), energy=L.energy,
                       color=list(L.color), radius=getattr(L, "shadow_soft_size", 0.05),
                       spot_size=math.degrees(getattr(L, "spot_size", 0)), spot_blend=getattr(L, "spot_blend", 0),
                       cat=ob.get("flat_cat", "")))

markers = {o.name: dict(loc=list(o.location), yaw=math.degrees(o.rotation_euler.z)) for o in scene.objects if o.type == "EMPTY"}
json.dump(dict(instances=instances, meshes=exported, materials=mats, lights=lights, markers=markers),
          open(os.path.join(OUT, "scene.json"), "w"), indent=1)
print("EXPORTED", len(exported), "meshes,", len(instances), "instances,", len(mats), "materials,", len(lights), "lights,",
      sum(v["tris"] for v in exported.values()), "tris")
