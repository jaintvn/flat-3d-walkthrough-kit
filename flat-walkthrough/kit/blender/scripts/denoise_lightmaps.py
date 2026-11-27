"""Denoises the baked lightmaps (OIDN via the compositor) and encodes them as sRGB PNGs for Unreal.

Blender -b --factory-startup -P denoise_lightmaps.py -- <unreal/import dir>

reads  <dir>/lightmaps/raw/LM_*.npy       (float16 RGB, from bake_lightmaps.py)
writes <dir>/lightmaps/png/LM_*.png       sRGB colour of L / RANGE (no alpha); decode in the material: texture (sRGB) * RANGE.
                                          (RGBM was tried first: phone ASTC compression turned its alpha scale into visible blocks.)
"""
import bpy, os, sys, glob, time
import numpy as np

DIR = sys.argv[sys.argv.index("--") + 1]
RAW = os.path.join(DIR, "lightmaps", "raw")
PNG = os.path.join(DIR, "lightmaps", "png")
TMP = os.path.join(DIR, "lightmaps", "_dn.exr")
os.makedirs(PNG, exist_ok=True)
RANGE = 4.0
T0 = time.time()

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.render.resolution_percentage = 100
sc.render.use_compositing = True
sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "OPEN_EXR"
sc.render.image_settings.color_depth = "32"
sc.render.filepath = TMP
for o in list(sc.objects):
    bpy.data.objects.remove(o)
ng = bpy.data.node_groups.new("dn", "CompositorNodeTree")
sc.compositing_node_group = ng
n_img = ng.nodes.new("CompositorNodeImage")
n_dn = ng.nodes.new("CompositorNodeDenoise")
n_dn.inputs["HDR"].default_value = True
out = ng.nodes.new("NodeGroupOutput")
ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
ng.links.new(n_img.outputs["Image"], n_dn.inputs["Image"])
ng.links.new(n_dn.outputs["Image"], out.inputs[0])

files = sorted(glob.glob(os.path.join(RAW, "LM_*.npy")))
for i, f in enumerate(files):
    name = os.path.splitext(os.path.basename(f))[0]
    a = np.load(f).astype(np.float32)
    h, w = a.shape[:2]
    src = bpy.data.images.new("src", w, h, float_buffer=True, alpha=False)
    px = np.ones((h, w, 4), np.float32)
    px[:, :, :3] = a
    src.pixels.foreach_set(px.ravel())
    n_img.image = src
    sc.render.resolution_x, sc.render.resolution_y = w, h
    bpy.ops.render.render(write_still=True)
    r = bpy.data.images.load(TMP, check_existing=False)
    o = np.empty(w * h * 4, np.float32)
    r.pixels.foreach_get(o)
    L = np.maximum(o.reshape(h, w, 4)[:, :, :3], 0.0)
    bpy.data.images.remove(r)
    bpy.data.images.remove(src)
    x = np.clip(L / RANGE, 0, 1)
    srgb = np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)
    enc = np.concatenate([srgb, np.ones((h, w, 1), np.float32)], axis=2)
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"           # values are already sRGB-encoded
    img.pixels.foreach_set(enc.astype(np.float32).ravel())
    img.filepath_raw = os.path.join(PNG, name + ".png")
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    if i % 25 == 0:
        print("DENOISE [%4.0fs] %d/%d %s" % (time.time() - T0, i + 1, len(files), name), flush=True)
if os.path.exists(TMP):
    os.remove(TMP)
print("DENOISE done %d lightmaps in %.0fs" % (len(files), time.time() - T0))
