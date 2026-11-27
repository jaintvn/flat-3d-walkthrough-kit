# Semi-furnished Mac build

Same flat and controls as the furnished Mac game, but stripped back to the shell: no furniture, kitchen, light fittings, fans or false ceiling. Lumen still renders it, but the only light is daylight.

* **App:** `build/Mac_SemiFurnished/FlatTypeG_SemiFurnished.app` (1.0 GB); shareable zip `build/FlatTypeG_SemiFurnished_macOS.zip` (613 MB). It has its own name and bundle ID, so it sits beside the furnished `build/Mac/FlatTypeG.app` without replacing it.
* **Map:** `/Game/Flat/Maps/L_FlatTypeG_SemiFurnished`, a copy of `L_FlatTypeG` with actors removed. The furnished level is not changed.

## Removed (255 objects and 38 lights)

| Requested | What went |
|---|---|
| Furniture | L-sofa with cushions and throw, living armchair, coffee table, dining table and six chairs, bedside tables, both balconies' tub chairs and side tables |
| Plants | Every indoor and balcony plant, including the kitchen herb pot and the desk plant |
| TV + TV stand | TV, screen and floating TV unit |
| Hanging lights | Dining linear pendant with globes, both bedroom-2 bedside pendants |
| Wall lights | Living-room, bedroom-1 and wash-basin sconces |
| Ceiling | The false ceiling (perimeter bands, cove lips, bathroom drops), cove LEDs and all 27 downlights. What's left is the plain flat ceiling slab everywhere |
| Fans | All three ceiling fans |
| Kitchen | Everything: base and wall cabinets, quartz counter and backsplash, sink and tap, hob, chimney, under-cabinet LEDs, fridge, washing machine |
| Beds | Both beds (plinth, mattress, duvet, pillows, headboard panels) |
| Study tables | Both study desks, their chairs and the desk lamp |
| Wardrobes | Both wardrobes |
| Curtains | All curtains, sheers and curtain rods |

Also removed: loose decor (books, vases, the photo frame, rugs and runners, kitchen jars and the chopping board, the dining painting, the foyer artwork, towels).

**Lighting:** with every fitting gone, the flat is lit by daylight only (sun and sky through the windows and balcony doors). The only artificial light left is the corridor light outside the main entrance. Auto exposure adapts as you move, and even the toilets read clearly.

## Kept

* Bathroom fittings: WCs, basins, taps, showers, glass partitions, mirrors and towel rails. Also the foyer wash-basin vanity and its mirror.
* Wall finishes: the fluted living-room wall panel, wall mouldings (including the headboard-wall mouldings) and the bedroom-1 wall mirror.
* Switch plates, doors, windows, railings and floor finishes.
* Outdoor context, including the stylised street trees seen from the windows and balconies.

The full list is in `unreal/scripts/ue_semifurnished_report.txt`.

## How it's built

1. `unreal/scripts/ue_semifurnished.py` (run in the editor via `FLAT_RUN`) loads `L_FlatTypeG` and deletes actors whose labels match the patterns at the top of the script. It then saves the result as `L_FlatTypeG_SemiFurnished` and never saves the source map. To change what is removed, edit `REMOVE` / `REMOVE_LIGHTS` and run it again.
2. `unreal/scripts/package_mac_semifurnished.sh` switches `GameDefaultMap` to the new map for the duration of the cook and restores it on exit. It packages a Shipping build, copies it to `build/Mac_SemiFurnished/`, renames the bundle, re-signs it ad hoc and zips it.

## Checked

* The packaged app's cooked `DefaultEngine.ini` (pulled out of the .pak) has `GameDefaultMap=/Game/Flat/Maps/L_FlatTypeG_SemiFurnished`. The package was a full cook, so it holds the current map.
* `codesign --verify --deep` passes. The project's `DefaultEngine.ini` is back to the furnished map.
* In-engine views are in `previews/semi_furnished/`. The living room shows a plain ceiling with no fan, sconces or downlights. The kitchen is bare walls, with only a switch plate left. Toilet 1 shows a plain ceiling and is bright enough on daylight. The earlier pass, before the second round of removals, also showed the dining room and both bedrooms clear of furniture.
* Not checked: walking through the packaged app itself (only its config was inspected). There are no screenshots of the bedrooms after the second round, but their removals are confirmed by the actor report.
