#!/bin/bash
# Build script for WAVsToAAF macOS

# Change to repo root directory
cd "$(dirname "$0")/.." || exit 1

echo "Building WAVsToAAF..."

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
    echo "✗ Build failed or app not found in dist/"
    exit 1
fi
