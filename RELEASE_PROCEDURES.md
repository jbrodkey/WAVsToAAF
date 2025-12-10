# WAVsToAAF Release Procedures

This document outlines the process for releasing new versions of WAVsToAAF.

## Version Management

### 1. Update Version Number
Edit `_version.py` and update the version:

```python
__version__ = "1.0.1"  # Change this for each release
```

The version string follows semantic versioning: `MAJOR.MINOR.PATCH`

## Building Distributions

### macOS Build

```bash
cd packaging
./build.sh
```

This script will:
1. Extract version from `_version.py`
2. Clean previous builds (`build/`, `dist/`)
3. Run PyInstaller with `WAVsToAAF.spec`
4. Update `Info.plist` with version information
5. Validate the app bundle (check executable, size, permissions)

**Output:** `dist/WAVsToAAF.app` (app bundle ready for distribution)

### Windows Build

Windows builds are automated via GitHub Actions. When you push to the `main` branch, the workflow:

1. Extracts version from `_version.py`
2. Installs dependencies
3. Runs syntax check
4. Builds exe with PyInstaller using `packaging/WAVsToAAF-Windows.spec`
5. Creates distribution package: `WAVsToAAF_v{version}.zip`
6. Runs validation checks
7. Uploads artifact to GitHub

**Output:** `WAVsToAAF_v{version}.zip` (Windows distribution package)

## Bundled Content

Both builds automatically include:
- Main application executable
- Icon (icns for macOS, ico for Windows)
- Data files from `data/` directory
- LICENSES.txt (with third-party attributions)
- README.md (main documentation)
- Platform-specific README (README_mac.md or README_windows.md)
- All aaf2 library dependencies

### What Gets Bundled
- **Data:** UCS category definitions, localization files
- **Documentation:** Platform guides, this file
- **Licenses:** Third-party attributions (pyaaf2 MIT license)
- **Code:** Main application files, _version.py

## Pre-Release Checklist

Before releasing a new version:

1. **Test GUI functionality:**
   - ✓ File/folder selection
   - ✓ Progress display updates correctly
   - ✓ Error handling (missing source, invalid FPS)
   - ✓ Output to AAFs directory works
   - ✓ Embed/linked mode toggle works
   - ✓ UCS inference toggle works
   - ✓ Help menu displays correctly
   - ✓ License/About dialogs appear
   - ✓ Open AAF Location button works

2. **Test CLI mode:**
   ```bash
   python wav_to_aaf.py <input> <output> --fps 24 --embed
   ```

3. **Test batch processing:**
   - Single WAV file
   - Directory with multiple WAVs
   - Stereo WAVs (verify L/R panning)
   - WAVs with BEXT metadata
   - WAVs with embedded XML

4. **Verify documentation:**
   - README.md is current
   - README_mac.md and README_windows.md are current
   - LICENSES.txt includes all dependencies
   - Help system displays correctly in bundled app

5. **Test bundled app:**
   ```bash
   # macOS
   ./dist/WAVsToAAF.app/Contents/MacOS/WAVsToAAF
   
   # Windows (from PowerShell)
   .\dist\WAVsToAAF.exe
   ```

## Release Process

### 1. Update Version
```bash
# Edit _version.py
__version__ = "1.1.0"
```

### 2. Update Changelog (optional)
Add entry to `CHANGELOG.md`:
```markdown
## v1.1.0 (2025-12-10)
- Added Help menu with documentation
- Improved progress display for batch processing
- Fixed source validation error handling
- Better AAFs directory structure management
```

### 3. Commit Version Changes
```bash
git add _version.py CHANGELOG.md
git commit -m "release: prepare v1.1.0"
git push
```

### 4. Trigger Windows Build
GitHub Actions will automatically build Windows distribution on push to main.

### 5. Build macOS Distribution
```bash
cd packaging
./build.sh
# Output: dist/WAVsToAAF.app
```

### 6. Create Release on GitHub
1. Go to https://github.com/jbrodkey/WAVsToAAF/releases
2. Click "Draft a new release"
3. Tag: `v1.1.0`
4. Title: `WAVsToAAF v1.1.0`
5. Description: Changelog notes
6. Upload artifacts:
   - `dist/WAVsToAAF.app` (as zip: `WAVsToAAF_v1.1.0_mac.zip`)
   - Windows artifact from GitHub Actions (copy WAVsToAAF_v1.1.0.zip)
7. Check "Create a discussion for this release"
8. Publish

## Distribution

### macOS Distribution
- Package: `WAVsToAAF.app` (app bundle)
- Users can double-click to run or place in Applications folder
- Code signing not currently implemented (users may see security warning)
- Minimum macOS: 10.9+ (Python 3.8+ requirement)

### Windows Distribution
- Package: `WAVsToAAF_v{version}.zip`
- Extract zip to get folder with exe and documentation
- Users can run exe directly (no installation required)
- Windows 7+ (Python 3.8+ requirement)

## Post-Release

1. **Announce release:**
   - Email users if applicable
   - Update website (www.editcandy.com)
   - Post release notes

2. **Monitor issues:**
   - Watch GitHub issues for bug reports
   - Respond to user feedback

3. **Plan next release:**
   - Collect feature requests
   - Prioritize improvements
   - Plan development cycle

## Troubleshooting Build Issues

### macOS Build Fails
```bash
# Check Python and PyInstaller
python --version
which pyinstaller
pyinstaller --version

# Verify spec file
python packaging/build.sh -v

# Check for icon file
ls -la icons/mac/WAVsToAAF.icns
```

### Windows Build Fails (GitHub Actions)
1. Check workflow logs: https://github.com/jbrodkey/WAVsToAAF/actions
2. Common issues:
   - Python version mismatch
   - Missing dependencies (pip install -r requirements.txt)
   - Syntax errors in code

### App Won't Start
- Check _version.py format (must have `__version__ = "x.y.z"`)
- Verify all bundled files exist (data/, docs/, LICENSES.txt)
- Check for runtime errors in log (GUI may show error messages)

## Version History

- **v1.0.0** - Initial release with core WAV-to-AAF conversion, GUI, UCS inference
- **v1.1.0** - Added Help menu, improved progress display, better error handling

## Notes for Future Releases

- Consider code signing for macOS (requires Apple Developer account)
- Consider notarization for macOS (required for newer versions)
- Plan for Windows installer (msi) if user base grows
- Keep dependencies minimal (currently only pyaaf2)
- Maintain backward compatibility with CLI interface
