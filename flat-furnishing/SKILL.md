---
name: flat-furnishing
description: Furnish and finish a flat model in Blender in a specific builder's interior style (researched from the builder's project galleries and specifications, or from user reference images), with realistic PBR materials and Poly Haven CC0 assets, and define the Furnished / Semi-furnished / Without-furniture variants. Stage 2 of the flat-walkthrough pipeline. Use when choosing interior style, writing furnish.py, swapping materials, placing furniture from plan annotations, tagging object categories, or editing variants.json.
---

# Style, furniture and variants

## 1. Style source (ask in intake if unknown)

- **Builder named:** open their website's project pages (WebFetch / web-fetch agent) and look for interior
  galleries, show-flat renders and the specification list (flooring, doors, windows, sanitaryware, kitchen).
  Record per project what you used, in `docs/01 §5`; the Type G example used Landmark Marquis, Lareina,
  Meritus and Interlerio. Specs are facts: model them as specified. Renders are style: palette, mouldings,
  ceiling bands, furniture shapes.
- **No usable builder imagery:** ask for 2–5 reference images or a style word. Never copy builder imagery into
  the build. References only.
- Fill gaps with restrained choices consistent with the references, and label them in the doc as design choices.

## 2. Furniture placement

- Furniture drawn or annotated on the plan (wardrobes, table and chair, TV and stand, fridge, washing machine)
  is the placement source. Everything else follows normal practice: bed headboard on a solid wall, TV opposite
  the sofa, dining under the pendant.
- `furnish.py` uses `Frame(bx, by, yaw)` per wall (local +y away from the wall) and the `items.py` builders
  (`Item`, `rbox`, `cushion`, `curtain`, `lathe`, `place` for Poly Haven glTF). Rewrite the per-room functions;
  keep the item builders.
- Naming is `<ROOM>_<Item>[_n]`, e.g. `LIV_Sofa_Seat_0`, `BR1_Wardrobe`, `KIT_Hob`. Names drive collision
  classes, variants and docs.
- **Category on every object** (`ob["flat_cat"] = "..."`): set it explicitly in each builder, or rely on the
  name rules in `categories.py`. Categories: arch, bath_fitting, mirror, switch, wall_finish, kitchen_fitted,
  appliance, wardrobe, false_ceiling, light_fitting, fan, loose_furniture, bed, study, tv, soft_furnishing,
  curtain, decor, plant, balcony_furniture, context. Lights belong to their fitting's category
  (a downlight's light source → light_fitting).
- Walkability: see flat-plan-to-blender. Furniture gets per-polygon collision in Unreal, so an L-shaped counter
  doesn't block the whole kitchen.

## 3. Materials

- `gen_textures.py` makes the generated sets: marble-look vitrified floor tiles with per-tile veining, quartz,
  bathroom wall tiles, and recolours of the Poly Haven scans into `textures/derived/manifest.json`.
  Change colours there for a new palette.
- The library in `blender/assets` and `blender/textures` comes from `base/polyhaven`: plastered wall, walnut,
  oak, linen, velvet, leather, granite, marble, concrete, laminate, anti-skid tiles; plants, ceiling fan,
  pendant, vases, frame, outdoor set. For a new asset, download the 2k glTF from polyhaven.com (CC0) into
  `blender/assets/<id>/` (ask before downloading) and note it in docs §7.
- Every material is PBR at real-world scale (1 UV = 1 m box mapping from `lib.MB`).

## 4. Variants (`unreal/scripts/variants.json`)

| Variant | Meaning | Default removal (categories) |
|---|---|---|
| Furnished | everything | none |
| SemiFurnished | the builder's hand-over fit-out only | loose_furniture, bed, study, tv, soft_furnishing, curtain, decor, plant, balcony_furniture, appliance |
| Unfurnished ("without furniture") | bare shell, daylight only | the above + kitchen_fitted, wardrobe, false_ceiling, light_fitting, fan |

- **Confirm SemiFurnished with the user.** Builders differ: some include a modular kitchen, wardrobes,
  false ceiling, lights and fans; some include only the kitchen platform. Edit `remove_cats` to match.
- Bathroom fittings, mirrors, switches, wall finishes, doors and windows always stay. The environment is
  never removed.
- `remove_patterns` (name regex) is the fallback for objects without a category. The Type G names are already
  listed, and the categories reproduce the shipped Unfurnished removal list exactly (checked).
- The same file drives both sides: `blender_variant.py` (a .blend for the Android bake) and `ue_variant.py`
  (the Unreal level). Unfurnished has no fittings, so it is lit by sun and sky only. Auto exposure handles it on
  Mac. On Android, exposure comes from the variant's own bake.

## 5. Checkpoint

Render every room (`render_previews.py … all 128 100`) and send `review.html`. Iterate here. Each Unreal rebuild
costs about 20 min, and an Android bake about 15 min.
