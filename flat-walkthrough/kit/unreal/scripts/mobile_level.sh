#!/bin/bash
# Builds the Android level L_FlatTypeG_Mobile from the Cycles-baked lightmaps.
# Prereq (Blender, see docs/03_android.md): bake_lightmaps.py + denoise_lightmaps.py
#   -> unreal/import/meshes (2 UV sets) + unreal/import/lightmaps/png
# Usage: [FLAT_VARIANT=SemiFurnished] unreal/scripts/mobile_level.sh [--skip-assets]
# With FLAT_VARIANT the lightmaps come from unreal/import_<variant> (bake of that variant's .blend) and the level is
# L_FlatTypeG_<Variant>_Mobile; the mesh re-import is skipped (meshes are shared with the furnished build).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$HERE/../FlatTypeG/FlatTypeG.uproject"
BIN="/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac"
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
V_LC="$(echo "${FLAT_VARIANT:-}" | tr 'A-Z' 'a-z')"
IMP="$HERE/../import${V_LC:+_$V_LC}"
export FLAT_VARIANT="${FLAT_VARIANT:-}"
gui() {  # run one ue_mobile.py stage in the GUI editor (Content/Python/init_unreal.py hook)
  FLAT_RUN="$HERE/ue_mobile.py" FLAT_STAGES=$1 FLAT_QUIT=1 "$BIN/UnrealEditor.app/Contents/MacOS/UnrealEditor" "$PROJ" -nosplash >/dev/null 2>&1 || true
  cat "$HERE/ue_mobile_report.txt"; echo
}
if [ "${1:-}" != "--skip-assets" ]; then
  # 1. re-import meshes (now with the lightmap UV channel) and their materials, as for the Mac build
  [ -n "$FLAT_VARIANT" ] || FLAT_STAGES=assets "$BIN/UnrealEditor-Cmd" "$PROJ" -run=pythonscript -script="$HERE/ue_build.py" -unattended -nosplash > "$IMP/ue_assets.log" 2>&1
  # 2. the Mac build's sky: six HDR views from the Lumen level, stitched into a panorama
  gui skycap
  "$BLENDER" -b --factory-startup -P "$HERE/../../blender/scripts/sky_panorama.py" -- "$IMP" 2>&1 | grep SKYPANO
  # 3. lightmap + sky textures, baked materials
  FLAT_STAGES=lightmaps,materials "$BIN/UnrealEditor-Cmd" "$PROJ" -run=pythonscript -script="$HERE/ue_mobile.py" -unattended -nosplash > "$IMP/ue_mobile_assets.log" 2>&1 || true   # non-zero on any logged error; the report says what ran
  cat "$HERE/ue_mobile_report.txt"; echo
fi
# 4. Nanite off + keep the Blender lightmap UVs (GUI only), copy the Lumen level, convert it, screenshots
for st in meshfix copy level shots; do gui $st; done
