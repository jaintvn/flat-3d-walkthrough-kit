"""Overlay the orthographic top render on plan_my_flat.jpg (same orientation) for checking.
python compare_plan.py <top_plan.png> <plan.jpg> <out_prefix>"""
import sys
from PIL import Image, ImageChops, ImageDraw, ImageFont
top_p, plan_p, out = sys.argv[1:4]
X0, X1, Y0, Y1 = -60, 1840, -280, 680
# plan pixel mapping measured from the drawing (inner wall faces):
#   x=0 -> px 505, x=1589 -> px 1819 ; y=0 -> py 957, y=552 -> py 493
KX, OX, KY, OY = 1314 / 1589, 505, 464 / 552, 957
top = Image.open(top_p).convert("RGBA")
W, H = top.size
bg = Image.new("RGBA", (W, H), (236, 230, 220, 255))
top = Image.alpha_composite(bg, top).convert("RGB")
sx, sy = (X1 - X0) / W, (Y1 - Y0) / H
plan = Image.open(plan_p).convert("RGB")
warped = plan.transform((W, H), Image.AFFINE, (KX * sx, 0, OX + KX * X0, 0, KY * sy, OY - KY * Y1), Image.BICUBIC)
top.save(out + "_render.jpg", quality=92)
Image.blend(top, warped, 0.5).save(out + "_overlay.jpg", quality=92)
# wall-line overlay: plan's dark wall pixels painted red over the render
g = warped.convert("L").point(lambda v: 255 if v < 50 else 0)
red = Image.new("RGB", (W, H), (230, 20, 20))
comp = top.copy(); comp.paste(red, mask=g)
comp.save(out + "_walls.jpg", quality=92)
print("ok", W, H)
