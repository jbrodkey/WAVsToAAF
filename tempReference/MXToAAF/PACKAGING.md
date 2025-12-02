# MXToAAF Packaging Guide

## Version Information

Current version: **0.9.0** (pre-release)

Version is managed in `mxto_aaf/__version__.py`

## Building Standalone Executables

### Prerequisites

1. **Python 3.10+** with pip
2. **PyInstaller**: `pip install pyinstaller`
3. **All dependencies**: `pip install -r requirements.txt`
4. **FFmpeg binaries** for your platform

### Quick Build

```bash
chmod +x build_package.sh
./build_package.sh
```

The script will:
- Install dependencies
- Prompt you to download/place FFmpeg binaries
- Build standalone executable with PyInstaller
- Create platform-specific output in `dist/`

### Manual FFmpeg Binary Setup

#### macOS
```bash
# Option 1: Download static builds
# Visit: https://evermeet.cx/ffmpeg/
# Download ffmpeg and ffprobe, place in binaries/macos/

# Option 2: Copy from Homebrew
brew install ffmpeg
cp $(which ffmpeg) binaries/macos/
cp $(which ffprobe) binaries/macos/
chmod +x binaries/macos/*
```

#### Windows
```bash
# Download from: https://www.gyan.dev/ffmpeg/builds/
# Extract ffmpeg.exe and ffprobe.exe to binaries/windows/
```

#### Linux
```bash
# Download from: https://johnvansickle.com/ffmpeg/
# Extract ffmpeg and ffprobe to binaries/linux/
chmod +x binaries/linux/*
```

### Building Manually

```bash
# Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# Place FFmpeg binaries (see above)

# Build
pyinstaller mxtoaaf.spec --clean

# Output will be in dist/
```

### Platform-Specific Outputs

**macOS:**
- App bundle: `dist/MXToAAF.app`
- Executable: `dist/MXToAAF.app/Contents/MacOS/mxtoaaf`
- Can be distributed as `.dmg` or `.app` bundle

**Windows:**
- Executable: `dist/mxtoaaf.exe`
- Can be distributed as standalone `.exe` or with installer

**Linux:**
- Executable: `dist/mxtoaaf`
- Can be distributed as AppImage or standalone binary

## Testing the Build

```bash
# macOS
./dist/MXToAAF.app/Contents/MacOS/mxtoaaf --version

# Windows/Linux
./dist/mxtoaaf --version

# Run a test conversion
./dist/mxtoaaf "sample.m4a" -o output.aaf --embed
```

## Version Management

### Incrementing Version

Edit `mxto_aaf/__version__.py`:

```python
__version__ = "1.0.0"  # Update this
```

Version scheme: `MAJOR.MINOR.PATCH`
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes

Current roadmap:
- `0.9.x`: Pre-release testing
- `1.0.0`: First stable release
- `1.x.x`: Feature additions
- `2.0.0`: Major refactor/breaking changes

### Displaying Version

Users can check version:
```bash
mxtoaaf --version
python3 -m mxto_aaf.cli --version
```

## Distribution

### macOS
1. Build app bundle with `build_package.sh`
2. Test on clean system
3. Code sign (optional): `codesign --sign "Developer ID" dist/MXToAAF.app`
4. Create DMG: `hdiutil create -volname "MXToAAF" -srcfolder dist/MXToAAF.app -ov -format UDZO MXToAAF-0.9.0.dmg`

### Windows
1. Build with `build_package.sh` on Windows
2. Test executable
3. Create installer with Inno Setup or NSIS (optional)
4. Distribute `.exe` or installer

### Linux
1. Build with `build_package.sh`
2. Test on target distributions
3. Create AppImage (optional): Use `appimage-builder`
4. Distribute binary or AppImage

## Troubleshooting

**"ffmpeg not found" error:**
- Ensure binaries are in correct `binaries/` subdirectory
- Check file permissions: `chmod +x binaries/macos/*`
- Verify spec file includes binaries

**"Module not found" errors:**
- Add missing modules to `hiddenimports` in `mxtoaaf.spec`
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`

**Large executable size:**
- Normal for bundled apps (50-150MB)
- Most size is ffmpeg binaries (~40-60MB)
- Can enable UPX compression (already enabled in spec)

## License Compliance

Bundled software licenses are documented in `LICENSES.txt`:
- **FFmpeg**: LGPL v2.1+ (included as separate executable)
- **python-aaf2**: MIT License
- **Mutagen**: GPL v2

When distributing, include `LICENSES.txt` with the application.
