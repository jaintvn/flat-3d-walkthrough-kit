# Type G 2BHK — Plan Analysis, Assumptions and Interior Design Direction

Checkpoint v1 (initial Blender model). All dimensions are in centimetres.

## 1. The two plans

| | Your plan (`plan_my_flat.jpg`) | Builder plan (`plan_builder.webp`) |
|---|---|---|
| Content | Type G 2BHK only, 3rd–17th floor, area table, compass | Part of a typical floor: unit F (3BHK) + unit G + part of a third unit, 210-wide passage, lift and fire ducts |
| Orientation | Long axis horizontal | Unit G rotated 90° clockwise |
| Extra information | Red notes: windows, "Window & Exhaust", "unusable area" (×3), "Glass", wardrobes, table & chair, fridge, washing machine, TV and stand, entrance door | Context: which walls are shared with unit F, where the common passage runs, and that the entrance opens from the passage |

**Cross-check:** after rotation, every room, opening, door swing, duct and furniture position in unit G matches your plan. No room is mirrored or relocated. Every printed size appears on both plans with width and depth swapped by the rotation (e.g. 330×390 ↔ 390×330, 300×413 ↔ 413×300).

**Area table (your plan):** total 1280 sq ft, carpet 872, external walls 108, balconies 86, common 214. The printed balcony sizes (150×233 + 300×150 = 8.0 m²) add up to exactly the 86 sq ft stated.

## 2. Coordinate system and scale

* Origin: inner face of the left exterior wall (x = 0) and inner face of the bottom party/passage wall (y = 0). Finished floor level is z = 0.
* +X points towards the living room (plan right, roughly south-west). +Y points towards the bedroom windows and balconies (plan up, roughly south-east).
* Drawing scale, measured from wall pixels: about 1.205 cm per pixel. Every printed room dimension is reproduced exactly when internal walls are 12 cm thick:
  * along X: 390 + 12 + 330 + 12 + 150 + 12 + 300 + 383 = **1589**
  * along Y: 390 + 12 + 150 = 150 + 12 + 390 = 300 + 12 + 240 = **552**
* The overlay check (`previews/checkpoint_v1/plan_overlay_walls.jpg`) puts your plan's wall lines on top of the model's walls. They coincide within a few centimetres everywhere.

## 3. Confirmed, measured and estimated items

| Item | Value used | Basis |
|---|---|---|
| Bedroom 1 | 390 × 390, plus a 132 × 150 entry pocket under bedroom 2's wardrobe wall | [C] printed; pocket [M] |
| Bedroom 2 | 330 × 390 | [C] |
| Toilet 1 / Toilet 2 | 240 × 150 / 150 × 240 | [C] |
| Kitchen | 360 × 240 | [C] |
| Dining / Living | 300 × 413 / 383 × 300, open plan | [C] |
| Foyer | 150 wide | [C] |
| Wash-basin alcove off the foyer | ~150 × 55 | [M] (shown on both plans) |
| Balcony 1 | Printed 150 × 233; modelled to the railing line ≈ 148 × 243 | [C~] see 4.1 |
| Balcony 2 | Printed 300 × 150; modelled 311 × 147 to the railing line | [C~] see 4.1 |
| Internal walls | 12 cm | [M] (8–10 px on the drawing; makes all printed sizes add up) |
| External / party walls | 20 cm | [E] (8" block + plaster) |
| Clear height to slab | 285 cm | [E] neither plan states it |
| False ceiling | Cove band at 265 cm; toilets flat at 240 cm | [E] style from the Landmark renders |
| Door head | 210 cm | [E] |
| Bedroom doors | 90 cm clear; toilet doors 75 cm; main door 105 cm opening | [M] from the door gaps |
| Kitchen entry | ~93 cm opening, no door | [M] |
| Bedroom 1 window | ~200 wide, sill 90 | [M] width / [E] sill |
| Bedroom 2 window | ~240 wide, sill 90 | [M] width (the drawings suggest 235–270) / [E] sill |
| Living window | ~190 wide, sill 75 | [M] / [E] |
| Kitchen window | ~110 wide over the sink, sill 105 | [M] / [E] |
| Toilet ventilators | 60 × 60, sill 150, louvres plus exhaust fan | [E] position [M] ("Window & Exhaust") |
| Ducts / "unusable areas" | Toilet 1 external duct, toilet 2 shaft plus open vent cut-out, kitchen shaft | [M] |
| Balcony railings | 15 cm curb, toughened glass, steel cap at 110 cm | [E] (builder render shows glass) |
| Floor level / storey | Assumed ~10th floor (30 m) for the view outside | [E] |

## 4. Discrepancies and open questions (not silently resolved)

1. **Balcony depths.** The printed sizes (150 and 233; 150) do not fit inside the room envelope if the balcony stops at the wall's inner face. The drawings show the balcony railing on the *outer* line of the exterior wall. Modelling it there gives ≈147–148 deep, which matches the printed 150 closely. Balcony 1's length comes out ~243 against the printed 233 (+10 cm). The balcony area in the model (~8.3 m²) is within 4% of the stated 86 sq ft (8.0 m²).
2. **Bedroom 2 door vs toilet 2 door.** Both plans hinge the bedroom 2 door at the toilet end, so when fully open it lies across the toilet 2 door. The plan is kept as drawn. In the model the bedroom 2 door stands at 70°. In Unreal I plan to make doors openable (E key) so this does not block navigation.
3. **Window widths** are not printed. Values are measured from the drawn glazing and rounded. Bedroom 2's window is the least certain (235–270).
4. **Ceiling height, sill heights, false-ceiling design** are estimates. Neither plan states them.
5. **Carpet area.** Rooms built from the printed sizes give about 840 sq ft against the stated 872 (–3.7%). The note on your plan says carpet area is calculated "as per structural measurement", i.e. before plaster. That likely accounts for most of the gap.
6. **Toilet 2 vent cut-out** ("Window & Exhaust", ~80 × 83). It is drawn without an outer wall, so it is modelled as an open ventilation cut-out. If it is actually a closed duct with a louvre, that is a one-line change.

## 5. Landmark Builders references used

The official site (landmarkbuilders.in/projects) has 14 projects. The usable *apartment interior* imagery is renders only. I found no photographs of finished flats on the site.

| Page | What was used |
|---|---|
| [Landmark Marquis](https://landmarkbuilders.in/project/marquis) — interior gallery (11 renders) + specifications | **Main reference.** Warm beige walls with white picture-frame mouldings. Perimeter gypsum ceilings with warm cove LED and downlights. Light marble-look large-format vitrified tiles. Dark walnut doors with chrome levers. Sage-green high-gloss kitchen with white marble-look counter and splashback, black chimney, black fridge. Walnut dining table, curved beige upholstered chairs, brass linear/bubble pendant, gold-framed abstract painting. Beige sofa, gold round coffee table, white floating TV unit with fluted panel and brass sconces. Dark-bladed ceiling fans. Sheer plus taupe drapes. Grey upholstered bed on a walnut base, floating study desk. Wash basin on a fluted walnut base with vessel basin. Spec: vitrified tiles, wall-hung WCs with concealed cisterns, prehung veneer main door, moulded inner doors, Jindal aluminium windows with MS grills, smart door lock. |
| [Landmark Lareina](https://landmarkbuilders.in/project/landmark-lareina) — interior gallery (5 renders) | Cane/rattan and light-wood occasional furniture (used for the balcony chairs). Concealed-cistern WC spec. |
| [Landmark Meritus](https://landmarkbuilders.in/project/meritus) — interior gallery | Bedroom wood-panel and grey wardrobe combinations (bedroom 2: grey matte wardrobe with light oak). Toilet wall tiles up to the false ceiling (spec). |
| [Interiors / Interlerio](https://landmarkbuilders.in/interiors) | Brass ring lighting, sage modular kitchen, the overall warm-neutral palette. |

Where no reference covered something, I chose restrained options consistent with the above: toilet tile colours, rug patterns, plants, curtain colours, bedroom 2 accent colour (sage) and balcony floor (wood-look anti-skid tile). These are design choices, not features of a specific Landmark property.

## 6. Room-by-room design (v1)

* **Living:** beige fabric L-sofa with chaise against the kitchen wall (as drawn), cream armchair, gold round coffee table, white floating TV unit on a fluted panel, two brass sconces, cove ceiling, ceiling fan, sheer plus drapes.
* **Dining:** 6-seat walnut table, curved beige chairs, brass linear pendant. Moulded feature wall with gold abstract painting on the toilet 2 wall. Glazed 4-panel slider to balcony 2 (centre panels open).
* **Kitchen:** L-shaped sage-gloss base and wall units, white quartz counter and splashback, built-in hob plus black angled chimney, steel sink under the window, black fridge plus front-load washer against the living wall (as annotated), under-cabinet LED.
* **Foyer / wash:** runner rug, plant, moulded wall with art, fluted walnut vanity with vessel basin, oval brass mirror and sconce.
* **Bedroom 1:** king bed (grey upholstered headboard, walnut base) on the party wall, walnut side tables, brass sconces, moulded headboard wall. Walnut 2-door wardrobe plus study desk where annotated. Full-length mirror in the entry pocket. 2-panel slider to balcony 1.
* **Bedroom 2:** queen bed against the toilet wall (as drawn), oak side tables, globe pendants, grey matte wardrobe plus oak study unit along the foyer wall, sage textiles.
* **Toilets:** beige large-format wall tiles to the false ceiling, darker anti-skid floor, wall-hung WC with chrome flush plate, counter basin on a walnut ledge, mirror, glass shower partition, rain shower, towel rail, louvred vent with exhaust fan.
* **Balconies:** wood-look tiles, glass railing, cane-and-oak lounge chairs, planters.

## 7. Checkpoint v2 — realistic furniture and materials (your requested change)

Architecture is unchanged from v1. Only furniture, fittings and materials were replaced.

**Materials: all now image-based PBR (colour + normal + roughness maps) at real-world scale**
* Floors: polished Statuario-style marble-look vitrified tiles, 80 × 80 cm with 3 mm joints. Generated seamlessly by `blender/scripts/gen_textures.py`; each tile has its own veining.
* Walls and ceilings: Poly Haven *plastered_wall_04* scan, recoloured to the warm-beige paint, white ceiling and exterior paint.
* Wood: Poly Haven *smoked walnut* and *natural walnut* veneer scans (furniture and doors, dark-walnut grading) and *white oak* veneer (bedroom 2).
* Upholstery: Poly Haven *rough linen* scan recoloured into beige, cream, taupe, sage, charcoal, white and drape. *Velour velvet* for the grey master headboard and beige dining chairs. *White leather* for the balcony tub chair.
* Kitchen counter and splashback: generated white quartz with fine speckle.
* Toilets: generated 60 × 120 cm matte stone-look wall tiles. Poly Haven *granite tile* floor.
* Balconies: Poly Haven *marble_01* limestone tiles. Ducts: *concrete_floor_01*.

**Furniture rebuilt with real construction**
* L-sofa: separate crowned seat cushions, leaning back cushions, rounded arm and back rails, brass legs, throw pillows.
* Beds: channel-tufted upholstered headboards, plinth bases, mattress, duvet and throw draped over the edges, sleeping pillows plus decorative and lumbar cushions.
* Dining and desk chairs: Marquis-style curved upholstered shell backs with tapered wooden legs. Living-room and balcony seating: tub chairs.
* Also: dining table with panel legs, brass drum coffee table with quartz top, drawer side tables with brass pulls.
* Bathrooms: wall-hung WCs, vessel basins on walnut ledges, rain showers, towels.
* Kitchen: profile handles, a hob with burner caps, and an undermount sink with gooseneck tap.
* Curtains: pleated with irregular folds.

**Downloaded CC0 assets (Poly Haven, public domain):** potted plants 01, 02 and 04, ceiling fan, modern ceiling lamp (bedroom 2 pendants), ceramic vases 01 and 03, standing picture frame, outdoor table and chair set (balcony 2). They are stored in `blender/assets/`, with the textures in `blender/textures/`.

## 8. Final adjustments for walkability (Unreal stage)

* **Toilet 2 door:** hinged on the lower jamb, so the open leaf rests against the wall instead of standing across the 150 cm toilet. The plans don't make the swing side certain.
* **Bedroom 2 door:** fully open against the toilet wall, as drawn. Its leaf has no collision, so the toilet 2 doorway stays usable.
* **Toilet doors:** open to 90°.
* **Desk chairs:** tucked under both desks.
* **Living armchair:** moved 18 cm, leaving an ~85 cm lane past the TV unit.
* **Balcony 2:** the bistro set (too deep for the 1.47 m balcony) was replaced by two tub chairs and a side table at the kitchen end.
* **Balcony 1:** side table moved.
