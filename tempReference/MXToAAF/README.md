# MXToAAF (workspace)

MXToAAF converts music files (mp3, m4a, aif, wav) into AAFs for Avid importing with rich metadata.

## Metadata Fields

MXToAAF extracts and embeds the following metadata fields into AAF files for display in Avid's bin columns:

**Core Fields:**
- **Track Name**: Song/track title (Avid column: "Track Name") - Primary identifier
- **Track**: Track number, e.g. "6" (Avid column: "Track") - Parsed from "6/10" format
- **Total Tracks**: Total tracks in album (Avid column: "Total Tracks") - Extracted from "6/10" format
- **Genre**: Musical genre (Avid column: "Genre") - Normalizes ID3 numeric codes like "(17)" → "Rock"

**Artist/Credits:**
- **Artist**: Primary artist/performer (Avid column: "Artist") - Falls back to album artist if not set
- **Album Artist**: Album-level artist - Separate from track artist when different
- **Talent**: Performer/artist (Avid column: "Talent") - Maps to Artist or Album Artist
- **Composer**: Song composer/writer (Avid column: "Composer")

**Album/Source:**
- **Source**: Album/source name (Avid column: "Source") - Used in AAF Name as "Source_TrackName"
- **Album**: Album title (Avid column: "Album") - Synonym for Source

**Additional:**
- **Catalog #**: Catalog number (Avid column: "Catalog #")
- **Description**: Notes/comments (Avid column: "Description")
- **Duration**: Length in seconds (Avid column: "Duration") - Extracted from audio file

**AAF Name Format:**
Each AAF's name is set to `Source_TrackName` (e.g., "Flicka_Main Title") to provide clear identification in Avid bins.

Dependencies / tag extraction
-----------------------------
- MXToAAF uses the `mutagen` Python library to read tags from MP3, MP4/M4A, AIFF and other audio formats when available.
- If `mutagen` is not installed, MXToAAF will fall back to `ffprobe` (from the ffmpeg toolchain) to read metadata atoms/tags present in media files (useful for macOS MP4/M4A atoms and many container formats).
- To get the best results, install mutagen as a dependency (there's a `requirements.txt` entry for it in this repo). CI installs this automatically.
- **Genre normalization**: ID3v1 numeric genre codes like "(17)" are automatically converted to text (e.g., "Rock"). Empty or placeholder values are filtered out.

Tag mapping
-----------
MXToAAF supports configurable mapping from extracted metadata fields to AAF tag names. The default mapping is:

```json
{
  "track_name": "TrackName",
  "talent": "Artist",
  "composer": "Composer",
  "album": "Album",
  "source": "Source",
  "track": "TrackNumber",
  "catalog_number": "CatalogNumber",
  "description": "Description",
  "duration": "Duration"
}
```

You can pass a custom map to the low-level `create_music_aaf` call (programmatically) using the `tag_map` parameter.

Unified CLI
-----------
MXToAAF provides a unified command that automatically detects whether your input is a single file or a directory:

```bash
# Single file conversion
python3 -m mxto_aaf "path/to/song.mp3" -o output.aaf --embed

# Batch directory conversion
python3 -m mxto_aaf "Sample Media/wavTest_MX" -o ./out-aafs --embed

# Interactive mode (prompts for input/output if not provided)
python3 -m mxto_aaf

# Batch with CSV reports
python3 -m mxto_aaf "Sample Media/wavTest_MX" -o ./out-aafs --embed --skip-existing \
  --export-csv ./out-aafs/results.csv --export-metadata-csv ./out-aafs/metadata.csv
```

Batch processing options:
- `--skip-existing`: Skip files if output AAF already exists
- `--export-csv`: Write per-file processing results (status, errors, duration)
- `--export-metadata-csv`: Write detailed parsed metadata fields (Track Name, Track, Genre, Artist, etc.)
- `--log-file`: Write detailed JSON log
- `--max-files`: Limit processing to N files for testing
- `--no-recursive`: Don't recurse into subdirectories
