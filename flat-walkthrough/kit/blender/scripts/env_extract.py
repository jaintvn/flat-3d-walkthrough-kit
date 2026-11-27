"""Turns satellite imagery, SRTM and OpenStreetMap into placement data for the exterior environment.

python env_extract.py <geo_dir> <out_dir>          (needs numpy, scipy, Pillow)

geo_dir : tiles/<z>_<x>_<y>.jpg (Esri World Imagery, z17 to 3.6 km, z18 to 0.9 km), tiles_meta.json,
          dem_near.npy/json (SRTM 30 m, +-1 km), dem_far.npy/json (SRTM 30 m sampled at 90 m, +-3.6 km), osm.json
out_dir : terrain.npz, houses.json, trees.json, roads.json, landcover_*.png (debug)

Frame: "site" metres, origin at the project pin 11.251028 N 75.818917 E, +E east, +N north, z = metres above the
plot's ground.  The imagery is used only to locate things (canopy, roofs, soil); no imagery pixels are exported
into the scene.
"""
import sys, os, json, math, random
import numpy as np
from scipy import ndimage as ndi
from PIL import Image

GEO, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
# project pin: <geo_dir>/site.json {"lat": .., "lon": ..} (written by geo_fetch.py); the example project's pin (Kozhikode) is the fallback
_site = os.path.join(GEO, "site.json")
LAT0, LON0 = ((lambda d: (d["lat"], d["lon"]))(json.load(open(_site))) if os.path.exists(_site)
              else (11.251028, 75.818917))
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110574.0
rng = random.Random(7)


def tile_px(z, lat, lon):
    n = 2 ** z
    return (lon + 180) / 360 * n * 256, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n * 256


def mosaic(z):
    X0, Y0, n = json.load(open(os.path.join(GEO, "tiles_meta.json")))[str(z)]
    img = np.zeros((n * 256, n * 256, 3), np.uint8)
    for i in range(n):
        for j in range(n):
            f = os.path.join(GEO, "tiles", "%d_%d_%d.jpg" % (z, X0 + i, Y0 + j))
            try:
                img[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] = np.asarray(Image.open(f).convert("RGB"))
            except Exception:
                pass
    # pixel -> site metres (Web Mercator is conformal; linear within a few km at this latitude)
    px0, py0 = tile_px(z, LAT0, LON0)
    mpp = 156543.03392 * math.cos(math.radians(LAT0)) / 2 ** z
    ox, oy = px0 - X0 * 256, py0 - Y0 * 256        # pin position in mosaic pixels
    return img, mpp, ox, oy


def classify(img):
    a = img.astype(np.float32) / 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    mx, mn = a.max(2), a.min(2)
    sat = (mx - mn) / (mx + 1e-4)
    exg = 2 * g - r - b
    # this imagery has a warm/green cast: grey roofs reach ExG 0.06, so vegetation is judged relative to brightness
    # (canopy ExG/lum 0.6-0.75, roofs 0.13-0.16, laterite lanes ~0.3)
    rel = exg / (lum + 1e-3)
    veg = (rel > 0.42) & (lum < 0.40)
    shadow = lum < 0.13
    veg = veg | (shadow & ndi.binary_dilation(veg, iterations=2))
    veg = ndi.binary_opening(veg, iterations=1)
    tile = (r > g * 1.12) & (r > b * 1.30) & (lum > 0.20) & ~veg            # red tile OR laterite soil
    concrete = (rel < 0.36) & (lum > 0.33) & (sat < 0.33) & ~tile & ~veg      # grey/white roofs, concrete
    blue = (b > r * 1.08) & (b > g * 0.98) & (lum > 0.2) & ~veg               # metal sheet / tarpaulin roofs
    return veg, tile, concrete, blue, lum


def rect_of(ys, xs):
    """Oriented bounding rectangle via PCA: centre, (w, d), angle (rad, of the w axis)."""
    c = np.array([xs.mean(), ys.mean()])
    P = np.stack([xs - c[0], ys - c[1]], 1)
    if len(P) < 5:
        return c, (1, 1), 0.0, 0.0
    ev, evec = np.linalg.eigh(np.cov(P.T))
    ax = evec[:, 1]
    ang = math.atan2(ax[1], ax[0])
    R = np.array([[math.cos(ang), math.sin(ang)], [-math.sin(ang), math.cos(ang)]])
    Q = P @ R.T
    w, d = np.ptp(Q[:, 0]) + 1, np.ptp(Q[:, 1]) + 1
    fill = len(P) / (w * d)
    return c, (w, d), ang, fill


def extract_buildings(img, mpp, ox, oy, rmin, rmax, exclude):
    veg, tile, concrete, blue, lum = classify(img)
    H, W = veg.shape
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.hypot((xx - ox) * mpp, (yy - oy) * mpp)
    ring = (dist >= rmin) & (dist < rmax)
    out = []
    for kind, m in (("tile", tile), ("concrete", concrete), ("sheet", blue)):
        m = ndi.binary_opening(m & ring, iterations=1)
        m = ndi.binary_closing(m, iterations=1)
        lab, n = ndi.label(m)
        objs = ndi.find_objects(lab)
        for k, sl in enumerate(objs):
            ys, xs = np.nonzero(lab[sl] == k + 1)
            area = len(ys) * mpp * mpp
            if area < 28 or area > 1800:
                continue
            ys = ys + sl[0].start
            xs = xs + sl[1].start
            c, (w, d), ang, fill = rect_of(ys.astype(float), xs.astype(float))
            wm, dm = w * mpp, d * mpp
            if fill < 0.55 or max(wm, dm) / max(1, min(wm, dm)) > 3.2 or min(wm, dm) < 4.0:
                continue                    # irregular -> soil patch, road, courtyard
            if kind == "tile":
                # laterite soil and tile look alike; real tile roofs have shading (hip ridges) -> higher local variance
                if lum[ys, xs].std() < 0.035:
                    continue
            E = (c[0] - ox) * mpp
            N = -(c[1] - oy) * mpp
            if any(math.hypot(E - ex, N - ey) < er for ex, ey, er in exclude):
                continue
            out.append({"E": round(E, 2), "N": round(N, 2), "w": round(wm, 2), "d": round(dm, 2),
                        "ang": round(-ang, 4), "roof": kind,
                        "rgb": [int(v) for v in img[int(c[1]), int(c[0])]]})
    return out


def dedupe(houses):
    """tile and concrete masks can both fire on one roof: keep the larger of two overlapping detections"""
    houses = sorted(houses, key=lambda h: -h["w"] * h["d"])
    kept, grid = [], {}
    for h in houses:
        r = 0.5 * min(h["w"], h["d"])
        ci, cj = int(h["E"] // 20), int(h["N"] // 20)
        clash = False
        for i in (ci - 1, ci, ci + 1):
            for j in (cj - 1, cj, cj + 1):
                for k in grid.get((i, j), ()):
                    if math.hypot(k["E"] - h["E"], k["N"] - h["N"]) < 0.5 * min(k["w"], k["d"]) + r:
                        clash = True
        if not clash:
            kept.append(h)
            grid.setdefault((ci, cj), []).append(h)
    return kept


def crown_points(img, mpp, ox, oy, rmin, rmax, bearing_ok, spacing):
    """Tree positions: local brightness maxima inside the canopy mask (sunlit crown tops), at least `spacing` m apart;
    gaps filled by jittered grid sampling of the mask so dense groves are not under-populated."""
    veg = classify(img)[0]
    H, W = veg.shape
    lum = img.astype(np.float32).mean(2)
    sm = ndi.gaussian_filter(lum, 1.6 / mpp)
    rad = max(1, int(round(spacing / mpp / 2)))
    peaks = (sm == ndi.maximum_filter(sm, size=2 * rad + 1)) & veg
    ys, xs = np.nonzero(peaks)
    pts = []
    occ = {}
    cell = spacing
    def ok(E, N):
        d = math.hypot(E, N)
        if d < rmin or d >= rmax:
            return False
        b = (math.degrees(math.atan2(E, N)) + 360) % 360
        return bearing_ok(b, d)
    def free(E, N):
        ci, cj = int(E // cell), int(N // cell)
        for i in (ci - 1, ci, ci + 1):
            for j in (cj - 1, cj, cj + 1):
                for (e, n) in occ.get((i, j), ()):
                    if (e - E) ** 2 + (n - N) ** 2 < (spacing * 0.8) ** 2:
                        return False
        return True
    def put(E, N, src):
        occ.setdefault((int(E // cell), int(N // cell)), []).append((E, N))
        pts.append((E, N, src))
    for y, x in zip(ys, xs):
        E, N = (x - ox) * mpp, -(y - oy) * mpp
        if ok(E, N) and free(E, N):
            put(E, N, 1)
    # fill
    step = spacing * 1.05
    e0 = -rmax
    while e0 < rmax:
        n0 = -rmax
        while n0 < rmax:
            E = e0 + rng.uniform(0, step)
            N = n0 + rng.uniform(0, step)
            x, y = int(ox + E / mpp), int(oy - N / mpp)
            if 0 <= x < W and 0 <= y < H and veg[y, x] and ok(E, N) and free(E, N):
                put(E, N, 0)
            n0 += step
        e0 += step
    return pts


def terrain(veg_far, mpp_far, ox_far, oy_far):
    """Bare-earth estimate: SRTM (a surface model) smoothed, minus a canopy allowance, rebased so the plot = 0."""
    out = {}
    for name in ("near", "far"):
        a = np.load(os.path.join(GEO, "dem_%s.npy" % name)).astype(np.float32)
        meta = json.load(open(os.path.join(GEO, "dem_%s.json" % name)))
        step = meta["step"]
        a = ndi.median_filter(a, 3)
        a = ndi.gaussian_filter(a, 45.0 / step)
        n = a.shape[0]
        # canopy fraction per DEM cell from the z17 vegetation mask
        cf = np.zeros_like(a)
        for i in range(n):
            for j in range(n):
                E = (j - (n - 1) / 2) * step
                N = ((n - 1) / 2 - i) * step
                x, y = int(ox_far + E / mpp_far), int(oy_far - N / mpp_far)
                r = int(step / mpp_far / 2)
                win = veg_far[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1]
                cf[i, j] = win.mean() if win.size else 0.6
        a = a - 6.0 * ndi.gaussian_filter(cf, 1)
        out[name] = (a, step)
    near, step = out["near"]
    c = (near.shape[0] - 1) // 2
    base = float(near[c - 1:c + 2, c - 1:c + 2].mean())
    np.savez(os.path.join(OUT, "terrain.npz"), near=out["near"][0] - base, near_step=out["near"][1],
             far=out["far"][0] - base, far_step=out["far"][1], base=base)
    return base


def roads():
    d = json.load(open(os.path.join(GEO, "osm.json")))
    rs = []
    W = {"trunk": 24, "primary": 10, "secondary": 8, "tertiary": 6.5, "unclassified": 5, "residential": 4.5,
         "living_street": 3.5, "service": 3.5, "track": 3}
    for e in d["elements"]:
        t = e.get("tags", {})
        if "highway" not in t or not e.get("geometry"):
            continue
        hw = t["highway"]
        if hw not in W:
            continue
        pts = [((p["lon"] - LON0) * KX, (p["lat"] - LAT0) * KY) for p in e["geometry"]]
        rs.append({"kind": hw, "name": t.get("name", ""), "width": W[hw], "pts": [[round(x, 2), round(y, 2)] for x, y in pts]})
    return rs


def debug_png(img, name, rmax, mpp, ox, oy):
    veg, tile, concrete, blue, lum = classify(img)
    vis = np.zeros(img.shape, np.uint8)
    vis[veg] = (40, 120, 40)
    vis[tile] = (200, 90, 60)
    vis[concrete] = (220, 220, 220)
    vis[blue] = (60, 90, 220)
    r = int(rmax / mpp)
    x0, y0 = int(ox) - r, int(oy) - r
    Image.fromarray(vis[max(0, y0):y0 + 2 * r, max(0, x0):x0 + 2 * r]).save(os.path.join(OUT, "landcover_%s.png" % name))


if __name__ == "__main__":
    known = json.load(open(os.path.join(OUT, "towers.json")))["towers"] if os.path.exists(os.path.join(OUT, "towers.json")) else []
    # towers lean towards NE in this imagery (roof displaced up to ~0.6 x height): exclude base and leaning roof
    exclude = [(t["E"] + k * 0.35 * t["h"], t["N"] + k * 0.3 * t["h"], max(t["w"], t["d"]) * 0.8)
               for t in known for k in (0, 0.5, 1)] + [(17.0, 22.0, 45.0)]   # own plot
    img18, mpp18, ox18, oy18 = mosaic(18)
    img17, mpp17, ox17, oy17 = mosaic(17)
    debug_png(img18, "z18", 450, mpp18, ox18, oy18)
    veg17 = classify(img17)[0]
    base = terrain(veg17, mpp17, ox17, oy17)
    near_ok = lambda b, d: True
    # balconies face 130, bedroom window 40; the far field is only ever seen between ~15 and ~245 deg
    far_ok = lambda b, d: 15 <= b <= 245
    houses = extract_buildings(img18, mpp18, ox18, oy18, 0, 850, exclude)
    houses += [h for h in extract_buildings(img17, mpp17, ox17, oy17, 850, 3500, exclude)
               if far_ok((math.degrees(math.atan2(h["E"], h["N"])) + 360) % 360, 0)]
    trees = crown_points(img18, mpp18, ox18, oy18, 0, 850, near_ok, 7.0)
    trees += crown_points(img17, mpp17, ox17, oy17, 850, 3500, far_ok, 8.5)
    houses = dedupe(houses)
    # land cover rasters for terrain colouring: (veg, bare soil) fractions; row 0 = north
    def cover(img, mpp, ox, oy, half, step):
        veg, tile, concrete, blue, lum = classify(img)
        n = int(2 * half / step) + 1
        out = np.zeros((n, n, 2), np.float32)
        r = max(1, int(step / mpp / 2))
        for i in range(n):
            for j in range(n):
                E = (j - (n - 1) / 2) * step
                N = ((n - 1) / 2 - i) * step
                x, y = int(ox + E / mpp), int(oy - N / mpp)
                v = veg[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1]
                t = tile[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1]
                if v.size:
                    out[i, j] = (v.mean(), t.mean())
                else:
                    out[i, j] = (0.6, 0.05)
        return out
    tz = dict(np.load(os.path.join(OUT, "terrain.npz")))
    tz["cover_near"] = cover(img18, mpp18, ox18, oy18, 1000, 10)
    tz["cover_far"] = cover(img17, mpp17, ox17, oy17, 3600, 90)
    np.savez(os.path.join(OUT, "terrain.npz"), **tz)
    json.dump({"houses": houses}, open(os.path.join(OUT, "houses.json"), "w"))
    json.dump({"trees": [[round(e, 2), round(n, 2), s] for e, n, s in trees]}, open(os.path.join(OUT, "trees.json"), "w"))
    json.dump({"roads": roads()}, open(os.path.join(OUT, "roads.json"), "w"))
    print("base %.1f m  houses %d  trees %d" % (base, len(houses), len(trees)))
