#!/bin/bash
# Build script for WAVsToAAF macOS

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
else
    echo "✗ Build failed or app not found in dist/"
    exit 1
fi
