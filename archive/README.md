# WAVsToAAF – Quick Start

**Version:** v1.0.0

## Overview

WAVsToAAF scans your WAVs, extracts production metadata (BEXT, RIFF LIST-INFO, embedded XML), auto-tags with UCS categories, and builds real AAFs. Use linked media for lightweight bins and easy relink, or embed audio for self-contained handoffs – your choice per run.

## Opening WAVsToAAF on a Mac (macOS)

If you see a security warning:
> "App can't be opened because it is from an unidentified developer."
> 
> OR
> 
> "Apple could not verify..."

You'll need to:
1. Open **System Settings > Privacy & Security**
2. Scroll down to **Security**
3. At the line for WAVsToAAF choose: **Open Anyway**

## What's in the Box

- Real AAFs via pyaaf2 (no XML intermediates)
- GUI and CLI workflows
- Linked vs Embedded AAFs (toggle)
- Relink-friendly with NetworkLocator file URLs
- 9 frame rates with normalization (23.98 → 23.976)
- BEXT, LIST-INFO, XML ingestion; UCS auto-categorization
- Single-file or batch folders

## WAVsToAAF – How to Use

### 1. Select Input
- **Single WAV:** Click "File..." and choose a single `.wav` file
- **Folder of WAVs:** Click "Folder..." and choose a directory that contains WAV files (subfolders supported). The app writes one AAF per WAV.

### 2. Select Output Folder (optional)
- Click "Browse..." to choose where AAF files will be written
- If you leave this blank the app will create an `AAFs` folder next to your WAV directory and write AAFs there

### 3. Set FPS (frames per second)
- Default is 24
- Choose from: 23.98, 23.976, 24, 25, 29.97, 30, 50, 59.94, 60
- 23.98 is normalized internally to 23.976
- Timecode fields include a `StartTC_fpsfps` comment (e.g., `StartTC_29_97fps`)

### 4. Audio Mode: Linked vs Embedded
- **Unchecked (default):** Linked AAFs reference original WAVs via NetworkLocator – small bins, fast relink
- **Checked:** Embedded AAFs are self-contained; portable but larger

### 5. Run Conversion
- Click "Run" – the app processes WAV files, extracts metadata (WAV header, BEXT, embedded XML, LIST/INFO, and UCS filename mapping), and writes AAF(s)
- A log pane displays progress and any skips/errors

### 6. Open Output
- After a successful run, click "Open AAF Location" to reveal the created AAF(s)

## What Gets Written

**AAF Structure:**
- MasterMob with comments
- SourceMob with WAVE Descriptor
- Timeline slots sized to audio length
- For linked mode: a NetworkLocator to the WAV file URL

**Technical Metadata:**
- SampleRate, BitDepth, Channels, Number of Frames, Duration
- Start/End timecode at selected FPS
- Track labels (A1, A1A2, A1An, etc.)

**BEXT (if present):**
- Description, Originator, OriginatorReference
- Origination Date/Time, Time Reference, UMID, Loudness

**LIST-INFO (if present):**
- IART, ICMT, ICOP, ICRD, IENG, IGNR, IKEY, INAM, IPRD, ISBJ, ISFT, ISRC

**XML (if present):**
- Keys from EBU Core, BWF MetaEdit, Pro Tools, or generic XML surfaced with prefixes:
  - `ebucore_`, `bwfmetaedit_`, `protools_`, `axml_`, `xml_`

**UCS Categorization:**
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

## Compatibility

- **Python:** 3.8+
- **Platforms:** macOS, Windows, Linux
- **WAV:** PCM WAV (`.wav`, `.wave`)
- **NLEs/DAWs:** Avid Media Composer, Pro Tools, and other AAF-capable apps

## Support

Questions or feature requests? Reach out via your usual channel.
