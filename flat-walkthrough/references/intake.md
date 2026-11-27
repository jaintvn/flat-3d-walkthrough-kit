# Intake: what to collect before building

Read the plans first (Read tool on each image; zoom by cropping with Pillow if text is small). Extract
everything printed, and only ask for the rest. Record answers in `project.json → intake` and every assumption in
`intake.unknowns_assumed` (also in docs/01 with [C] confirmed / [M] measured / [E] estimate tags).

## Always needed

| Input | Where it usually is | If missing |
|---|---|---|
| Plan image(s) of the unit | user | ask; a unit plan plus the floor-plate plan is ideal (the second shows party walls, passage, which side is outside) |
| Which unit is theirs | unit label on the plate ("Type G") | ask if the plate shows several units |
| Room sizes | printed dims (e.g. 390 x 390) | measure from the drawing scale (derive cm/px from two printed dims; check they agree) |
| Wall thickness | not printed | internal 12 cm, external/party 20 cm [E]; choose so printed sizes add up exactly |
| Ceiling / door / sill heights | rarely printed | slab 285, door head 210, bedroom sill 90, kitchen sill 105, toilet vent 150 [E] |
| Compass / facing | north arrow on the plan | **ask** "Which direction do the balconies face?" (needed for sun and for the environment) |
| Floor number | brochure / user | ask if environment or view height matters; else assume mid floor |
| Variants wanted | user | offer Furnished, Semi-furnished, Without furniture (multiSelect) |
| Targets | user | Mac app, Android APK (multiSelect); ask for the phone model(s) for Android tiers |

## Style (flat-furnishing)

| Input | Ask |
|---|---|
| Builder name | "Who is the builder? I'll use their show-flat / brochure interiors as the style." Then research their site's project galleries and specifications (doc 01 §5 in the example). |
| No builder, or builder has no interiors online | ask for 2–5 reference images or a style word (warm modern, minimal, Kerala traditional, Scandinavian …) |
| What the builder hands over (for Semi-furnished) | "What comes with the flat: modular kitchen, wardrobes, false ceiling, lights, fans, bathroom fittings?" (updates variants.json) |
| Plan annotations | furniture drawn on the plan is the placement source; ask only if it conflicts with walkability |

## Environment (flat-environment), only when wanted

| Input | Ask |
|---|---|
| Latitude, longitude | "Share the location pin (Google Maps link or lat, long) of the building." Plus code or address is fine; convert and confirm. |
| Building position on the plot, which façade faces the road | ask; a site plan, brochure render or Street View screenshot settles it |
| Floor-plate plan of the whole tower | needed to model your own tower's other wings that block the view |
| Floor heights (ground/podium floors) | brochure "G + 1 + 17", parking floors; else 3.0 m typical, 3.6 m ground and podium [E] |
| Things under construction | "Show <tower> as completed or as today?" |
| Consent | "This sends the pin to Esri (imagery), OpenTopoData (elevation) and Overpass (OpenStreetMap). OK?" |

## Question wording

One `AskUserQuestion` call, at most 4 questions, each self-contained (name the plan/room you're asking about).
Put the recommended default first and mark it "(Recommended)". Example set for a first run:

1. "Which versions do you want?" (multiSelect: Furnished, Semi-furnished, Without furniture)
2. "Which apps?" (multiSelect: Mac, Android)
3. "Who is the builder, so I can match their interior style?" (options: name you read on the plan
   (Recommended) / I'll share reference images / Pick a neutral modern style)
4. "Add the real surroundings in the balcony and window views?" (Yes, I'll share the location pin / Not now)

Ask the follow-ups (pin, facing, hand-over list) only for what the answers turn on.
