#!/bin/bash
# Packages the walkthrough as a macOS Shipping app.
#   unreal/scripts/package_mac.sh                  -> build/Mac/FlatTypeG.app            (map L_FlatTypeG)
#   unreal/scripts/package_mac.sh SemiFurnished    -> build/Mac_SemiFurnished/FlatTypeG_SemiFurnished.app (+ zip)
# A variant app gets its own name and bundle id so it sits next to the furnished one. The start-up map is switched
# only for the cook and restored on exit. Add --copy-only after the variant to skip the cook.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENGINE="${UE_ENGINE:-/Users/Shared/Epic Games/UE_5.8/Engine}"
PROJ_DIR="$ROOT/unreal/FlatTypeG"
VARIANT=""; COPY_ONLY=""
for a in "$@"; do [ "$a" = "--copy-only" ] && COPY_ONLY=1 || VARIANT="$a"; done
SFX="${VARIANT:+_$VARIANT}"
NAME="FlatTypeG$SFX"
MAPN="L_FlatTypeG$SFX"
MAP="/Game/Flat/Maps/$MAPN"
OUT="$ROOT/build/Mac$SFX"
APP="$OUT/$NAME.app"
INI="$PROJ_DIR/Config/DefaultEngine.ini"
if [ -z "$COPY_ONLY" ]; then
  cp "$INI" "$INI.pkgbak"
  trap 'mv "$INI.pkgbak" "$INI"' EXIT
  sed -i '' "s#^GameDefaultMap=.*#GameDefaultMap=$MAP.$MAPN#" "$INI"
  grep -q "^GameDefaultMap=$MAP" "$INI"
  "$ENGINE/Build/BatchFiles/RunUAT.sh" BuildCookRun -project="$PROJ_DIR/FlatTypeG.uproject" -noP4 -platform=Mac \
    -clientconfig=Shipping -map=$MAP -build -cook -stage -pak -iostore -prereqs -unattended -utf8output
fi
# UE 5.8's -archive step copies the bare Binaries/ .app (no staged data) for content-only Mac projects, which crashes
# at launch, so the complete bundle is taken from the staging directory.
rm -rf "$OUT"; mkdir -p "$OUT"
ditto "$PROJ_DIR/Saved/StagedBuilds/Mac/FlatTypeG-Mac-Shipping.app" "$APP"
if [ -n "$VARIANT" ]; then
  PL="$APP/Contents/Info.plist"
  /usr/libexec/PlistBuddy -c "Set :CFBundleName $NAME" -c "Set :CFBundleIdentifier com.flatwalkthrough.typeg.$(echo "$VARIANT" | tr 'A-Z' 'a-z')" "$PL"
  /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string $NAME" "$PL" 2>/dev/null || /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName $NAME" "$PL"
  codesign --force --deep -s - "$APP"
fi
codesign --verify --deep "$APP"
(cd "$OUT" && ditto -c -k --keepParent "$NAME.app" "$ROOT/build/${NAME}_macOS.zip")
echo "PACKAGE OK: $APP ($(du -sh "$APP" | cut -f1)); zip build/${NAME}_macOS.zip"
