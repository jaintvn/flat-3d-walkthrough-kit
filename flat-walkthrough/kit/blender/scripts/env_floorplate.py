"""Traces the tower's typical floor plate (4th-13th floor plan, which includes the 11th floor) into polygons in the
flat's frame (metres).

python env_floorplate.py <plan image> <out json> <debug png>        (numpy, scipy, Pillow, scikit-image)

Registration (measured on reference/plan_typical_04_13.jpg): Type G's party-wall inner face at u = 1083 px, its
NE wall inner face at v = 155 px, 3.61 cm/px (G interior 552 cm = 153 px; 1589 cm = 440 px, both match).
Flat frame: X = (v - 155) * s (page-down, bearing 220), Y = (u - 1083) * s (page-right, bearing 130).
"""
import sys, json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import measure

SRC, OUT, DBG = sys.argv[1:4]
U0, V0, S = 1083.0, 155.0, 0.0361
img = np.asarray(Image.open(SRC).convert("RGB")).astype(float)
H, W, _ = img.shape
bg = np.median(img[50:120, 1500:1700].reshape(-1, 3), 0)
diff = np.abs(img - bg).sum(2)
m = diff > 32
m = ndi.binary_opening(m, iterations=4)          # drops leader lines, dashed balcony outlines and thin text
lab, n = ndi.label(m)
sizes = ndi.sum(m, lab, range(1, n + 1))
m = lab == (1 + int(np.argmax(sizes)))           # the building is the largest component
m = ndi.binary_closing(m, iterations=2)
m = ndi.binary_fill_holes(m)


def to_flat(u, v):
    return [round((v - V0) * S, 3), round((u - U0) * S, 3)]


def flat_to_px(x, y):
    return U0 + y / S, V0 + x / S


def polys(mask):
    out = []
    pad = np.pad(mask, 2)
    for c in measure.find_contours(pad.astype(float), 0.5):
        if len(c) < 20:
            continue
        c = measure.approximate_polygon(c, tolerance=5.0)
        pts = [(p[1] - 2, p[0] - 2) for p in c[:-1]]       # (u, v)
        area = 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
        if abs(area) < 400:
            continue
        out.append([to_flat(u, v) for u, v in pts])
    return out


full = polys(m)
# floor 11: the interior model already contains Type G (walls to the railing line) and the common passage
m11 = m.copy()
# G: from its party wall (shared with F) outwards past the railing line, so no sliver of plate is left around it
for (x0, x1, y0, y1) in ((-1.2, 16.9, -0.20, 6.8), (10.95, 18.0, -2.30, -0.20)):
    u0, v0 = flat_to_px(x0, y0)
    u1, v1 = flat_to_px(x1, y1)
    m11[int(min(v0, v1)) - 1:int(max(v0, v1)) + 2, int(min(u0, u1)) - 1:int(max(u0, u1)) + 2] = False
f11 = polys(m11)
g = [to_flat(u, v) for u, v in ((U0 - 6, V0 - 6), (U0 + 159, V0 - 6), (U0 + 159, V0 + 446), (U0 - 6, V0 + 446))]
json.dump({"scale_m_per_px": S, "origin_px": [U0, V0], "typical": full, "floor11": f11, "g_block": g},
          open(OUT, "w"), indent=0)
vis = Image.fromarray(img.astype(np.uint8)).convert("RGB")
d = ImageDraw.Draw(vis)
for poly, col in [(p, (255, 0, 0)) for p in full] + [(p, (0, 90, 255)) for p in f11 if len(f11) > 0]:
    pts = [flat_to_px(x, y) for x, y in poly]
    if col[2] == 255:
        pts = [(u + 4, v + 4) for u, v in pts]
    d.line(pts + [pts[0]], fill=col, width=3)
vis.save(DBG)
print("typical polys", [len(p) for p in full], "floor11 polys", [len(p) for p in f11])
