# Release: vX.Y.Z

## Highlights
- Short bullets on the most important improvements.

## Changes
- Changed: …
- Added: …
- Removed: …

## Fixes
- Fixed: …

## Packaging
- PyInstaller app: `dist/WAVsToAAF.app` (macOS)
- Bundled resources: `data/UCS_*.csv`
- Notes: Default is embedded AAFs; use `--linked` for linked.

## Checks
- [ ] Tests pass locally (`pytest -q`)
- [ ] App builds (`./packaging/build.sh`)
- [ ] GUI launches (`open dist/WAVsToAAF.app`)
- [ ] Basic embed/linked conversions succeed

## Upgrade Notes
- Breaking/behavior changes and flags to be aware of.

---

Copy this template into the GitHub Release body and edit sections as needed.
