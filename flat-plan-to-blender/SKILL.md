---
name: flat-plan-to-blender
description: Read an apartment floor plan image (unit plan, floor-plate plan, builder brochure) and build an exact-dimension 3D shell of the flat in Blender by script, with walls, openings, doors, windows, sliders, ducts, balconies, false ceilings and lights, then prove it matches the plan with a top-down overlay. Stage 1 of the flat-walkthrough pipeline (start from the flat-walkthrough skill for intake and project setup). Use when writing or fixing layout.py / build_flat.py, measuring a plan, resolving dimension conflicts, or checking the model against the drawing.
---

# Plan → Blender shell

Project scripts are under `blender/scripts/` (copied by flat-walkthrough's scaffold). The ones you rewrite for a
new flat are `layout.py` (all data) and the flat-specific builders in `build_flat.py`. `lib.py` and `items.py`
are a generic toolkit; keep them.

## 1. Read the plan (write `docs/01_plan_analysis_and_design.md` §1–4 as you go)

- Read every image. If there are two plans (the user's unit plan and the builder's floor plate), find the rotation
  between them and cross-check every room, door swing, duct and window. Report any mismatch; don't resolve it
  silently.
- **Frame:** origin is the inner face of one exterior corner, +X along the long axis, +Y towards the balconies,
  z = 0 at finished floor, all in **cm**. Write the compass bearing of +Y in a comment, and later in
  `site.json`.
- **Scale:** measure cm/px from at least two printed dimensions in each direction, then choose internal and
  external wall thicknesses so the printed room sizes **add up exactly** along every row and column. Write
  the sums out, e.g. `390+12+330+12+150+12+300+383 = 1589`. Tag every value [C] printed, [M] measured or
  [E] estimated.
- Check the area table: rooms from printed sizes should land within ±5% of the stated carpet area. Plaster
  vs structural measurement explains about 3–4%.
- Typical conflicts: balcony depth measured to the railing line vs the wall face; door swings that clash;
  windows without printed widths; vents/ducts marked "unusable area". List them as open questions with the
  choice made.

## 2. Write `layout.py`

Data only (see the Type G version for the schema):
- `ZONES` (name, kind, x0, x1, y0, y1). `kind` is room/wet/kitchen/balcony/service/vanity/passage; it drives
  floor and wall finishes and false-ceiling heights.
- `wall(name, x0, x1, y0, y1, openings, h)`, where an opening is `(a0, a1, sill, head, kind)` and kind is
  door/door_main/window/vent/slider/arch. Prefix external walls `EXT_`, partitions `INT_`, outside context `CTX_`.
- `DOORS` (name, hinge, closed_dir, swing_normal, clear width, open angle). Open the doors so they rest against
  walls: the player can't open doors in the game.
- `SPAWN` = (x, y, z, yaw), just inside the main door, facing the living room.
- Heights: `H_SLAB`, `DOOR_H`, sills (see the intake defaults).

## 3. Build and check

```
Blender -b --factory-startup -P blender/scripts/build_flat.py -- blender/flat_<slug>.blend
python3 blender/scripts/gen_textures.py blender
Blender -b blender/flat_<slug>.blend -P blender/scripts/render_previews.py -- previews/checkpoint_v1 top 64 100
python3 blender/scripts/compare_plan.py previews/checkpoint_v1/top_plan.png reference/<plan>.jpg previews/checkpoint_v1/plan
```
- Update `compare_plan.py` / `annotate_plan.py` with the plan's pixel registration: `KX, OX, KY, OY` from two
  wall faces per axis, plus the room labels.
- **Acceptance:** in `*_walls.jpg`, the plan's wall pixels (red) sit on the model's walls within a few cm
  everywhere. Fix layout.py until they do. Show this overlay to the user at checkpoint 1.
- `build_flat.py` sets `flat_cat` on every object through `categories.py`. Look at the
  "CATEGORIES defaulted" line it prints: anything that isn't architecture needs a name the rules match, or an
  explicit `ob["flat_cat"]` (see flat-furnishing).
- Placeholder context (`CTX_Ground`, `CTX_Buildings`, `CTX_Trees`, `CTX_Facade` in collection `05_Context`)
  gives windows something to show until flat-environment replaces it.

## 4. Checkpoint renders

`render_previews.py`: rewrite `CAMS` with one eye-height (160 cm) camera per room, plus `top` and `iso`
(cut-away). `make_review_page.py` builds `previews/<dir>/review.html`. Show it to the user and wait for a yes
before furnishing.

## Walkability rules (they also save Unreal iterations)

- The player capsule is radius 25 cm and half-height 88 cm. Keep at least a 75 cm clear lane past furniture and
  door leaves. Doors open to 90° against a wall. If a drawn swing blocks a doorway, change the hinge side or
  remove the leaf's collision, and record the change.
- Toilets around 150 cm wide: a door opening into the room blocks the WC. Hinge it so the leaf rests on the wall.
