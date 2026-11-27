# Balcony view and surrounding environment: research summary (before any modelling)

Status: research (sections A–E) **answered and confirmed** by you on 2026-11-06; reconstruction **version 1 built** (section F).

Tags: **[V]** verified from a map, imagery or an official/primary source · **[L]** from a property listing (unverified) · **[E]** my estimate, with the reasoning given · **[?]** open question.

Supporting data is in `reference/environment/`:

* `satellite_250m_site.png`: 0.3 m/px imagery around the pin. Rings are at 100 m and 250 m. The red ray is the balcony direction (130°); the yellow rays are ±45°.
* `satellite_3km_view_wedge.png`: 2.3 m/px imagery with rings at 0.1/0.25/0.5/1/1.5/2/3 km. Blue dots mark the identified buildings.
* `osm.json` (OpenStreetMap, ODbL), `elev.json` and `profile.json` (SRTM elevations), `landmarks.json` (distances and bearings below), `compass_crop.png`.

Imagery: Esri World Imagery (Maxar/Earthstar). It is used as a local reference only and is not redistributed.

---

## A. Location analysis

| Item | Finding | Tag |
|---|---|---|
| Pin | 11.251028 N, 75.818917 E (plus code 7R29+CH7, Kozhikode) | [V] |
| Locality | Methottuthazham / Kommeri, about 0.7 km south-west of the NH66 Kozhikode bypass | [V] OSM, Google Maps |
| Landmark Blueberry | 11.251508 N, 75.818687 E: **59 m NNW of the pin**. Single tower, 72 units, completed Oct 2023 (K-RERA/PRJ/KKD/081/2021). Listings say "10 floors", but the satellite shadow suggests it is taller. | position [V], floors [L] |
| The pin itself | Sits on the lane that runs NNW–SSE past Blueberry. Street View (Feb 2026) at 11.250875, 75.818796 shows a coconut grove **east/north-east of the lane** with a dirt access track, a lorry and a JCB, i.e. an unbuilt plot. A two-storey concrete frame is under construction behind a wall **west/south-west of the lane**. | [V] Street View |
| Lane direction at the site | about 130–150° (SE) heading south | [V] imagery |
| **Plan compass** | The north needle points **40° anticlockwise from page-up** on the 14th–17th floor plan. Your own Type G plan has the same compass rotated 90° with the unit, which is consistent. | [V] measured, ±3° |
| Building grid | Page-up = bearing 40° (NE), page-right = **130° (SE)**, page-down = 220° (SW), page-left = 310° (NW) | derived |
| **Type G position** | The upper-right wing of the floor plan, i.e. the **north-east end** of the tower, next to unit F | [V] plan |
| **Both G balconies** | Balcony 1 (bedroom 1, 233×150) and balcony 2 (dining, 150×300) open to page-right → **face 130° (SE)** | [V] plan + compass |
| Other G openings | Bedroom 1 end window faces **40° (NE)**, towards HiLITE Metromax. Kitchen/living windows face 220° (SW) towards the tower's own core. | [V] plan |
| Building front | You said the front faces the road. The plan's page-down side (units C and B, with curved corners) matches the render's façade: curved balcony stacks either side of the tall central panel. That side faces **220° (SW)**, i.e. towards the lane at the pin. Type G is then at the back (NE) of the tower, and its balconies look **along** the lane direction over the neighbouring groves, not at the road. | [E] **needs your confirmation** |
| Terrain | Undulating laterite upland. SRTM gives 15–30 m at the site and 5–47 m within 3 km. A wooded hill about 1.0 km SSE (the Zamorin's Guruvayurappan College hill) reaches about 70 m. Low wetland/paddy lies about 0.9 km SW. The Kallai/Mampuzha valley is 3 km S. SRTM is a surface model, so these heights include roughly 5–10 m of tree canopy. | [V] SRTM 30/90 m, ±5 m |
| Vegetation | A dense coconut-palm canopy dominates every direction, with broadleaf trees mixed in (tall-trunked trees in Street View; mango/jackfruit/anjili typical of Kozhikode house compounds), banana and shrubs. Red laterite soil shows in cleared plots. | [V] imagery + Street View; species mix [E] |

## B. Nearby building inventory (distances from the estimated Type G balcony)

Type G is placed about 45 m north-east of the pin, at the back of the tower ([E], see questions). Relative angle: 0° = straight out of the balcony (130°); negative = left, positive = right.

| Building | Distance | Bearing (rel.) | Floors | Est. height | Style / notes | Balcony visibility |
|---|---|---|---|---|---|---|
| **Own tower, A wing** | 5–25 m | +18° to +90° | same as yours | — | Same façade: white, curved balconies | **Blocks the right side of the view** from your floor upward (balcony 2: everything beyond about 18° right; balcony 1: beyond about 48° right) [E] from plan geometry |
| Castle Apartment | 331 m | 119° (−10°) | not found | [E] 4–6 fl, 13–20 m | Low-rise apartment block | In view, slightly left of centre, below eye level |
| Vinod Villa Serviced Apts | ~500 m | 118° (−11°) | not found | [E] 2–4 fl | Low-rise | In view, mostly behind canopy |
| Sastha Homes | 979 m | 127° (−2°) | not found | [E] low-rise | Serviced apartment | Dead centre, probably just a roofline in the trees |
| **HiLITE Olympus 1** | ~1.75 km | ~115° (−14°) | 33 floors [V Wikipedia]; brochure 6B+G+24+service+recreation | **122 m** [V] | Contemporary high-rise, glass/white | **Dominant skyline element**, about +3° above your eye line |
| HiLITE Olympus 2 | ~1.8 km | ~115–120° | 32 floors (3B+G+26+2) [V developer] | [E] ~110 m | Under construction (2025) | In view if built by the time you move in. Need to decide how to show it. |
| **HiLITE Corinth** | 1.66 km | 107° (−22°) | not found | [E] 15–20 fl | High-rise apartments | In view, left of Olympus |
| Anvi's Apartments | ~1.56 km | ~102° (−27°) | not found | [E] mid-rise | Near HiLITE City | In view, far left |
| HiLITE City campus | 1.5–2.2 km | 100–125° | — | — | Large construction site with several towers (WTC development announced 2025) | Skyline cluster, left of centre |
| Confident Phoenix | ~310 m | 179° (+49°) | S+18 [L] | [E] ~58 m | Single tower | **Hidden by your own A wing** at balcony 2 |
| HiLITE Metromax | 410 m | 39° (−90°) | not found | [E] high-rise (shadow) | Twin towers next to NH66 | Not visible from the balconies. **Fills the bedroom 1 end window.** |
| Landmark Blueberry | 57 m | 288° | 10 [L] | [E] 30–40 m | — | Behind you; not visible from G |
| Houses (hundreds) | 30 m – 3 km | all | 1–3 | 4–11 m | Kerala RCC houses: flat concrete roofs with parapets and water tanks, some red-tile sloping roofs, pastel/white paint | Everywhere below the horizon, seen through the canopy |

Floor counts or heights marked [E] could not be confirmed online. They will be estimated from Street View, from roof shadows measured against Olympus 1's known 122 m, or from photos you can provide.

## C. Balcony visibility analysis (11th floor, facing SE)

Eye height: Type G's typical floor runs from the 3rd floor upwards. Floor-to-floor is assumed at 3.0 m (285 cm clear, as already in the model, plus a 15 cm slab). That puts the **11th-floor finished floor about 33 m above ground ([E], range 33–36 m depending on the ground/parking floors)**, with eyes about 34.6 m up. The existing scene places the ground at −30 m, so it would move down by about 3 m.

From that height:
* Everything within about 300 m is looked **down** on (houses 100 m away sit about 18° below the eye line), so the near field reads as roofs and palm crowns, not façades.
* **Left (−45° to −15°):** the HiLITE City cluster (Corinth, Anvi's, Olympus 1 and 2) at 1.5–2 km. The NH66 corridor shows only as gaps in the canopy at the far left. On very clear days (post-monsoon), the Wayanad ghats appear as a faint ridge about 1.2° above the horizon at the far left edge (75–90°, 70–80 km).
* **Centre (−15° to +15°):** an unbroken coconut canopy with house roofs. Castle Apartment and Vinod Villa sit at 300–500 m, slightly left. Beyond that is low undulating terrain; the horizon is flat (within ±0.3°) all the way out.
* **Right (+15° to +45°):** your own tower's A wing, with its balconies, windows and the curved-corner slab edges, a few metres away. From balcony 1 (bedroom 1) the A wing starts further right, and the wooded college hill shows at about +36° before the wing cuts it off.
* **Below:** your own plot's boundary wall and landscaping, the neighbouring grove, and the lane further right.

## D. Environment reconstruction plan

| Tier | Range | What | How |
|---|---|---|---|
| 0 | 0–60 m | Own tower (A wing, F wing, slab edges, curved balconies), own plot (boundary wall, driveway, landscaping) | Modelled from the floor plan plus the render. The parts visible from G only (façade above and below the 11th floor). |
| 1 | 60–400 m | Individual houses and the nearest apartments (Castle). Every coconut palm and broadleaf tree in view. | Footprints traced from 0.3 m imagery; heights from shadows and Street View. Roofs, parapets, water tanks, rough façade colours. Trees placed one by one from crowns visible in the imagery. |
| 2 | 0.4–2.5 km | HiLITE City towers, mid-rises, house roofs | Massing with correct height and silhouette, and window-band textures. Houses as instanced roof boxes on the terrain. Canopy as instanced palm/broadleaf cards following the imagery's green mask. |
| 3 | 2.5–80 km | Terrain and horizon, the ghats ridge | SRTM heightfield mesh with an aerial-perspective fade. The distant ridge as a low silhouette. |

Trees: coconut palms are the critical asset (curved 15–25 m trunks, 6–8 m pinnate crowns). I'd build them procedurally in Blender (geometry nodes: trunk curve and frond cards), with 4–6 variants plus broadleaf (mango/jackfruit type) and banana/areca variants. Alternatives are a Fab/Megascans tropical pack if you have one, or CC0 assets; Poly Haven has few tropical trees.

## E. Unreal Engine implementation (compatible with the current pipeline)

Existing scene, inspected:
* Blender units are cm, origin at the inner face of the flat's left and bottom walls, finished floor z = 0. Plan +Y = bearing **130°** (balconies), plan +X = bearing **220°**. Unreal uses (x, −y).
* Context today is placeholder only: `CTX_Ground` at −30 m, 26 random boxes (`CTX_Buildings`), 140 sphere "trees" (`CTX_Trees`) and a façade stub (`CTX_Facade`), all in collection `05_Context` (`blender/scripts/build_flat.py: build_context`).
* Sun: azimuth **110°**, elevation **35°** (`LGT_Sun`). For Kozhikode that is **about 09:00 IST in mid-October or late February**: morning light from slightly left of the balcony direction. **I will keep this** (no time change). The exterior is therefore lit from the front-left and slightly back-lit.
* Mac level: SkyAtmosphere, real-time SkyLight, ExponentialHeightFog (density 0.004), VolumetricCloud, Lumen, histogram auto-exposure (min 4 / max 11 EV, bias 0.6). Android level: baked lightmaps and a sky panorama captured from the Mac sky.

Plan:
1. **Geo-reference:** a single transform from (lat, lon, SRTM height) to plan cm, anchored at the G balcony, with plan +Y = 130°. The interior is not touched.
2. **Replace only `05_Context`** (the placeholder ground, boxes and sphere trees) with a new `06_Environment` set: terrain mesh, buildings by tier, trees, own-tower wings. Interior geometry, materials, lights and cameras stay as they are.
3. **Mac (Lumen):** Nanite for the terrain, tier 0–1 buildings and the trees (Nanite foliage in 5.8). Instanced static meshes and HLOD for tier 2. Fog retuned only as far as distance haze needs (Kerala morning: roughly 8–15 km visibility), not heavier.
4. **Android:** render the finished environment into the sky panorama the mobile level already uses (the same capture path as now, plus a near-field cards layer). The phone keeps 30 fps without adding geometry.
5. **Verification:** a top-down overlay of the model on the satellite image, and a balcony render compared with Street View views and the HiLITE skyline angles in this document.

## Your answers (2026-11-06)

1. The tower goes on the coconut-grove plot by the lane at the pin (your Street View screenshot looks north into it, with Landmark Blueberry on the left).
2. The 11th floor has the same layout as floors 14–17. Later corrected: the 4th–13th floor plan (units A–G) is the one that applies.
3. Ground floor: parking. 1st floor: gym, lobby, parking, kids' play area. Flats from the 2nd floor up.
4. Show HiLITE Olympus 2 and HiLITE City as completed.

## F. Reconstruction, version 1

### Placement and heights

| Item | Value | Tag |
|---|---|---|
| Plan scale (14th–17th floor plan) | 3.41 cm/px (G interior 552 cm = 162 px) | [V] measured |
| Tower footprint | 35.1 × 41.4 m, grid rotated so plan-up = 40° (from the compass) | [V] plan |
| Footprint position | Centre 10 m NE of the pin; front (C/B side) faces the lane, about 8 m setback | [E] (no site plan) |
| Type G flat origin | 16.4 m E, 24.9 m N of the pin | derived |
| Floor heights | Plinth 0.6 + ground 3.6 + 1st 3.6, then 3.0 m per floor (16 typical floors, 2nd–17th) | [E] |
| **11th-floor level** | **34.8 m** above the plot; eye height 36.4 m | [E] ±1.5 m |
| Plot ground | 17.6 m above sea level (SRTM, canopy-corrected) | [E] ±4 m |

### What was built (`blender/environment.blend`, collection `06_Environment`)

| Layer | Content | Source |
|---|---|---|
| Terrain | 10 m mesh to ±1 km and 90 m mesh to ±3.6 km, plus a horizon apron to 25 km. Coloured by land cover (shaded litter under canopy, laterite where bare). | SRTM 30 m, smoothed, minus a canopy allowance; land cover from imagery |
| Houses | 15,959 buildings: 10,040 flat concrete roofs (parapet, black water tank, stair cabins, some GI truss roofs), 5,747 hip tile roofs, 172 sheet roofs. Pastel walls. Windows and sunshades within 450 m. | Footprint, orientation and roof type detected from satellite imagery; floors estimated from footprint area (1–6) |
| High-rises | 16 buildings from `env_data/towers.json`, including Olympus 1 (122 m), Olympus 2 (shown complete), Corinth, Confident Phoenix, Metromax, Blueberry and the HiLITE Mall. **WTC Kozhikode is assumed massing** (two 150 m towers): no published design exists. | Mixed V/L/E per tower, recorded in the file |
| Own tower | Traced outline of the **4th–13th typical floor plan** (`reference/plan_typical_04_13.jpg`, units A–G). Every storey is extruded from it: white walls, a mitred slab band, punched windows with sunshades, balcony bays with glass balustrades, podium and stone plinth. On floor 11 the outline excludes Type G and the common passage (the interior model contains them); on other floors G is a closed volume with the flat's balconies and windows. Landscaped plot with a stone boundary wall. | Plan geometry ([V], traced at 3.61 cm/px); façade detail [E] from the render |
| Streets | OSM roads (tarred or laterite), compound walls along lanes within 450 m, concrete poles every 35 m with 1,312 wire spans | OpenStreetMap + [E] |
| Vegetation | 186,630 instances: coconut palms (5 variants), broadleaf mango/jackfruit/anjili type (4), areca (2), banana, plus undergrowth. Full-detail models within 380 m, lighter versions beyond. | Tree positions from crown detection in the imagery; species mix [E] (~56% palm near, 62% far) |

Nothing in the interior changed. Renders hide only the four placeholder objects (`CTX_Ground`, `CTX_Buildings`, `CTX_Trees`, `CTX_Facade`), which this environment replaces. Lighting is unchanged: sun azimuth 110°, elevation 35°, about 09:00 IST in mid-October. Haze is added as aerial perspective (visibility about 10 km) on geometry only, never on the sky.

### Rebuild

```
python blender/scripts/env_extract.py <geo dir> blender/env_data                       # imagery/SRTM/OSM -> placement data
Blender -b --factory-startup -P blender/scripts/env_build.py -- <FlatTypeG>              # -> blender/environment.blend
Blender -b blender/flat_typeG.blend -P blender/scripts/env_render.py -- previews/environment all 128 1600
Blender -b blender/environment.blend -P blender/scripts/env_export.py -- unreal/import_env
FLAT_RUN=<abs>/unreal/scripts/ue_environment.py FLAT_STAGES=assets,level FLAT_QUIT=1 UnrealEditor FlatTypeG.uproject
```
`<geo dir>` holds the downloaded imagery tiles (Esri World Imagery, used for locating only, not redistributed), the SRTM grids and `osm.json`.

### Unreal (Mac level `L_FlatTypeG`)

* `unreal/scripts/ue_environment.py` imports the 124 meshes into `/Game/Flat/Environment` with Nanite on. Tree assets use Nanite *Preserve Area* shape preservation; without it the leaflets were simplified away and the trees showed as bare trunks.
* It creates two-sided materials (foliage uses the two-sided-foliage shading model, with per-instance colour variation) and places the vegetation as 24 instanced (HISM) components with 186,630 instances.
* It removes the 4 placeholder actors and saves the level. A backup of the level before this change is in `unreal/backup/`.
* **One change outside the environment:** the height fog. It was tuned for the old flat placeholder ground (density 0.004 at −30 m) and turned the real kilometres of terrain white. It now sits on the plot ground (−34.8 m) with density 0.0006 and height falloff 0.05. Sun, sky light, sky atmosphere, clouds, exposure and all interior lights are unchanged.
* Order matters: `ue_build.py`'s level stage rebuilds the level from the interior export, which still contains the placeholders. Run `ue_environment.py` (stage `level`) again after it.
* Views were checked in the editor viewport with Lumen (`previews/environment/unreal_*.jpg`). The Mac game was repackaged with the environment (`build/Mac/FlatTypeG.app`, 1.1 GB).

### Previews

`previews/environment/`:
* Blender Cycles: `bal2_from_dining`, `bal2_rail`, `bal2_rail_left`, `bal2_rail_right`, `bal2_down`, `bal1_rail`, `bed1_window`.
* Unreal Lumen: `unreal_bal2_rail` (after the correction).

### Correction 1 (A wing too close)

Version 1 assembled the rest of the tower from rectangles placed by eye. One of them, a "core" block, filled the open courtyard between Type G's kitchen end and the A wing and the stair core. That put a wall about 5 m from balcony 2. The tower is now traced from the 4th–13th floor plan (`blender/scripts/env_floorplate.py` → `env_data/own_floorplate.json`). The courtyard is open.

Measured from balcony 2's railing line, the A wing's nearest corner is about 3 m ahead and 7 m to the right. Its long north-east face runs 4.6 m to the right of the balcony's edge, from 6 m to 15 m ahead. Looking straight out (130°), it only fills the right edge of the view.

### Known limitations of version 1

* House floor counts and wall colours are estimated, not observed. Only the nearest buildings could be checked against Street View.
* Tree species are assigned by proportion, not identified per tree.
* The tower's position on the plot is estimated within about ±10 m. A site plan would fix it.
* The Android build is unchanged. Bringing the environment to the phone means baking it into the mobile sky panorama. Also, `mobile_level.sh` copies the Mac level, so it must leave out the `06_Environment` actors before it is run again.
