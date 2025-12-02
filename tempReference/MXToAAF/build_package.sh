#!/bin/bash
# Build script for MXToAAF cross-platform packaging

set -e  # Exit on error

echo "============================================"
echo "MXToAAF Packaging Script"
echo "============================================"

# Determine platform
PLATFORM=$(uname -s)
echo "Platform: $PLATFORM"

# Create binaries directory structure
mkdir -p binaries/macos binaries/windows binaries/linux

# Function to setup ffmpeg binaries
setup_ffmpeg() {
    local platform=$1
    local target_dir="binaries/$platform"
    
    echo ""
    echo "Checking FFmpeg binaries for $platform..."
    
    case $platform in
        macos)
            if [ -f "$target_dir/ffmpeg" ] && [ -f "$target_dir/ffprobe" ]; then
                echo "✓ FFmpeg binaries found in $target_dir"
                chmod +x "$target_dir/ffmpeg" "$target_dir/ffprobe"
            else
                echo "⚠ FFmpeg binaries not found in $target_dir"
                echo ""
                echo "Auto-copying from Homebrew installation..."
                if command -v ffmpeg &> /dev/null; then
                    cp "$(which ffmpeg)" "$target_dir/"
                    cp "$(which ffprobe)" "$target_dir/"
                    chmod +x "$target_dir/ffmpeg" "$target_dir/ffprobe"
                    echo "✓ Copied from system installation"
                else
                    echo ""
                    echo "FFmpeg not found. Please install and place binaries:"
                    echo "  Option 1: brew install ffmpeg && cp \$(which ffmpeg) $target_dir/ && cp \$(which ffprobe) $target_dir/"
                    echo "  Option 2: Download from https://evermeet.cx/ffmpeg/ and place in $target_dir/"
                    exit 1
                fi
            fi
            ;;
        windows)
            if [ -f "$target_dir/ffmpeg.exe" ] && [ -f "$target_dir/ffprobe.exe" ]; then
                echo "✓ FFmpeg binaries found in $target_dir"
            else
                echo "⚠ FFmpeg binaries missing. Download from:"
                echo "  https://www.gyan.dev/ffmpeg/builds/"
                echo "  Extract ffmpeg.exe and ffprobe.exe to: $target_dir/"
                exit 1
            fi
            ;;
        linux)
            if [ -f "$target_dir/ffmpeg" ] && [ -f "$target_dir/ffprobe" ]; then
                echo "✓ FFmpeg binaries found in $target_dir"
                chmod +x "$target_dir/ffmpeg" "$target_dir/ffprobe"
            else
                echo "⚠ FFmpeg binaries missing. Download from:"
                echo "  https://johnvansickle.com/ffmpeg/"
                echo "  Extract ffmpeg and ffprobe to: $target_dir/"
                exit 1
            fi
            ;;
    esac
}

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Setup ffmpeg for current platform
case $PLATFORM in
    Darwin)
        setup_ffmpeg macos
        ;;
    Linux)
        setup_ffmpeg linux
        ;;
    MINGW*|MSYS*|CYGWIN*)
        setup_ffmpeg windows
        ;;
esac

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf build dist

# Build with PyInstaller
echo ""
echo "Building executable with PyInstaller..."
pyinstaller mxtoaaf.spec --clean

echo ""
echo "============================================"
echo "Build Complete!"
echo "============================================"

case $PLATFORM in
    Darwin)
        echo "macOS app bundle: dist/MXToAAF.app"
        echo "Executable: dist/MXToAAF.app/Contents/MacOS/mxtoaaf"
        ;;
    *)
        echo "Executable: dist/mxtoaaf"
        ;;
esac

echo ""
echo "To test the build:"
echo "  ./dist/mxtoaaf --version"
echo "  ./dist/mxtoaaf --help"
