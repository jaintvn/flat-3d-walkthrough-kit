---
name: flat-android
description: Make the Android (APK) version of a flat walkthrough from its Unreal Mac level. Lighting is baked in Blender Cycles into per-object lightmaps (Lightmass doesn't run on Apple Silicon), and the flow builds a mobile level with baked materials, the Mac sky as a panorama, per-room exposure and specular-only lights, packages one APK per variant (Furnished / SemiFurnished / Unfurnished) with touch controls at 30 fps, then installs and verifies it on a USB-connected phone with adb. Part of the flat-walkthrough pipeline. Use for Android builds, phone glitches (black patches, blocky walls, dull lighting), quality tiers, or testing on a Galaxy or other device.
---

# Android: baked lighting + APK per variant

Prereqs: the Mac level for the variant is current (flat-unreal-mac). Android Studio (SDK, NDK 28, JBR) and UE's
Android platform must be installed. The keystore was created by scaffold; its password lives in
`Config/DefaultEngine.ini`, never in chat.

## Per variant (furnished: no FLAT_VARIANT; else SemiFurnished / Unfurnished)

```
# 0. variant .blend (skip for furnished)
Blender -b blender/flat_<slug>.blend -P blender/scripts/blender_variant.py -- Unfurnished unreal/scripts/variants.json blender/flat_<slug>_unfurnished.blend
# 1. bake (~15 min, background): LightmapUV + Cycles diffuse direct+indirect per object, 256 samples, 112 texels/m
Blender -b blender/flat_<slug>[_variant].blend -P blender/scripts/bake_lightmaps.py -- unreal/import[_variant] 256 112
# 2. denoise (OIDN) + encode sRGB of L/4
Blender -b --factory-startup -P blender/scripts/denoise_lightmaps.py -- unreal/import[_variant]
# 3. mobile level (~16 min): [mesh re-import], Mac sky capture -> panorama, lightmaps, baked materials, meshfix, copy, level, shots
[FLAT_VARIANT=Unfurnished] unreal/scripts/mobile_level.sh
# 4. APK (~13 min cold, ~2 min warm)
unreal/scripts/package_android.sh [Unfurnished]       # build/Android/<Name>[_Variant].apk, package <id>[.<variant>]
```
Variants reuse the furnished meshes (same LightmapUV unwrap, which is deterministic), with their own lightmaps
(`/Game/Flat/Lightmaps_<Variant>`), per-actor materials and `L_<Name>_<Variant>_Mobile`. The mobile copy and
the APK cook leave out the Nanite environment.

## The look (how the Mac build is matched; settings at the top of ue_mobile.py)

- Every baked surface uses a baked master material: emissive = albedo × lightmap, plus reflections from per-room
  reflection captures (`ROOMS`, which is flat-specific).
- Downlights and pendants stay as **movable specular-only lights** (diffuse scale 0) for highlights on marble,
  quartz and lacquer. Metals keep 30% of the baked light. MinRoughness is 0.25.
- Bake balance: window glass is light-transparent during the bake, sun ×3, sky ×2, sheer curtains pass 75%.
  The interior tint is 1.13/0.98/0.84, contrast 1.3, saturation 1.08, bloom 0.3.
- Fixed exposure plus **per-room exposure volumes** (`ROOM_EV`: small rooms +0.8 to +1.1 EV, flat-specific)
  stand in for Lumen's eye adaptation. Mobile auto exposure locks onto the windows and blacks out the rooms.
- Sky: six HDR captures from the Lumen level, stitched by `sky_panorama.py` onto an unlit dome (NoCollision!).
- Renderer: mobile **deferred** shading (per-pixel reflection captures), TAA, 8× aniso on top tiers.
  `t.MaxFPS=30`. Tiers Epic/High/Mid/Low use resolution scale 2.0/1.5/1.0/0.75.
  Package: arm64, Vulkan + ES3.1, ASTC, data inside the APK, sensor landscape, min SDK 26, target 36.
- Touch: the template's `UI_TouchSimple` (left stick walks, right stick looks, jump button). Gamepads work too.

## Bugs already solved (check these first when something looks wrong)

| Symptom | Cause | Fix in kit |
|---|---|---|
| Black jagged patches on floors | a stray engine Plane from a Lightmass test z-fighting with the floor | `strip_test_shapes` on copy; list actors over the area to find others |
| Interior walls black | Cycles baked into the active (material) UV | LightmapUV set active |
| Scrambled lighting | UE "Generate Lightmap UVs" overwrote the Blender UVs | `meshfix` stage (GUI) |
| Plants/fans empty | Cycles skips linked duplicates | single-user mesh per instance |
| Blocky walls on phone | ASTC on RGBM alpha | sRGB L/4, highest ASTC quality |
| Reflection jumps between rooms | forward renderer: one capture per mesh | mobile deferred |
| Grain while moving | specular aliasing | TAA + aniso |
| Blue haze | physical height fog with fixed exposure | fog removed/thinned |
| Camera under floor | sky dome collision | NoCollision |
| UBT "name exceeds maximum" | long project path → mutex name | build via `~/Library/Caches/<Name>Build` symlink |
| Compile "not active" | UBA can't run the Intel NDK under Rosetta | `-ubtargs=-NoUBA` |

Diagnosis tools: preview on Mac with the mobile renderer:
`UnrealEditor <uproject> /Game/Flat/Maps/L_<Name>_Mobile -game -featureleveles31 -windowed -ResX=1280 -ResY=720 -ExecCmds="BugItGo x y z p y r"`.
You can also project a lightmap top-down through the UE UV1 to separate content errors from rendering errors.

## Phone test (only with the user's phone connected and USB debugging on)

`ADB=~/Library/Android/sdk/platform-tools/adb`; `$ADB devices` (set `ANDROID_SERIAL`).
`$ADB install -r build/Android/<apk>`;
`$ADB shell am start -n <package>/com.epicgames.unreal.SplashActivity`;
walk with `$ADB shell input swipe 250 900 250 700 2600` (left stick);
`$ADB exec-out screencap -p > previews/android/<device>/NN_name.png`; memory with `dumpsys meminfo <package>`;
frame times with `dumpsys gfxinfo <package> framestats`.
Look at the screenshots yourself before reporting. Sustained fps/thermal runs take 10+ min: offer them,
don't run unasked. Write it all up in `docs/03_android.md`, including what is unverified (e.g. tiers on
devices you didn't have).
