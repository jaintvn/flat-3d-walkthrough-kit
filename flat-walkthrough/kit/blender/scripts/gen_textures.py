"""Generates the project's texture set into blender/textures/derived (numpy + Pillow).

* Polished marble-look vitrified floor tiles (80x80 cm, 2 mm grout) - generated
* White quartz (counters, splashback) - generated
* Bathroom wall tiles (60x120 cm, matte stone look) - generated
* Recoloured versions of the Poly Haven CC0 scans (fabrics, woods, plaster)
Writes textures/derived/manifest.json: name -> {D, N, R, size_m}
python gen_textures.py <blender_dir>
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageFilter

ROOT = sys.argv[1]
SRC = os.path.join(ROOT, "textures")
OUT = os.path.join(SRC, "derived")
os.makedirs(OUT, exist_ok=True)
MAN = {}


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0


def tile_noise(n, cells, rng):
    """Tileable value noise in [0,1] (n x n) from a cells x cells random grid."""
    g = rng.random((cells, cells)).astype(np.float32)
    big = np.tile(g, (3, 3))
    im = Image.fromarray(big, "F").resize((3 * n, 3 * n), Image.BICUBIC)
    return np.asarray(im, np.float32)[n:2 * n, n:2 * n]


def fbm(n, rng, base=3, octaves=6, gain=0.5):
    acc, amp, tot = np.zeros((n, n), np.float32), 1.0, 0.0
    for o in range(octaves):
        acc += amp * tile_noise(n, base * 2 ** o, rng)
        tot += amp
        amp *= gain
    acc /= tot
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-6)


def save(name, arr, mode="RGB"):
    p = os.path.join(OUT, name + ".png")
    a = np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(a, mode if a.ndim == 3 else "L").save(p, optimize=True)
    return "textures/derived/" + name + ".png"


def normal_from_height(h, strength):
    gy, gx = np.gradient(h)
    nx, ny = -gx * strength, gy * strength          # OpenGL convention (+Y up)
    nz = np.ones_like(h)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / l * 0.5 + 0.5, ny / l * 0.5 + 0.5, nz / l * 0.5 + 0.5], -1)


# ------------------------------------------------------------------ marble floor (2x2 tiles of 80 cm)
def blur(a, r):
    h, w = a.shape
    im = Image.fromarray(a.astype(np.float32), "F")
    small = im.resize((max(1, int(w / r)), max(1, int(h / r))), Image.BILINEAR)
    return np.asarray(small.resize((w, h), Image.BICUBIC), np.float32)


def marble_tile(n, seed, base, vein, faint):
    """Directional, branching veins with varying width and soft halos (Statuario-style print)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n
    ang = rng.uniform(-0.6, 0.6) + (np.pi / 4 if seed % 2 else -np.pi / 4)
    lin = x * np.cos(ang) + y * np.sin(ang)
    lin2 = x * np.cos(ang + 0.5) + y * np.sin(ang + 0.5)
    t1, t2, t3 = fbm(n, rng, 2, 7), fbm(n, rng, 3, 7), fbm(n, rng, 4, 6)
    wv, fade = fbm(n, rng, 2, 4), fbm(n, rng, 2, 4)
    f = lin * 2.6 + t1 * 0.95 + t2 * 0.30 + rng.uniform(0, 1)
    width = 0.0006 + 0.006 * wv ** 2
    v_main = np.exp(-(np.sin(np.pi * f) ** 2) / width) * np.clip(fade * 1.6 - 0.25, 0, 1)
    g = lin2 * 5.0 + t3 * 0.8 + t1 * 0.3
    v_fine = np.exp(-(np.sin(np.pi * g) ** 2) / 0.0005) * np.clip(1.2 - fade * 1.5, 0, 1) * 0.5
    halo = blur(v_main, 10) * 0.9
    cloud = fbm(n, rng, 2, 5)
    col = base[None, None] * (0.97 + 0.05 * cloud[..., None])
    col = col * (1 - 0.18 * halo[..., None]) + faint * 0.18 * halo[..., None]
    m = np.clip(v_main * 0.75 + v_fine * 0.45, 0, 1)[..., None]
    col = col * (1 - m) + vein * m
    return np.clip(col, 0, 1), cloud


def gen_marble():
    n, T = 1024, 2
    base, vein, faint = hexc("#efe8dc"), hexc("#a99073"), hexc("#d8ccb8")
    D = np.zeros((n * T, n * T, 3), np.float32)
    R = np.zeros((n * T, n * T), np.float32)
    Hh = np.ones((n * T, n * T), np.float32)
    for i in range(T):
        for j in range(T):
            c, cl = marble_tile(n, 100 + i * 7 + j, base, vein, faint)
            D[i * n:(i + 1) * n, j * n:(j + 1) * n] = c
            R[i * n:(i + 1) * n, j * n:(j + 1) * n] = 0.07 + 0.06 * cl
    g = 2  # px of grout on each tile edge -> ~3 mm joint
    grout = np.zeros((n * T, n * T), bool)
    for k in range(T):
        for sl in (slice(k * n, k * n + g), slice((k + 1) * n - g, (k + 1) * n)):
            grout[sl, :] = True
            grout[:, sl] = True
    D[grout] = hexc("#d6cdbd")
    R[grout] = 0.8
    Hh[grout] = 0.0
    Hh = np.asarray(Image.fromarray((Hh * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    MAN["Floor_Marble"] = dict(D=save("T_Floor_Marble_D", D), N=save("T_Floor_Marble_N", normal_from_height(Hh, 3.0)),
                               R=save("T_Floor_Marble_R", R), size_m=1.6)


def gen_quartz():
    n = 2048
    rng = np.random.default_rng(7)
    cl = fbm(n, rng, 3, 6)
    base = hexc("#f3f0eb")
    D = base[None, None] * (0.975 + 0.04 * cl[..., None])
    # fine grey speckle
    sp = rng.random((n, n)) > 0.9965
    spk = np.asarray(Image.fromarray((sp * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    D = D * (1 - 0.6 * spk[..., None]) + hexc("#9b958c") * 0.6 * spk[..., None]
    # very faint soft veins (tileable: built only from tileable noise)
    t = fbm(n, rng, 2, 6)
    v = np.exp(-(np.sin(np.pi * t * 5.0) ** 2) / 0.004) * 0.0
    D = D * (1 - v[..., None]) + hexc("#b7b0a6") * v[..., None]
    R = 0.06 + 0.04 * cl
    MAN["Quartz"] = dict(D=save("T_Quartz_D", D), N=None, R=save("T_Quartz_R", R), size_m=2.0)


def gen_bathwall():
    # 2 tiles wide (60 cm each) x 1 tile tall (120 cm) -> 1.2 m square, 2048 px
    n = 2048
    rng = np.random.default_rng(21)
    D = np.zeros((n, n, 3), np.float32)
    R = np.zeros((n, n), np.float32)
    half = n // 2
    for j in range(2):
        cl = fbm(n, rng, 2, 6)[:, :half]
        t = fbm(n, rng, 2, 6)[:, :half]
        y, x = np.mgrid[0:n, 0:half].astype(np.float32) / n
        f = y * 1.5 + t * 2.0
        v = np.exp(-(np.sin(np.pi * f * 1.4) ** 2) / 0.01) * 0.03
        base = hexc("#dcd3c6") * (0.96 + 0.07 * cl[..., None])
        D[:, j * half:(j + 1) * half] = base * (1 - v[..., None]) + hexc("#bdb1a0") * v[..., None]
        R[:, j * half:(j + 1) * half] = 0.32 + 0.1 * cl
    Hh = np.ones((n, n), np.float32)
    g = 2
    grout = np.zeros((n, n), bool)
    for sl in (slice(0, g), slice(n - g, n), slice(half - g, half + g)):
        grout[:, sl] = True
    for sl in (slice(0, g), slice(n - g, n)):
        grout[sl, :] = True
    D[grout] = hexc("#c9bfb1")
    R[grout] = 0.85
    Hh[grout] = 0
    Hh = np.asarray(Image.fromarray((Hh * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
    MAN["Bath_Wall"] = dict(D=save("T_Bath_Wall_D", D), N=save("T_Bath_Wall_N", normal_from_height(Hh, 2.5)),
                            R=save("T_Bath_Wall_R", R), size_m=1.2)


# ------------------------------------------------------------------ recolours of Poly Haven scans
def load(name, kind):
    suf = {"D": "diff", "N": "nor_gl", "R": "rough"}[kind]
    return os.path.join(SRC, name, "%s_%s_2k.jpg" % (name, suf))


def rel(p):
    return os.path.relpath(p, ROOT)


def lum(name):
    a = np.asarray(Image.open(load(name, "D")).convert("RGB"), np.float32) / 255
    return a @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def gradmap(src, out, dark, light, size, lo=2, hi=98, gamma=1.0):
    L = lum(src)
    a, b = np.percentile(L, lo), np.percentile(L, hi)
    t = np.clip((L - a) / (b - a + 1e-6), 0, 1) ** gamma
    D = hexc(dark) * (1 - t[..., None]) + hexc(light) * t[..., None]
    MAN[out] = dict(D=save("T_" + out + "_D", D), N=rel(load(src, "N")), R=rel(load(src, "R")), size_m=size)


def tint(src, out, color, size, contrast=1.0):
    L = lum(src)
    L = 1 + (L / L.mean() - 1) * contrast
    D = np.clip(hexc(color)[None, None] * L[..., None], 0, 1)
    MAN[out] = dict(D=save("T_" + out + "_D", D), N=rel(load(src, "N")), R=rel(load(src, "R")), size_m=size)


def as_is(src, out, size, mul=1.0):
    a = np.asarray(Image.open(load(src, "D")).convert("RGB"), np.float32) / 255 * mul
    MAN[out] = dict(D=save("T_" + out + "_D", a), N=rel(load(src, "N")), R=rel(load(src, "R")), size_m=size)


gen_marble()
gen_quartz()
gen_bathwall()
gradmap("smoked_walnut_veneer", "Walnut", "#2b1a0f", "#7c5638", 1.0, gamma=0.9)
gradmap("natural_walnut_veneer", "Walnut_Door", "#25160c", "#5f402a", 1.0)
gradmap("white_oak_veneer", "Oak", "#8d6a48", "#cfae86", 0.5)
for nm, c in (("Beige", "#cbbfac"), ("Grey", "#8f8b86"), ("Taupe", "#9e8b77"), ("Sage", "#8c9b87"), ("Cream", "#ebe5da"),
              ("Charcoal", "#4b4947"), ("White", "#f2efe9"), ("Drape", "#ab9882")):
    tint("rough_linen", "Linen_" + nm, c, 0.27, contrast=1.3)
tint("velour_velvet", "Velvet_Grey", "#827d78", 0.28, contrast=1.2)
tint("velour_velvet", "Velvet_Beige", "#c9baa4", 0.28, contrast=1.2)
tint("leather_white", "Leather_Cream", "#e2dace", 0.3)
tint("plastered_wall_04", "Paint_Wall", "#e7ddcc", 3.2, contrast=0.35)
tint("plastered_wall_04", "Paint_Ceiling", "#f5f2ec", 3.2, contrast=0.25)
tint("plastered_wall_04", "Paint_Ext", "#e9e3d8", 3.2, contrast=0.6)
tint("rough_linen", "Rug_Beige", "#c3b39c", 0.6, contrast=2.2)
tint("rough_linen", "Rug_Grey", "#9a948d", 0.6, contrast=2.2)
as_is("granite_tile", "Toilet_Floor", 2.3, mul=1.35)
as_is("marble_01", "Balcony_Stone", 1.5)
as_is("concrete_floor_01", "Concrete", 2.0)
as_is("laminate_floor_02", "Laminate", 1.7)
def gen_art(name, cols, seed):
    n = 1024
    rng = np.random.default_rng(seed)
    f = fbm(n, rng, 2, 7) * 0.7 + fbm(n, rng, 4, 5) * 0.3
    f = (f - f.min()) / (f.max() - f.min())
    stops = np.linspace(0, 1, len(cols))
    C = np.stack([hexc(c) for c in cols])
    D = np.zeros((n, n, 3), np.float32)
    for k in range(3):
        D[..., k] = np.interp(f, stops, C[:, k])
    brush = fbm(n, rng, 32, 3)
    D *= (0.94 + 0.08 * brush[..., None])
    MAN[name] = dict(D=save("T_" + name + "_D", np.clip(D, 0, 1)), N=None, R=None, size_m=1.2)


gen_art("Art_Gold", ["#2c2a33", "#7b5a2e", "#d9a441", "#f0d48a", "#efe6cf", "#5b6f7c"], 41)
gen_art("Art_Calm", ["#e8e1d4", "#c9b79c", "#8e9a8b", "#5d6b66", "#e8e1d4"], 42)
json.dump(MAN, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
print("generated", len(MAN), "texture sets")
