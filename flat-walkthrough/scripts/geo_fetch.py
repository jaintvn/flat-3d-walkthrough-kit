#!/usr/bin/env python3
"""Downloads the geo inputs for the flat-environment pipeline (blender/scripts/env_extract.py) around one pin.

python3 geo_fetch.py --lat 11.251028 --lon 75.818917 --out <geo dir> [--far-km 3.6] [--near-km 0.9] [--dry-run]

Writes (the layout env_extract.py reads):
  tiles/<z>_<x>_<y>.jpg     Esri World Imagery, z17 to +-far-km, z18 to +-near-km   (reference only; never ship pixels)
  tiles_meta.json           {"17": [X0, Y0, n], "18": [...]}   n x n tiles from (X0, Y0)
  dem_near.npy/json         SRTM 30 m grid, +-1.0 km, step 30 m   (row 0 = north, col 0 = west; centre = pin)
  dem_far.npy/json          SRTM 30 m sampled every 90 m, +-far-km
  osm.json                  Overpass: roads to +-far-km, buildings to +-1 km, named places to +-far-km (ODbL)
  site.json                 {"lat", "lon"}

Sends the pin's coordinates to server.arcgisonline.com, api.opentopodata.org and overpass-api.de: tell the user and
get their OK before running (it is their home's location). Polite rate limits: tiles 8/s, DEM 1 request/s
(opentopodata public limit: 100 points/request, 1000 requests/day), one Overpass query.
"""
import argparse, json, math, os, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "flat-walkthrough-geo/1.0"}
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
TOPO = "https://api.opentopodata.org/v1/srtm30m?locations="
OVERPASS = "https://overpass-api.de/api/interpreter"


def get(url, data=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def tile_xy(z, lat, lon):
    n = 2 ** z
    return ((lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def tile_plan(lat, lon, z, half_km):
    mpt = 156543.03392 * math.cos(math.radians(lat)) / 2 ** z * 256      # metres per tile
    r = int(math.ceil(half_km * 1000 / mpt))
    cx, cy = tile_xy(z, lat, lon)
    X0, Y0 = int(cx) - r, int(cy) - r
    return X0, Y0, 2 * r + 1


def dem_grid(lat, lon, half_m, step):
    n = 2 * int(math.ceil(half_m / step)) + 1
    kx = 111320 * math.cos(math.radians(lat))
    ky = 110574.0
    pts = []
    for i in range(n):
        N = ((n - 1) / 2 - i) * step
        for j in range(n):
            E = (j - (n - 1) / 2) * step
            pts.append((lat + N / ky, lon + E / kx))
    return n, pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--far-km", type=float, default=3.6)
    ap.add_argument("--near-km", type=float, default=0.9)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    meta = {str(z): tile_plan(a.lat, a.lon, z, h) for z, h in ((17, a.far_km), (18, a.near_km))}
    grids = {"near": (1000.0, 30.0), "far": (a.far_km * 1000, 90.0)}
    n_tiles = sum(v[2] ** 2 for v in meta.values())
    n_dem = {k: dem_grid(a.lat, a.lon, h, s)[0] ** 2 for k, (h, s) in grids.items()}
    print("tiles %d (%s), DEM points %s -> %d requests, 1 Overpass query"
          % (n_tiles, meta, n_dem, sum(math.ceil(v / 100) for v in n_dem.values())))
    if a.dry_run:
        return
    import numpy as np
    out = a.out
    os.makedirs(os.path.join(out, "tiles"), exist_ok=True)
    json.dump({"lat": a.lat, "lon": a.lon}, open(os.path.join(out, "site.json"), "w"))
    json.dump(meta, open(os.path.join(out, "tiles_meta.json"), "w"))

    # imagery
    done = 0
    for z, (X0, Y0, n) in meta.items():
        for i in range(n):
            for j in range(n):
                f = os.path.join(out, "tiles", "%s_%d_%d.jpg" % (z, X0 + i, Y0 + j))
                if not os.path.exists(f):
                    try:
                        open(f, "wb").write(get(ESRI.format(z=z, x=X0 + i, y=Y0 + j)))
                    except Exception as e:
                        print("tile failed", z, X0 + i, Y0 + j, e)
                    time.sleep(0.125)
                done += 1
        print("tiles z%s done (%d)" % (z, done))

    # elevation
    for name, (half, step) in grids.items():
        n, pts = dem_grid(a.lat, a.lon, half, step)
        vals = []
        for k in range(0, len(pts), 100):
            chunk = pts[k:k + 100]
            q = "|".join("%.6f,%.6f" % p for p in chunk)
            res = json.loads(get(TOPO + urllib.parse.quote(q, safe="|,.")))["results"]
            vals += [r["elevation"] if r["elevation"] is not None else float("nan") for r in res]
            time.sleep(1.05)
        arr = np.array(vals, np.float32).reshape(n, n)
        if np.isnan(arr).any():
            arr[np.isnan(arr)] = np.nanmean(arr)
        np.save(os.path.join(out, "dem_%s.npy" % name), arr)
        json.dump({"step": step, "n": n, "lat0": a.lat, "lon0": a.lon, "dataset": "srtm30m"},
                  open(os.path.join(out, "dem_%s.json" % name), "w"))
        print("DEM %s %dx%d  min %.1f max %.1f" % (name, n, n, float(arr.min()), float(arr.max())))

    # OpenStreetMap
    R, Rb = int(a.far_km * 1000), 1000
    q = ("[out:json][timeout:180];("
         'way["highway"](around:%d,%f,%f);way["building"](around:%d,%f,%f);'
         'node["name"](around:%d,%f,%f);way["name"]["building"](around:%d,%f,%f););out geom;'
         % (R, a.lat, a.lon, Rb, a.lat, a.lon, R, a.lat, a.lon, R, a.lat, a.lon))
    data = get(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode())
    open(os.path.join(out, "osm.json"), "wb").write(data)
    print("OSM elements", len(json.loads(data)["elements"]))
    print("GEO OK", out)


if __name__ == "__main__":
    main()
