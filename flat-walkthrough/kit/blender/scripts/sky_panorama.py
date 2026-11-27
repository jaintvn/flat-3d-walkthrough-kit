"""Stitches the six overlapping sky captures of the Mac (Lumen) level into an equirectangular panorama for the
mobile sky dome.

Blender -b --factory-startup -P sky_panorama.py -- <unreal/import dir>

reads  <dir>/lightmaps/sky_{px,nx,py,ny,pz,nz}.exr   (written by unreal/scripts/ue_mobile.py, stage skycap)
writes <dir>/lightmaps/sky_panorama.png              sRGB of L / scale, 2048 x 1024, row 0 = straight up
       <dir>/lightmaps/sky_panorama.json             {"scale", "mean"} for the material (M_MobileSky)
Directions are Unreal world axes (X forward, Y right, Z up); the material samples u = atan2(y, x) / 2pi + 0.5,
v = acos(z) / pi.
"""
import bpy, os, sys, json
import numpy as np

D = os.path.join(sys.argv[sys.argv.index("--") + 1], "lightmaps")
W, H = 2048, 1024
# capture orientation per face: forward F, right R, up U (Unreal world)
FACES = {
    "px": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "nx": ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    "py": ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    "ny": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    "pz": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
    "nz": ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
}


def load(name):
    img = bpy.data.images.load(os.path.join(D, "sky_%s.exr" % name))
    w, h = img.size
    a = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1, :, :3]   # row 0 = top
    return a


faces = {k: load(k) for k in FACES}
v, u = np.mgrid[0:H, 0:W]
phi = ((u + 0.5) / W - 0.5) * 2 * np.pi
theta = (v + 0.5) / H * np.pi
d = np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], axis=-1)


FOV = 110.0                                       # = SKY_FOV in ue_mobile.py
T = np.tan(np.radians(FOV / 2))


def stitch(faces):
    """Feathered blend: every face contributes where it sees the direction, weighted by the distance from its edge
    (volumetric clouds differ slightly between captures; the overlap hides the seams)."""
    acc = np.zeros((H, W, 3), np.float32)
    wsum = np.zeros((H, W), np.float32)
    for k, (F, R, U) in FACES.items():
        F, R, U = (np.array(x, np.float32) for x in (F, R, U))
        f = d @ F
        x = (d @ R) / np.maximum(f, 1e-6) / T
        y = (d @ U) / np.maximum(f, 1e-6) / T
        edge = 1 - np.maximum(np.abs(x), np.abs(y))       # 1 at the centre, 0 at the image border
        wgt = np.where(f > 0, np.clip(edge / 0.25, 0, 1) ** 2, 0).astype(np.float32)
        img = faces[k]
        h, w = img.shape[:2]
        col = np.clip(((x + 1) / 2 * w).astype(int), 0, w - 1)
        row = np.clip(((1 - y) / 2 * h).astype(int), 0, h - 1)
        acc += img[row, col] * wgt[..., None]
        wsum += wgt
    return acc / np.maximum(wsum, 1e-6)[..., None]


out = stitch(faces)
lum = 0.2126 * out[..., 0] + 0.7152 * out[..., 1] + 0.0722 * out[..., 2]
upper = lum[: H // 2]
mean = float(upper.mean())                       # brightness of the visible sky (upper hemisphere)
scale = float(np.percentile(lum, 99.5)) * 1.1    # 8-bit range; the sun disc may clip
x = np.clip(out / scale, 0, 1)
srgb = np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)
img = bpy.data.images.new("sky_panorama", W, H, alpha=False)
img.colorspace_settings.name = "Non-Color"
px = np.ones((H, W, 4), np.float32)
px[..., :3] = srgb[::-1]                         # Blender stores rows bottom-up
img.pixels.foreach_set(px.ravel())
img.filepath_raw = os.path.join(D, "sky_panorama.png")
img.file_format = "PNG"
img.save()
json.dump({"scale": scale, "mean": mean}, open(os.path.join(D, "sky_panorama.json"), "w"))
print("SKYPANO mean %.4g scale %.4g" % (mean, scale))
