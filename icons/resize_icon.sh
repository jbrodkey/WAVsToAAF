#!/bin/bash
# Resize a 1024x1024 PNG icon to all required sizes for macOS icon sets
# Usage: ./resize_icon.sh WAVsToAAF_1024.png

if [ $# -eq 0 ]; then
    echo "Usage: $0 <input_png_file>"
    echo "Example: $0 WAVsToAAF_1024.png"
    exit 1
fi

INPUT_FILE="$1"

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: File '$INPUT_FILE' not found"
    exit 1
fi

mkdir -p DMG.iconset
sips -z 16 16     "$INPUT_FILE" --out DMG.iconset/icon_16x16.png
sips -z 32 32     "$INPUT_FILE" --out DMG.iconset/icon_16x16@2x.png
sips -z 32 32     "$INPUT_FILE" --out DMG.iconset/icon_32x32.png
sips -z 64 64     "$INPUT_FILE" --out DMG.iconset/icon_32x32@2x.png
sips -z 128 128   "$INPUT_FILE" --out DMG.iconset/icon_128x128.png
sips -z 256 256   "$INPUT_FILE" --out DMG.iconset/icon_128x128@2x.png
sips -z 256 256   "$INPUT_FILE" --out DMG.iconset/icon_256x256.png
sips -z 512 512   "$INPUT_FILE" --out DMG.iconset/icon_256x512@2x.png
sips -z 512 512   "$INPUT_FILE" --out DMG.iconset/icon_512x512.png
cp "$INPUT_FILE" DMG.iconset/icon_512x512@2x.png

echo "Icon set created in DMG.iconset/"
