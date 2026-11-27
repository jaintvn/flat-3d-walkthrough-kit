"""Builds previews/<dir>/review.html with relative image links."""
import sys, os, html
d = sys.argv[1]
views = [("plan_comparison.jpg", "Top-down: your plan (A) vs. the model (B), same scale"),
         ("plan_overlay_walls.jpg", "Wall check: plan wall pixels (red) drawn over the model"),
         ("01_cutaway_overview.jpg", "Cut-away overview from the balcony side"),
         ("view_living.jpg", "Living room, from the foyer"), ("view_dining.jpg", "Dining + feature wall, from the living room"),
         ("view_kitchen.jpg", "Kitchen"), ("view_foyer.jpg", "Foyer, from bedroom-1 door towards living"),
         ("view_vanity.jpg", "Wash-basin alcove off the foyer"), ("view_bed1.jpg", "Bedroom 1 (master)"),
         ("view_bed1b.jpg", "Bedroom 1 - wardrobe, desk, balcony slider"), ("view_bed2.jpg", "Bedroom 2"),
         ("view_toilet1.jpg", "Toilet 1"), ("view_toilet2.jpg", "Toilet 2"), ("view_balcony2.jpg", "Balcony 2 from the dining")]
cards = "\n".join('<figure><a href="%s"><img src="%s" loading="lazy"></a><figcaption>%s</figcaption></figure>' % (f, f, html.escape(c))
                  for f, c in views if os.path.exists(os.path.join(d, f)))
page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Type G Flat Review</title><style>
:root{--bg:#f6f2ea;--fg:#2d241d;--card:#fff;--mut:#7a6d60}
@media (prefers-color-scheme:dark){:root{--bg:#1d1a17;--fg:#eee6da;--card:#28241f;--mut:#a89a8a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,Helvetica,sans-serif}
main{max-width:1500px;margin:auto;padding:16px}
h1{font-weight:600;margin:.4em 0}p{color:var(--mut);max-width:70ch}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%%,460px),1fr));gap:14px}
figure{margin:0;background:var(--card);border-radius:8px;overflow:hidden}
figure:nth-child(-n+2){grid-column:1/-1}
img{width:100%%;display:block}figcaption{padding:8px 12px;font-size:14px}
</style></head><body><main><h1>Type G 2BHK - Blender checkpoint</h1>
<p>Click any image for full size. Architecture follows both floor plans; interiors follow the Landmark Marquis / Lareina / Meritus renders. See docs/01_plan_analysis_and_design.md for confirmed vs. estimated items.</p>
<div class="grid">%s</div></main></body></html>""" % cards
open(os.path.join(d, "review.html"), "w").write(page)
print("ok")
