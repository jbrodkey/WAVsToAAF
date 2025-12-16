#!/bin/bash
# Build script for WAVsToAAF macOS

# Change to repo root directory (script now lives in root, so stay in current dir)
cd "$(dirname "$0")" || exit 1

echo "Building WAVsToAAF..."

# Extract version from _version.py
VERSION=$(grep "__version__" _version.py | sed 's/.*"\(.*\)".*/\1/')
echo "Version: $VERSION"

# Check for icon file
if [ -f "icons/mac/WAVsToAAF.icns" ]; then
    echo "Found macOS icon, including in build..."
else
    echo "Warning: No icon found at icons/mac/WAVsToAAF.icns"
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/

# Build with PyInstaller using spec file
echo "Building application..."
pyinstaller WAVsToAAF.spec

# Check if build succeeded
if [ -d "dist/WAVsToAAF.app" ]; then
    echo "✓ Build complete! WAVsToAAF.app is ready at dist/WAVsToAAF.app"
    
    # Update Info.plist with version information
    PLIST="dist/WAVsToAAF.app/Contents/Info.plist"
    if [ -f "$PLIST" ]; then
        echo "Updating Info.plist with version $VERSION..."
        
        # Use plutil to update plist (available on macOS)
        if command -v plutil &> /dev/null; then
            plutil -replace CFBundleShortVersionString -string "$VERSION" "$PLIST"
            plutil -replace CFBundleVersion -string "$VERSION" "$PLIST"
            echo "✓ Info.plist updated"
        else
            echo "Warning: plutil not found, skipping Info.plist update"
        fi
    fi
    
    # Validate the app
    echo ""
    echo "Validating build..."
    APP_PATH="dist/WAVsToAAF.app"
    EXECUTABLE="$APP_PATH/Contents/MacOS/WAVsToAAF"
    
    if [ -f "$EXECUTABLE" ]; then
        echo "✓ Executable found"
        if [ -x "$EXECUTABLE" ]; then
            echo "✓ Executable is runnable"
            FILE_SIZE=$(du -sh "$APP_PATH" | cut -f1)
            echo "✓ App bundle size: $FILE_SIZE"
        else
            echo "✗ Executable is not runnable"
            exit 1
        fi
    else
        echo "✗ Executable not found at $EXECUTABLE"
        exit 1
    fi
    
    echo ""
    echo "✓ Build validation passed!"
else
    echo "✗ Build failed: dist/WAVsToAAF.app not found"
    exit 1
fi
