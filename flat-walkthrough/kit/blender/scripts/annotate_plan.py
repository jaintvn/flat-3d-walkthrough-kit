"""Builds the annotated top-down sheet: original plan (same scale) above the 3D render with labels.
python annotate_plan.py <top_plan.png> <plan.jpg> <out.jpg>"""
import sys
from PIL import Image, ImageDraw, ImageFont
top_p, plan_p, out = sys.argv[1:4]
X0, X1, Y0, Y1 = -60, 1840, -280, 680
KX, OX, KY, OY = 1314 / 1589, 505, 464 / 552, 957
top = Image.open(top_p).convert("RGBA")
W, H = top.size
s = W / 2850
bg = Image.new("RGBA", (W, H), (240, 235, 226, 255))
render = Image.alpha_composite(bg, top).convert("RGB")
sx, sy = (X1 - X0) / W, (Y1 - Y0) / H
plan = Image.open(plan_p).convert("RGB")
warped = plan.transform((W, H), Image.AFFINE, (KX * sx, 0, OX + KX * X0, 0, KY * sy, OY - KY * Y1), Image.BICUBIC)
F = lambda n: ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", max(10, int(n * s)))
def P(x, y):
    return ((x - X0) / sx, (Y1 - y) / sy)
d = ImageDraw.Draw(render)
labels = [  # x, y, name, dims, tag
    (195, 170, "BEDROOM 1", "390 x 390", "C"), (567, 300, "BEDROOM 2", "330 x 390", "C"),
    (270, 477, "TOILET 1", "240 x 150", "C"), (819, 400, "TOILET 2", "150 x 240", "C"),
    (60, 440, "BALCONY 1", "150 x 233*", "C~"), (1060, 520, "BALCONY 2", "300 x 150*", "C~"),
    (1409, 455, "KITCHEN", "360 x 240", "C"), (1060, 40, "DINING", "300 x 413", "C"),
    (1400, 40, "LIVING", "383 x 300", "C"), (720, 40, "FOYER", "150 wide", "C"),
    (819, 135, "WASH", "~150 x 55", "M"), (468, 120, "BED-1 ENTRY", "~132 x 150", "M"),
    (1450, -140, "COMMON PASSAGE", "context only", "E"),
]
for x, y, n, dim, tag in labels:
    px, py = P(x, y)
    for txt, f, dy in ((n, F(30), -18 * s), (dim + "  [" + tag + "]", F(24), 16 * s)):
        bb = d.textbbox((0, 0), txt, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.rectangle((px - tw / 2 - 6 * s, py + dy - th / 2 - 5 * s, px + tw / 2 + 6 * s, py + dy + th / 2 + 7 * s), fill=(255, 255, 255, 215))
        d.text((px - tw / 2, py + dy - th / 2 - bb[1]), txt, fill=(40, 30, 25), font=f)
# small markers
for x, y, t in ((540, 105, "D 90"), (687, 175, "D 90"), (188, 380, "D 75"), (760, 260, "D 75"), (1521, -32, "MAIN DOOR 105"),
                (1261, 360, "OPENING ~93"), (285, 590, "DUCT"), (700, 600, "VENT CUT-OUT"), (845, 600, "SHAFT"), (1554, 346, "SHAFT")):
    px, py = P(x, y)
    f = F(20)
    bb = d.textbbox((0, 0), t, font=f)
    d.rectangle((px - 4 * s, py - 4 * s, px + bb[2] + 4 * s, py + bb[3] + 4 * s), fill=(255, 244, 214))
    d.text((px, py), t, fill=(150, 60, 20), font=f)
# scale bar 1 m and compass note
bx, by = P(1150, -230)
d.rectangle((bx, by, bx + 100 / sx, by + 10 * s), fill=(30, 30, 30))
d.text((bx, by + 14 * s), "1 m", fill=(30, 30, 30), font=F(22))
# combine sheet: plan crop (same scale) above the render
panel_h = H
sheet = Image.new("RGB", (W, H * 2 + int(120 * s)), (250, 247, 241))
sheet.paste(warped, (0, int(60 * s)))
sheet.paste(render, (0, H + int(120 * s)))
d2 = ImageDraw.Draw(sheet)
d2.text((20 * s, 12 * s), "A. Your plan (plan_my_flat.jpg), re-sampled to the model's scale", fill=(60, 40, 30), font=F(34))
d2.text((20 * s, H + 70 * s), "B. Blender model - orthographic top view, cut at 2.0 m.   [C] printed dimension  [M] measured from drawing  [E] estimate   * see notes", fill=(60, 40, 30), font=F(34))
sheet.save(out, quality=92)
render.save(out.replace(".jpg", "_labels.jpg"), quality=92)
print("ok", sheet.size)
