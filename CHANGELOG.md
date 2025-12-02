# Changelog

All notable changes to this project will be documented in this file.

Format based on Keep a Changelog; versioning will follow Semantic Versioning once releases begin.

## [Unreleased]
- Added: Packaging & Run docs; clarified GUI instructions.
- Changed: Embedded AAFs are the default (CLI/GUI); linked via `--linked`.
- Changed: CLI prompts for input when args are omitted (interactive default).
- Fixed: UCS low-confidence collection and report; CSV written next to AAFs (single and batch modes).
- Build: Include `pyaaf2` and `data/` in PyInstaller build (hidden import + resources).
- Tests: Self-contained pytest fixtures (tiny WAVs); 7 tests passing.
- Removed: Unused vendored “aaf python stuff/”.

## [v1.0.0] – internal
- Initial internal version with GUI and CLI.
- Linked vs Embedded AAF support; UCS auto-categorization; FPS normalization (23.98 → 23.976).
- Single-file and batch directory processing; BEXT/LIST-INFO/XML ingestion.
