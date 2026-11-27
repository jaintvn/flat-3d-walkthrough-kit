---
name: flat-unreal-mac
description: Bring a scripted Blender flat into Unreal Engine 5.8 (FBX + scene.json import, materials, collision, lights, Lumen, first-person player), verify walkability with automated capsule sweeps, create the Semi-furnished / Without-furniture variant levels, and package one signed macOS app per variant. Part of the flat-walkthrough pipeline. Use for the Unreal import, level building, walk-through checks, mouse sensitivity, Mac packaging, or when a Mac build of the flat crashes, looks wrong or is missing a variant or the environment.
---

# Unreal 5.8 + Mac apps

Engine `/Users/Shared/Epic Games/UE_5.8`. `UE=/Users/Shared/Epic\ Games/UE_5.8/Engine/Binaries/Mac`.
Project `unreal/<Name>/<Name>.uproject`, a content-only First Person template project (made by
flat-walkthrough's scaffold). The automation hook `Content/Python/init_unreal.py` runs `$FLAT_RUN` after the
editor loads. `FLAT_QUIT=1` quits when it's done.

## Build order (every step writes a `*_report.txt` next to its script; read it)

```
Blender -b blender/flat_<slug>.blend -P blender/scripts/export_ue.py -- unreal/import
FLAT_STAGES=assets "$UE/UnrealEditor-Cmd" <uproject> -run=pythonscript -script=<abs>/unreal/scripts/ue_build.py -unattended
FLAT_RUN=<abs>/unreal/scripts/ue_build.py FLAT_STAGES=level FLAT_QUIT=1 "$UE/UnrealEditor.app/Contents/MacOS/UnrealEditor" <uproject>
FLAT_RUN=<abs>/unreal/scripts/ue_verify.py FLAT_QUIT=1 …UnrealEditor <uproject>                 # walk checks
FLAT_MOUSE_SCALE=0.5 "$UE/UnrealEditor-Cmd" <uproject> -run=pythonscript -script=<abs>/unreal/scripts/ue_mouse_sensitivity.py
FLAT_RUN=<abs>/unreal/scripts/ue_environment.py FLAT_STAGES=assets,level FLAT_QUIT=1 …UnrealEditor <uproject>   # if environment
FLAT_VARIANT=SemiFurnished FLAT_RUN=<abs>/unreal/scripts/ue_variant.py FLAT_QUIT=1 …UnrealEditor <uproject>
FLAT_VARIANT=Unfurnished   FLAT_RUN=<abs>/unreal/scripts/ue_variant.py FLAT_QUIT=1 …UnrealEditor <uproject>
unreal/scripts/package_mac.sh                     # build/Mac/<Name>.app + build/<Name>_macOS.zip
unreal/scripts/package_mac.sh SemiFurnished       # build/Mac_SemiFurnished/<Name>_SemiFurnished.app + zip
unreal/scripts/package_mac.sh Unfurnished
```
Each cook takes about 10–20 min. Run it in the background and wait for the completion notice.

**Order is the contract:** level → environment → variants → (mobile). A variant level is a snapshot of the
furnished level at the time it was made. Re-make every variant after any change to the furnished level.

## What ue_build.py / ue_verify.py do (adapt for a new flat)

- Masters and material instances from scene.json, textures with real-world scale, one StaticMeshActor per
  instance labelled with the Blender name. Collision: walls and doors simple; furniture per-polygon; context
  none; the bedroom door leaf none when it blocks a doorway.
- Lights: Lumen GI and reflections, movable lights from Blender, sun and sky, SkyAtmosphere, volumetric clouds,
  height fog, and histogram auto exposure (4–11 EV, bias 0.6).
- Player: the First Person template character with walk speed 3 m/s, capsule radius 25 cm, arms hidden, and
  PlayerStart at `SPAWN`.
- **ue_verify.py has flat-specific data**: walking routes from the spawn through every doorway to every room,
  room rectangles for the floor-hole grid, and screenshot cameras. Rewrite them from layout.py.
  Acceptance: all routes clear and 0 floor-hole misses. The navmesh result is unreliable in automation; the
  capsule sweeps are the real test.

## Gotchas

- **Packaging:** UE 5.8's `-archive` copies an incomplete .app (no paks) that crashes at launch. package_mac.sh
  takes the complete bundle from `Saved/StagedBuilds/Mac/…`. Variants get their own CFBundleName and
  CFBundleIdentifier and an ad-hoc re-sign; the start-up map is switched only for the cook.
- The app is unsigned for distribution. First launch needs right-click → Open (say so in the README).
- Mouse look: the Scalar modifier on `IA_MouseLook` only (gamepad look is `IA_Look`). Synthetic mouse input
  doesn't reach a captured cursor, so the exact turn rate can't be measured. Say it's unverified.
- Never leave test actors in `L_<Name>`. The Plane/Cube from a Lightmass test ended up in every copy.
  ue_variant.py strips them.
- Lightmass doesn't work on Apple Silicon; don't try static lighting here (flat-android bakes in Cycles).
- Editor-only settings (Generate Lightmap UVs, viewport screenshots, Save As) need the GUI editor via FLAT_RUN,
  not the commandlet.

## Verify the packaged app

Launch each .app, screenshot the spawn and a few rooms (computer-use `app_screenshot`, or `screencapture`), and
check `codesign --verify --deep`. For a variant, confirm the cooked config has the right `GameDefaultMap`. Docs:
`docs/02_testing.md` (checks, results, issues fixed, not verified) and the README deliverables table, one row per app.
