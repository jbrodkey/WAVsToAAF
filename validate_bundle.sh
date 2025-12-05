#!/bin/zsh
# Automated validation script for WAVsToAAF macOS app bundle

APP_PATH="dist/WAVsToAAF.app"
PLIST_PATH="$APP_PATH/Contents/Info.plist"

# 1. Check if app bundle exists
if [[ ! -d "$APP_PATH" ]]; then
    echo "Error: App bundle not found at $APP_PATH"
    exit 1
fi

echo "App bundle found: $APP_PATH"

# 2. Validate Info.plist
if [[ ! -f "$PLIST_PATH" ]]; then
    echo "Error: Info.plist not found in app bundle."
    exit 1
fi

echo "Info.plist found. Contents:"
plutil -p "$PLIST_PATH"

# 3. Check version info
VERSION=$(plutil -p "$PLIST_PATH" | grep CFBundleShortVersionString | awk -F '"' '{print $4}')
if [[ -z "$VERSION" ]]; then
    echo "Warning: Version info not found in Info.plist."
else
    echo "App version: $VERSION"
fi

# 4. Attempt to launch the app (headless)
open "$APP_PATH" &
sleep 2
APP_PID=$(pgrep -f "WAVsToAAF")
if [[ -z "$APP_PID" ]]; then
    echo "Warning: App did not launch (may require GUI)."
else
    echo "App launched successfully (PID: $APP_PID)."
    kill "$APP_PID"
fi

# 5. Check code signing status
codesign --verify --verbose "$APP_PATH"
if [[ $? -eq 0 ]]; then
    echo "Code signing: OK"
else
    echo "Code signing: Not signed or invalid (expected for free distribution)"
fi
