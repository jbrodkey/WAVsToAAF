# WAVsToAAF

Convert WAV files to Advanced Authoring Format (AAF) with rich metadata for fast organizing, relinking, and batch import in Avid Media Composer and other AAF-compatible tools.

Version: v1.0.0

## Overview

WAVsToAAF scans your WAVs, extracts production metadata (BEXT, RIFF LIST-INFO, embedded XML), auto-tags with UCS categories, and builds real AAFs. Use linked media for lightweight bins and easy relink, or embed audio for self-contained handoffs—your choice per run.

## Highlights

- Real AAFs via pyaaf2 (no XML intermediates)
- GUI and CLI workflows
- Linked vs Embedded AAFs (toggle)
- Relink-friendly with NetworkLocator file URLs
- 9 frame rates with normalization (23.98 → 23.976)
- BEXT, LIST-INFO, XML ingestion; UCS auto-categorization
- Single-file or batch folders

## Requirements

- Python 3.8+ (macOS, Windows, Linux)
- pip to install dependencies

Install dependency:

```bash
pip install pyaaf2
```

## Quick Start

### GUI

```bash
python3 wav_to_aaf_gui.py
```

1) Choose a WAV file or a folder
2) Choose an Output Folder
3) Set FPS (defaults to 24)
4) “Embed audio in AAF (default)” is ON by default; uncheck to create linked AAFs
5) Run

The log will show progress and where AAFs were saved. “Open AAF Location” reveals the result.

### Packaging & Run (macOS)

From the WAVsToAAF folder on macOS:

```bash
./packaging/build.sh
```

This creates `dist/WAVsToAAF.app`. The build bundles the `data/` folder so UCS CSVs are available at runtime. If an icon file exists at `icons/mac/WAVsToAAF.icns`, it will be applied automatically.

Launch the app:

```bash
open dist/WAVsToAAF.app
```

Run from source (GUI or CLI):

```bash
# GUI
python3 wav_to_aaf_gui.py

# CLI interactive (prompts for paths)
python3 wav_to_aaf.py
```

### CLI

Interactive (prompts for paths):

```bash
python3 wav_to_aaf.py
```

Batch a folder → folder:

```bash
python3 wav_to_aaf.py ./audio_files ./aaf_output
```

Single file → AAF:

```bash
python3 wav_to_aaf.py -f input.wav output.aaf
```

Common flags:

```bash
# Help / version
python3 wav_to_aaf.py --help
python3 wav_to_aaf.py --version

# Frame rate (timecode calculations)
python3 wav_to_aaf.py ./audio_files ./aaf_output --fps 23.976

# Embed audio into AAF (default). Use --linked to create linked AAFs when preferred.
python3 wav_to_aaf.py -f input.wav output.aaf --embed

# UCS matching
python3 wav_to_aaf.py ./audio_files ./aaf_output --ucs-exact  # disable fuzzy UCS guessing; only exact ID prefixes accepted

# Skip log (enabled by default; only written if files were skipped)
python3 wav_to_aaf.py ./audio_files ./aaf_output --skip-log /path/to/SkipLog.txt
```

Supported FPS values: 23.98, 23.976, 24, 25, 29.97, 30, 50, 59.94, 60

Notes:
- 23.98 is normalized internally to 23.976
- Timecode fields include a StartTC_{fps}fps comment (e.g., StartTC_29_97fps)
- Skip logs help you review files that weren’t processed and the reason (only created when there are skips)

## Linked vs Embedded AAFs

- Embedded (default):
  - Self-contained AAFs; portable and archive-friendly
  - Larger files; no external relink required

- Linked (opt-in via `--linked`):
  - Small AAFs that reference the original WAVs
  - Best for editorial prep, bins, and when you have centralized media storage
  - Relink works via NetworkLocator file URLs

Both modes batch import cleanly in Media Composer. Linked AAFs also relink to original WAVs when media is online.

## What gets written

### AAF structure
- MasterMob with comments for key fields
- SourceMob with WAVE Descriptor
- Timeline slots sized to audio length
- For linked workflows: NetworkLocator to the WAV file URL

### Technicals
- SampleRate, BitDepth, Channels, Number of Frames, Duration
- Start/End timecode fields at selected FPS
- Tracks label (A1, A1A2, A1A{n})

### BEXT (if present)
- Description, Originator, OriginatorReference
- Origination Date/Time, Time Reference, UMID
- Loudness values when available

### LIST-INFO (if present)
- IART, ICMT, ICOP, ICRD, IENG, IGNR, IKEY, INAM, IPRD, ISBJ, ISFT, ISRC …

### XML (if present)
- Keys from EBU Core, BWF MetaEdit, Pro Tools, or generic XML are surfaced with a type prefix (ebucore_, bwfmetaedit_, protools_, axml_, xml_)

### UCS categorization
- Primary category (Category, SubCategory, ID, Full Name)
- Match score

## Examples

Create linked AAFs for a folder at 29.97 fps:

```bash
python3 wav_to_aaf.py ./FX ./AAF --fps 29.97
```

Create an embedded AAF for a single file at 23.976:

```bash
python3 wav_to_aaf.py -f "Some File.wav" "Some File.aaf" --fps 23.976 --embed
```

## Tips

- If your filesystem paths include spaces, quote them as shown above
- On macOS, you can reveal the output from the GUI using “Open AAF Location”
- Linked AAFs are ideal for bins and later relinking to original WAVs

## Compatibility

- Python: 3.8+
- Platforms: macOS, Windows, Linux
- WAV: PCM WAV (.wav, .wave)

Note: This tool intentionally supports only PCM WAV files. Other audio file formats (AIFF, MP3, FLAC, etc.) are not supported. If you need additional formats, convert to WAV externally before running this tool.
- NLEs/DAWs: Avid Media Composer, Pro Tools, and other AAF-capable apps

## Project layout

```
WAVsToAAF/
├── README.md                  # Main documentation (this file)
├── wav_to_aaf.py              # CLI entry point (convert WAVs → AAF)
├── wav_to_aaf_gui.py          # GUI entry point (Tkinter app)
├── requirements.txt           # Python deps for development/CLI
├── .gitignore                 # Ignore build artifacts, caches, DMG staging, etc.
│
├── data/                      # Runtime data files packaged alongside the app
│   └── UCS_v8.2.1_Full_List.csv  # UCS categories (preferred location)
│

## Tests & Continuous Integration

- Unit tests use pytest. Install dev deps and run tests locally with:

```bash
python3 -m pip install -r requirements.txt
pytest -q
```

- Tests are self-contained and generate tiny WAVs at runtime; no external media is required. The project uses `pyaaf2` from PyPI for AAF support.
├── docs/                      # Extra documentation and user-facing assets
│   └── README.rtf             # RTF version styled to match WAVsToALE
│
├── icons/                     # App icons and artwork (mac/win, DMG backgrounds)
│   ├── WAVsToAAF_1024.png
│   ├── mac/
│   └── win/
│
├── dev/                       # Developer utilities (not required at runtime)
│   └── inspect_aaf_metadata.py
│
└── archive/                   # Legacy experiments/tests kept for reference
  └── (older prototypes, test scripts)
```

Notes:
- The app looks for UCS CSVs in data/ (bundled in builds via add-data). Keep future UCS updates here.
- docs/ holds the RTF README so the project root stays clean.
- dev/ and archive/ are optional for daily use; safe to omit from distributions.

## Version History

### v1.0.0 (2025‑11‑04)
- First public release
- GUI and CLI
- Linked vs Embedded AAF option
- 9 FPS options with 23.98 → 23.976 normalization
- BEXT, LIST‑INFO, XML ingest; UCS auto‑categorization
- Single‑file and batch directory processing

## License

Copyright (c) 2025 Jason Brodkey. All rights reserved.

## Related

- WAVsToALE – ALE generator companion utility
- pyaaf2 – Python AAF library used by this tool

## Support

Questions or feature requests? Reach out via your usual channel.