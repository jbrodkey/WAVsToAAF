# WAVsToAAF

Convert WAV files to Advanced Authoring Format (AAF) files with embedded metadata.

## Overview

WAVsToAAF is a Python utility that scans directories for WAV files, extracts comprehensive audio metadata including BEXT (Broadcast Extension) chunk data, LIST-INFO metadata, embedded XML chunks, and UCS categorization, then generates actual AAF files suitable for professional media workflows.

## Features

- **Batch Processing**: Process entire directories of WAV files
- **Single File Mode**: Process individual files
- **Real AAF Files**: Creates actual .aaf files (not XML) using pyaaf2
- **BEXT Support**: Extracts broadcast metadata from BEXT chunks
- **LIST-INFO Support**: Extracts RIFF INFO metadata (IART, ICMT, ICOP, INAM, etc.)
- **XML Chunk Support**: Extracts embedded XML metadata (EBU Core, BWF MetaEdit, Pro Tools, etc.)
- **UCS Integration**: Universal Category System sound categorization
- **Audio Metadata**: Captures sample rate, channels, duration, file size
- **Linked Media**: Creates AAF files that reference original WAV files
- **Professional Workflow**: Compatible with Avid Media Composer, Pro Tools, and other AAF-compatible software
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Supported Metadata

### Basic WAV Properties
- Sample rate, channels, bit depth
- File size and duration
- Creation and modification times

### BEXT Chunk (Broadcast Extension)
- Description, Originator, Originator Reference
- Origination Date/Time, Time Reference
- UMID (Unique Material Identifier)
- Loudness metadata (LUFS, True Peak, etc.)

### LIST-INFO Chunks (RIFF INFO)
- **IART**: Artist
- **ICMT**: Comment
- **ICOP**: Copyright
- **ICRD**: Creation Date
- **IENG**: Engineer
- **IGNR**: Genre
- **IKEY**: Keywords
- **IMED**: Medium
- **INAM**: Title/Name
- **IPRD**: Product/Album
- **ISBJ**: Subject
- **ISFT**: Software
- **ISRC**: Source
- **ISRF**: Source Form
- **ITCH**: Technician

### XML Chunks (Embedded XML Metadata)
- **EBU Core XML**: `<ebucore:ebuCoreMain>` - European Broadcasting Union metadata standard
- **BWF MetaEdit XML**: `<BWFMetaEdit>` - BWF metadata editor format
- **Pro Tools XML**: `<ProTools>` - Avid Pro Tools session metadata
- **AXML Chunks**: `<axml>` - BWF AXML chunk format
- **Generic XML**: Any `<?xml>` content found in WAV files

### UCS Categorization
- Primary category matching with confidence scores
- Alternative category suggestions
- 753 predefined sound categories

## Installation

### Requirements
- Python 3.7 or higher
- Standard library only (no external dependencies required)
## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Dependencies
Install required Python packages:

```bash
pip install pyaaf2
```

### Setup
```bash
# Clone or download the script
cd pythonScripts/WAVsToAAF

# Make executable (Unix/macOS)
chmod +x wav_to_aaf.py
```

## Usage

### Interactive Mode (Recommended)

Simply run the script without arguments for a user-friendly interactive experience:

```bash
python wav_to_aaf.py
```

The script will prompt you for:
- **Input path**: WAV directory or single WAV file
- **Output path**: AAF output directory or file (with smart defaults)

### Command Line Interface

#### Process Directory (Default)
```bash
# Process current directory, output to ./aaf_output
python wav_to_aaf.py

# Process specific input directory
python wav_to_aaf.py ./audio_files

# Process input directory, specify output directory
python wav_to_aaf.py ./audio_files ./my_aaf_output
```

#### Process Single File
```bash
# Process single WAV file
python wav_to_aaf.py -f input.wav output.aaf
```

#### Help and Version
```bash
# Show help
python wav_to_aaf.py --help

# Show version
python wav_to_aaf.py --version
```

### Python API

```python
from wav_to_aaf import WAVsToAAFProcessor

# Create processor
processor = WAVsToAAFProcessor()

# Process directory
result = processor.process_directory('./audio_files', './aaf_output')

# Process single file
result = processor.process_single_file('input.wav', 'output.aaf')
```

## Output Format

The generated AAF files contain:

### AAF Structure
- Master Mob with embedded metadata
- Source Mob with WAVE descriptor
- File references to original WAV files
- Timeline slots with proper audio mapping

### Audio Properties
- Sample rate, channels, bit depth
- Duration in frames and timecode
- File size and timestamps

### BEXT Metadata (if present)
- Description and originator information embedded in comments
- Origination date and time
- Time reference and UMID
- Loudness metadata (EBU R128)

### UCS Categorization
- Automatic sound categorization using Universal Category System
- Category matching based on filename and BEXT description
- Primary category information embedded in mob name/comments
- Match confidence scoring

### AAF File Benefits
- **Professional Compatibility**: Works with Avid Media Composer, Pro Tools, and other AAF-compatible software
- **Linked Media**: References original WAV files rather than copying/converting audio data
- **Metadata Preservation**: BEXT, INFO, and UCS data embedded in AAF structure
- **Timeline Ready**: Can be imported directly into editing timelines
- **Lossless**: No audio quality degradation as files are linked, not converted

## Universal Category System (UCS) Integration

WAVsToAAF automatically categorizes sounds using the Universal Category System v8.2.1:

- **Automatic Detection**: Analyzes filenames and BEXT descriptions
- **753 Categories**: Complete UCS category database included
- **Smart Matching**: Keyword and pattern-based categorization
- **Primary Category**: Best match embedded in AAF metadata
- **Confidence Scoring**: Match quality assessment

### Category Matching Process:
1. **Filename Analysis**: Extracts keywords from WAV filename
2. **BEXT Integration**: Uses BEXT description if available  
3. **Keyword Matching**: Compares against UCS synonyms and keywords
4. **Scoring Algorithm**: Calculates match confidence
5. **Result Selection**: Returns best match for embedding in AAF

## BEXT Chunk Support

WAVsToAAF automatically detects and extracts BEXT (Broadcast Extension) chunks according to EBU R68-2000 standard:

- **Description**: Textual description of the sound
- **Originator**: Name of the originator/organization
- **Originator Reference**: Unique reference for the originator
- **Origination Date/Time**: When the material was first created
- **Time Reference**: Sample count since midnight
- **UMID**: Unique Material Identifier
- **Loudness Metadata**: EBU R128 loudness values (if present)
          <MatchScore>8.5</MatchScore>
        </PrimaryCategory>
      </UCSMetadata>
      <TimelineMobSlot SlotID="1">
        <AudioProperties>
          <SampleRate>48000</SampleRate>
          <Channels>2</Channels>
          <Duration>00:02:30:00</Duration>
        </AudioProperties>
      </TimelineMobSlot>
    </MasterMob>
  </ContentStorage>
</AAF>
```

## UCS (Universal Category System) Support

## Error Handling

- Gracefully handles corrupted or unsupported files
- Continues processing even if individual files fail
- Provides detailed error messages and progress feedback
- Validates input/output directories

## Limitations

- Creates AAF files with media links (not embedded audio)
- Requires original WAV files to remain accessible for playback
- Comments/metadata support depends on AAF version capabilities

## Compatibility

- **Python**: 3.7+
- **Platforms**: Windows, macOS, Linux
- **WAV Formats**: Standard PCM WAV files
- **Dependencies**: pyaaf2
- **AAF Software**: Avid Media Composer, Pro Tools, DaVinci Resolve, and other AAF-compatible applications

## Version History

### 2.0.0 (2025-11-03)
- **Major Update**: Now creates actual AAF files instead of XML
- Added pyaaf2 dependency for real AAF file generation
- Improved metadata embedding in AAF structure
- Enhanced compatibility with professional audio/video software
- Interactive mode improvements

### 1.3.0 (2025-11-03)
- Added interactive mode for user-friendly input prompting
- Added XML chunk support (EBU Core, BWF MetaEdit, Pro Tools)
- Path sanitization and smart defaults

### 1.2.0 (2025-11-03) 
- Added XML chunk extraction and parsing
- Enhanced metadata extraction capabilities

### 1.1.0 (2025-11-03)
- Added LIST-INFO chunk support
- Expanded metadata extraction

### 1.0.0 (2025-11-03)
- Initial release
- Basic WAV to AAF XML conversion
- BEXT chunk extraction
- Batch and single file processing
- Command line interface

## License

Copyright (c) 2025 Jason Brodkey. All rights reserved.

## Related Projects

- **WAVsToALE**: Convert WAV files to Avid Log Exchange format
- **pyaaf2**: Python library for reading and writing AAF files

## Support

For issues, feature requests, or questions, please create an issue in the project repository.