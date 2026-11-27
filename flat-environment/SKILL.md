---
name: flat-environment
description: Reconstruct the real surroundings of an apartment from its latitude/longitude so the balcony and window views in the Blender renders and the Unreal Mac walkthrough are accurate. It covers research (orientation from the plan compass, nearby towers and landmarks with distances and bearings, eye height) and the build: SRTM terrain, houses detected from satellite imagery, known high-rises, OSM roads, procedural trees and the user's own tower from the floor-plate plan, with Nanite in Unreal. Part of the flat-walkthrough pipeline. Use when the user wants the view outside, the surrounding environment, the balcony view, or gives a location pin for their flat.
---

# Geo-referenced environment

Research first, build second. Write `docs/05_balcony_environment_research.md` with sections A–E (location,
building inventory, visibility, reconstruction plan, Unreal plan). Ask the user to confirm the open questions
**before** modelling (example: `example_typeG/05_balcony_environment_research.md`). Tag facts
[V] verified / [L] listing / [E] estimate / [?] open.

## Inputs (from intake; ask for what's missing)

Pin lat/lon. The plan compass, giving the bearing of the flat's +Y. Floor number and the podium/ground floor heights.
The whole floor-plate plan, for your own tower's other wings. The tower's position on the plot and which façade
faces the road. Whether to show buildings under construction as complete. **Consent to send the pin to the
data services.**

## Research (A–C)

- Bearings: measure the plan's north arrow against page-up (±3°), then derive the bearing of each
  façade/balcony. Example: north is 40° anticlockwise from page-up, so page-right = 130° (SE).
- Nearby buildings: OSM, the builder's other projects, listings, Wikipedia for tall towers. Give each a
  distance, a bearing relative to the balcony, floors and height. When heights aren't published, estimate them from shadow
  length against a building of known height.
- Eye height = plinth + ground + podium + (n − podium) × typical floor + 1.6 m. List what blocks the view:
  usually your own tower's other wings.

## Build

```
python3 ~/.claude/skills/flat-walkthrough/scripts/geo_fetch.py --lat <lat> --lon <lon> --out <geo dir> --dry-run   # counts
python3 ~/.claude/skills/flat-walkthrough/scripts/geo_fetch.py --lat <lat> --lon <lon> --out <geo dir>             # ~5 min
python3 blender/scripts/env_floorplate.py reference/<floor plate>.jpg blender/env_data/own_floorplate.json previews/environment/floorplate_debug.png
python3 blender/scripts/env_extract.py <geo dir> blender/env_data
Blender -b --factory-startup -P blender/scripts/env_build.py -- <project root>          # -> blender/environment.blend
Blender -b blender/flat_<slug>.blend -P blender/scripts/env_render.py -- previews/environment all 128 1600
Blender -b blender/environment.blend -P blender/scripts/env_export.py -- unreal/import_env
FLAT_RUN=<abs>/unreal/scripts/ue_environment.py FLAT_STAGES=assets,level FLAT_QUIT=1 UnrealEditor <uproject>
```
Keep the geo dir outside the project or git-ignored: the imagery is for local reference only and is never shipped
or committed.

### Per-site values to set

- `site.json → env_build`: `ffl_m` (the flat's finished floor above the plot ground), `plan_m_per_px`,
  `bearing_plus_y`, `plan_centre_px`, `shift_m`, `flat_origin_px`. env_build.py reads these; the example
  values are the fallback, so a missing site.json silently builds Kozhikode. Check the printed metadata.
- `env_floorplate.py`: plan registration (the flat's two inner wall faces in pixels, and the scale) in its header.
- `blender/env_data/towers.json`: one entry per known tall building (E/N metres from the pin, footprint, angle,
  height, style, source). Mark assumed massing "ASSUMED" in `src`.
- `env_render.py` cameras: one per balcony railing and per main window, in flat-frame metres.
- Regional look: `env_trees.py` builds Kerala vegetation (coconut, areca, banana, mango/jackfruit-type
  broadleaf) and env_build.py builds Kerala RCC houses (flat roofs with parapet and water tank, tile hip roofs).
  For another region, change the species mix and house styles, and say so in the doc.

## Unreal (Mac level only)

- ue_environment.py imports about 124 meshes into `/Game/Flat/Environment` with Nanite. Trees use Nanite
  **Preserve Area**; without it, leaflets vanish and trees show as bare trunks. It places vegetation as HISM
  (about 190k instances) and removes the 4 `CTX_*` placeholders.
- Height fog must move to the real plot ground (`-ffl_m`) and get much thinner (density about 0.0006, falloff
  0.05). Otherwise kilometres of terrain go white.
- Re-run it after any `ue_build.py` level stage, then re-make the variant levels so they include the view
  (flat-unreal-mac).
- Android: the environment is left out of the mobile copy and the APK cook (too heavy). The phone shows the
  Mac sky panorama only. Baking the environment into that panorama, plus a near-field card layer, is designed
  (doc 05 §E.4) but **not implemented**. Tell the user if they expect the view on Android.

## Verify

Overlay the model top-down on the satellite image, compare the balcony renders with Street View, and check
skyline angles against the bearings in the doc. List the known limitations (estimated house heights, species by
proportion, ±10 m tower placement without a site plan).
