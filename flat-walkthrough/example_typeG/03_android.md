# Android build: approach, status and how to rebuild

## Goal

Build a playable APK for the Galaxy S24 Ultra (Snapdragon 8 Gen 3, Adreno 750) and Galaxy S25 (Snapdragon 8 Elite, Adreno 830), and for any other capable Android device. The lighting should match the Mac version while staying cheap enough for phones.

## How the lighting is carried over

The Mac build uses Lumen (real-time GI) with 40 movable lights. Neither runs on phones. The Android build therefore uses **baked lighting**: the full light transport (sun, sky, downlights, coves, all bounces) is computed offline once and stored in a lightmap per object.

* **Unreal's Lightmass doesn't run on this Mac.** UE 5.8's installed build ships Lightmass as an Intel binary under Rosetta. Even a one-cube test scene fails after about 4 s. The editor and Lightmass connect, but the job never completes.
* **The bake is done in Blender Cycles instead.** Cycles is the path tracer behind the approved previews, so the mobile lighting comes from the same light setup:
  1. `blender/scripts/bake_lightmaps.py` gives each mesh a second UV set (*LightmapUV*: unique, non-overlapping islands) and re-exports the FBX. It then bakes DIFFUSE direct + indirect lighting for all 341 objects at 80 texels/m (64–2048 px, 31 MP in total) and 256 samples. Plants and ceiling fans use their own Poly Haven UVs, because thousands of leaf islands would fall below a texel.
  2. `blender/scripts/denoise_lightmaps.py` denoises each lightmap with Intel OIDN (via the compositor). It then encodes them as sRGB colour of *lighting ÷ 4* (no alpha), compressed at the highest ASTC quality.
     RGBM (HDR in the alpha channel) was tried first. Phone ASTC compression turned it into visible blocks on smooth walls (`previews/android/v1_rgbm_block_artifacts.png`).
* **In Unreal**, `L_FlatTypeG_Mobile` is a copy of the Mac level, built by `unreal/scripts/ue_mobile.py` and `unreal/scripts/mobile_level.sh`:
  * Every baked surface uses a *baked* master material: `emissive = albedo × lightmap`, plus specular reflections from 12 per-room reflection captures (marble, quartz and glass still reflect).
  * There are **no runtime lights**, which is about as cheap as mobile shading gets.
  * The sky is an unlit gradient dome, because SkyAtmosphere needs a special sky mesh on mobile.
  * Glass and LED strips keep their normal materials.
  * Exposure is fixed at 1.2 EV, about the per-room average of the Lumen build. Auto exposure on the mobile renderer locks onto the bright windows and blacks out the rooms.

Previews:
* `previews/mobile_editor/` has editor captures from the same viewpoints as `previews/unreal_editor/` (Lumen).
* `previews/mobile_preview/` has screenshots of the level running on the **mobile renderer** (`-featureleveles31`, i.e. OpenGL ES 3.1 shading on Metal).
* `previews/android/` has screenshots of the **packaged APK** running in the Android emulator.

## Bugs found and fixed on the way

| Symptom | Cause | Fix |
|---|---|---|
| Interior walls black | Cycles bakes into the **active** UV map, which was still the material UVs (box-mapped, in metres) | LightmapUV made active for the bake |
| Lighting scrambled in Unreal | Unreal's "Generate Lightmap UVs" overwrote the Blender lightmap UVs; the setting can only be changed in the full editor | `meshfix` stage run in the GUI editor; it verifies that 0 meshes still generate UVs |
| Plants, vases and fans empty | Cycles skips linked duplicates (shared mesh data) | each instance gets its own mesh copy |
| Checkerboard materials | lightmap sampler's default texture used the wrong compression type, so the material failed to compile | a real lightmap is used as the default |
| Blue haze | exponential height fog is physically scaled; with fixed exposure it dominates | fog removed in the mobile level |
| Camera under the floor | the 150 m sky-dome sphere had collision around the PlayerStart | NoCollision profile |
| Blocky walls on Android | ASTC compression of RGBM lightmaps | plain sRGB lightmaps (range ×4), highest compression quality |
| UBT crash: "length of the name exceeds the maximum limit" | Unreal Build Tool makes a named mutex from the project path, and this workspace path is too long | packaging goes through the short symlink `~/Library/Caches/FlatTypeGBuild` |
| Compile processes "not active" | Unreal's build accelerator (UBA) can't run the Intel NDK compilers under Rosetta | `-ubtargs=-NoUBA` |

## Device settings

`Config/DefaultEngine.ini` and `Config/DefaultDeviceProfiles.ini`:

* **CPU and graphics:** arm64; Vulkan, with OpenGL ES 3.1 as fallback.
* **Textures:** ASTC.
* **Android versions:** minimum SDK 26 (Android 8), target SDK 36.
* **Screen:** sensor landscape, full screen, display cutout used.
* **Shading, anti-aliasing and HDR:** mobile deferred shading, temporal AA, Mobile HDR.
* **Package:** data packaged inside the APK.
* **Package name:** `com.flatwalkthrough.typeg`.
* **Signing:** own key at `unreal/FlatTypeG/Build/Android/flattypeg.keystore` (password in DefaultEngine.ini).

Quality tiers:

| Tier | Devices | Resolution scale | Anti-aliasing | Frame cap |
|---|---|---|---|---|
| Android_Epic | Adreno 7xx/8xx, e.g. **S24 Ultra, S25** | 2.0 | TAA | 30 fps |
| Android_High | | 1.5 | TAA | 30 fps |
| Android_Mid | | 1.0 | TAA | 30 fps |
| Android_Low | | 0.75 | TAA | 30 fps |

The lighting is identical on every tier because it is baked; only sharpness and frame rate change.

## Navigation controls

The UE First Person template's touch interface (`Content/Input/Touch/UI_TouchSimple`) is created automatically when the game runs on Android:

* left virtual joystick: walk
* right virtual joystick: look
* button: jump

Gamepads also work (`bAllowControllers=True`).

## Version 3: your feedback on the phone build

| # | Your report | Cause | Fix |
|---|---|---|---|
| 1 | Glitches on the bedroom 2 floor | The marble floor is one mesh for the whole flat. The mobile *forward* renderer gives each mesh one reflection capture (picked from its centre), so bedroom 2 reflected another room, and the reflection jumped as you moved | **Mobile deferred shading** with per-pixel reflection captures (`r.Mobile.ShadingPath=1`, clustered reflections), and reflection captures at 256 px |
| 2 | Grain on cushions and floors while moving | Texture and specular aliasing on fine fabric and marble detail; MSAA only smooths edges | **Temporal AA** (`r.Mobile.AntiAliasing=2`) and 8× anisotropic filtering on the top tiers |
| 3 | Lighting dull, not like the Mac build | (a) Window glass blocked all direct sun in the Cycles bake, since shadow rays can't pass refraction. (b) The sun was weak relative to the lamps, and the sheer curtains blocked 55%. (c) No specular highlights. (d) Neutral colour and low contrast | (a) Glass made light-transparent for the bake. (b) Sun ×3, sky ×2, sheer curtains pass 75% (the Lumen build's balance). (c) All **40 downlights and pendants kept as movable specular-only lights** (diffuse scale 0): highlights on marble, quartz and lacquer. (d) Warm tint on interior lightmaps (1.13 / 0.98 / 0.84), contrast 1.3, saturation 1.08, bloom 0.3, calibrated against the Mac spawn view. **Per-room exposure zones** stand in for Lumen's eye adaptation: kitchen +1.0 EV, foyer +1.1, bedrooms +0.8, baths +0.9 |
| 4 | Material quality in the kitchen and elsewhere | Lightmap detail; no highlights; dark metals | Lightmaps at 112 texels/m (44 MP, up from 31); specular lights (above); metals keep 30% of the baked light, so they're never black; lightmaps at the highest ASTC quality |
| 5 | Background should match the Mac build | Mobile can't run SkyAtmosphere or volumetric clouds | The **Mac sky itself**: six overlapping HDR captures from the Lumen level, stitched in Blender (`blender/scripts/sky_panorama.py`) into a 2048×1024 panorama on an unlit sky dome. Distance haze from height fog (per-pixel fog) |
| 6 | Max 30 fps | | `t.MaxFPS=30` on every tier. The top tier (S24 Ultra / S25) spends the headroom on resolution (scale 2.0) |

Spawn view, Mac vs mobile, on the same viewpoint:

| | Brightness | Warmth (blue relative to average) | Contrast |
|---|---|---|---|
| Mac | 0.17 | 0.53 | 4.3 |
| Mobile v2 | 0.56 | 0.84 | 2.0 |
| Mobile v3 | 0.26 | 0.40 | 4.5 |

The colour was eased slightly after this measurement. Previews: `previews/mobile_preview/es31_*_v3.jpg`, `previews/android/v3/`.

## Version 4: black jagged patches on both bedroom floors

**Cause:** a stray 10 m × 10 m engine `Plane` (plus a 1 m `Cube`) at the origin, at exactly floor height. Both were left in `L_FlatTypeG` by an early one-cube Lightmass test and copied into the mobile level. The plane covered bedroom 1 and the west half of bedroom 2 and z-fought with the marble floor. With no baked lighting it rendered black, and TAA smeared it into jagged streaks as you moved.

How it was found:
* The floor lightmap is correct: a top-down projection, through both Blender's and UE's own lightmap UVs, shows black only under the beds and rugs.
* The patches stayed with the downlights, reflections and post-processing turned off.
* Listing the level actors over the bedroom floor showed the plane.

**Fix:** both shapes were removed from `L_FlatTypeG` and `L_FlatTypeG_Mobile`. `ue_mobile.py` (copy stage, `strip_test_shapes`) now removes any `/Engine/BasicShapes` Plane or Cube before copying, so a rebuild can't bring them back. The Mac app in `build/` was packaged before the test, so it was never affected. The same build also clamps material roughness to at least 0.25, which keeps downlight highlights on marble from overflowing.

**Verified on the Galaxy S24 Ultra:** the bedroom 1 floor and the visible part of bedroom 2 render clean (`previews/android/s24ultra/51_bed1_door.png`, `52_bed1_inside.png`).

## Status and testing

**APK:** `build/Android/FlatTypeG.apk`, 310 MB (version 4).
* Shipping build, arm64, ASTC textures, game data inside the APK.
* Package `com.flatwalkthrough.typeg`, version 1.0, Android 8 and newer (min SDK 26, target SDK 36).
* Signed with the project key (`CN=Type G Flat Walkthrough`, V2 signature verified with `apksigner`).

**Tested in the Android emulator** (Pixel Tablet, Android 15, arm64, 2560×1600; `previews/android/`):
* It installs, launches and loads the flat at the spawn point, facing the living room as on the Mac. Version 3 uses about 440 MB of memory.
* Baked lighting, materials, plants and window views render correctly.
* **Touch controls:** the left stick walked the player across the dining room to the balcony door, and the right stick turned the view. The game ran for several minutes without a crash.
* The camera holds still with no input.
* The `FlatTypeG_Test` emulator (16 GB storage) was added for this. The existing Pixel Tablet emulator has only 6 GB, too little for the APK. It can be deleted in Android Studio → Device Manager.

**Not verified:**
* **On a real S24 Ultra / S25.** The emulator runs on the Mac's GPU, so its frame rate says nothing about phones. The device-profile tier the phones get (Android_Epic) is expected from Unreal's GPU table, not observed.
* **Frame rate, battery and thermals on hardware.** To test, plug the phone in with USB debugging on, then run `adb install build/Android/FlatTypeG.apk`.
* **Vulkan vs OpenGL ES selection on the phones.** Both are packaged, and Vulkan is preferred where the device profile allows it.

**Sharing:** send the APK file. The recipient needs to allow "Install unknown apps" for the app they open it with (Files, Chrome, etc.).

## Rebuild order

1. `Blender -b blender/flat_typeG.blend -P blender/scripts/bake_lightmaps.py -- unreal/import 256 112` (about 15 min on an M5 Pro)
2. `Blender -b --factory-startup -P blender/scripts/denoise_lightmaps.py -- unreal/import` (about 30 s)
3. `unreal/scripts/mobile_level.sh` (re-import, Mac sky capture + panorama, lightmaps, baked materials, meshfix, copy, convert, screenshots; about 16 min)
4. `unreal/scripts/package_android.sh` (about 13 min on a cold cache, about 2 min warm)
