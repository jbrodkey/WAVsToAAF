#!/usr/bin/env bash
set -euo pipefail

# Build WAVsToAAF macOS app with PyInstaller
# - windowed app (no console)
# - includes data/ folder (for UCS CSVs)
# - optional .icns icon if available

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJ_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJ_DIR"

APP_NAME="WAVsToAAF"
ENTRY="$SCRIPT_DIR/gui_launcher.py"
DIST_DIR="$PROJ_DIR/dist"
BUILD_DIR="$PROJ_DIR/build"

# Clean
rm -rf "$DIST_DIR" "$BUILD_DIR"

# Locate icon (optional)
ICON_FLAG=()
if [[ -f "icons/mac/${APP_NAME}.icns" ]]; then
  ICON_FLAG=("--icon" "icons/mac/${APP_NAME}.icns")
elif [[ -f "icons/${APP_NAME}.icns" ]]; then
  ICON_FLAG=("--icon" "icons/${APP_NAME}.icns")
fi

# Ensure PyInstaller is available
if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "Error: pyinstaller not found. Install with: pip install pyinstaller" >&2
  exit 1
fi

# Include entire data directory for future UCS updates
ADD_DATA=("--add-data" "data:data")

# Build
pyinstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --hidden-import wav_to_aaf \
  --hidden-import _version \
  --hidden-import aaf2 \
  ${ICON_FLAG[@]+"${ICON_FLAG[@]}"} \
  "${ADD_DATA[@]}" \
  "$ENTRY"

# Result path
APP_PATH="$DIST_DIR/${APP_NAME}.app"
if [[ -d "$APP_PATH" ]]; then
  echo "Built app: $APP_PATH"
else
  echo "Build failed or app not found in $DIST_DIR" >&2
  exit 2
fi
