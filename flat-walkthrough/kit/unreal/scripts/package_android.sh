#!/bin/bash
# Packages the walkthrough for Android (arm64, Vulkan + OpenGL ES 3.1, ASTC textures, data inside the APK)
# -> FlatTypeG/build/Android/FlatTypeG.apk
# Needs UE 5.8 with the Android target platform installed (Epic Games Launcher -> UE 5.8 -> Options -> Android).
# Usage: unreal/scripts/package_android.sh [Variant] [--copy-only]
#   no variant -> build/Android/FlatTypeG.apk (map L_FlatTypeG_Mobile, package com.flatwalkthrough.typeg)
#   Variant    -> build/Android/FlatTypeG_<Variant>.apk (map L_FlatTypeG_<Variant>_Mobile, package <PackageName>.<variant>)
# Each variant is its own app id, so all of them can be installed side by side. Config is restored on exit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENGINE="${UE_ENGINE:-/Users/Shared/Epic Games/UE_5.8/Engine}"
PROJ_DIR="$ROOT/unreal/FlatTypeG"
OUT="$ROOT/build/Android"
VARIANT=""; COPY_ONLY=""
for a in "$@"; do [ "$a" = "--copy-only" ] && COPY_ONLY=1 || VARIANT="$a"; done
SFX="${VARIANT:+_$VARIANT}"
MAPN="L_FlatTypeG${SFX}_Mobile"
INI="$PROJ_DIR/Config/DefaultEngine.ini"
AINI="$PROJ_DIR/Config/Android/AndroidEngine.ini"   # holds the Android start-up map
GINI="$PROJ_DIR/Config/DefaultGame.ini"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export NDKROOT="${NDKROOT:-$(ls -d "$ANDROID_HOME"/ndk/* | sort -V | tail -1)}"
export NDK_ROOT="$NDKROOT"
export JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
# UnrealBuildTool derives a named mutex from the project path; long paths (like this workspace) overflow it.
# Build through a short symlink instead.
SHORT="$HOME/Library/Caches/FlatTypeGBuild"
ln -sfn "$PROJ_DIR" "$SHORT"
if [ -z "$COPY_ONLY" ]; then
  cp "$INI" "$INI.pkgbak"; cp "$AINI" "$AINI.pkgbak"; cp "$GINI" "$GINI.pkgbak"
  trap 'mv "$INI.pkgbak" "$INI"; mv "$AINI.pkgbak" "$AINI"; mv "$GINI.pkgbak" "$GINI"' EXIT
  # /Game/Flat is always cooked (DefaultGame.ini); keep the Mac-only Nanite environment and the Lumen levels out of
  # the APK, or it grows by ~800 MB.
  python3 -c 'import sys,re; p=sys.argv[1]; s=open(p).read(); h="[/Script/UnrealEd.ProjectPackagingSettings]"; assert h in s; open(p,"w").write(s.replace(h, h+"\n+DirectoriesToNeverCook=(Path=\"/Game/Flat/Environment\")",1))' "$GINI"
  sed -i '' "s#^GameDefaultMap=.*#GameDefaultMap=/Game/Flat/Maps/$MAPN.$MAPN#" "$AINI"
  grep -q "^GameDefaultMap=/Game/Flat/Maps/$MAPN" "$AINI"
  if [ -n "$VARIANT" ]; then
    V="$(echo "$VARIANT" | tr 'A-Z' 'a-z')"
    sed -i '' -e "s#^PackageName=\(.*\)#PackageName=\1.$V#" -e "s#^ApplicationDisplayName=\(.*\)#ApplicationDisplayName=\1 ($VARIANT)#" "$INI"
  fi
  "$ENGINE/Build/BatchFiles/RunUAT.sh" BuildCookRun -project="$SHORT/FlatTypeG.uproject" -noP4 \
    -platform=Android -cookflavor=ASTC -clientconfig=Shipping -distribution -map=/Game/Flat/Maps/$MAPN \
    -build -cook -stage -pak -iostore -package -archive -archivedirectory="$PROJ_DIR/Saved/ArchivedAndroid" \
    -ubtargs="-NoUBA" -unattended -utf8output
fi
mkdir -p "$OUT"
APK="$(find "$PROJ_DIR/Saved/ArchivedAndroid" "$PROJ_DIR/Binaries/Android" -name "*.apk" -newer "$PROJ_DIR/FlatTypeG.uproject" 2>/dev/null | head -1)"
[ -n "$APK" ] || { echo "no APK found"; exit 1; }
cp "$APK" "$OUT/FlatTypeG$SFX.apk"
"$ANDROID_HOME/build-tools/$(ls "$ANDROID_HOME/build-tools" | sort -V | tail -1)/apksigner" verify --print-certs "$OUT/FlatTypeG$SFX.apk" | head -3
echo "PACKAGE OK: $OUT/FlatTypeG$SFX.apk ($(du -h "$OUT/FlatTypeG$SFX.apk" | cut -f1))"
