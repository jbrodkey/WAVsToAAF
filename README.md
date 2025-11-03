# WAVsToAAF

Convert WAV files to simplified AAF (Advanced Authoring Format) XML files with embedded metadata.

## Overview

WAVsToAAF is a Python utility that scans directories for WAV files, extracts comprehensive audio metadata including BEXT (Broadcast Extension) chunk data, LIST-INFO metadata, embedded XML chunks, and UCS categorization, then generates simplified AAF XML files suitable for media management workflows.

## Features

- **Batch Processing**: Process entire directories of WAV files
- **Single File Mode**: Process individual files
- **BEXT Support**: Extracts broadcast metadata from BEXT chunks
- **LIST-INFO Support**: Extracts RIFF INFO metadata (IART, ICMT, ICOP, INAM, etc.)
- **XML Chunk Support**: Extracts embedded XML metadata (EBU Core, BWF MetaEdit, Pro Tools, etc.)
- **UCS Integration**: Universal Category System sound categorization
- **Audio Metadata**: Captures sample rate, channels, duration, file size
- **Timecode Generation**: Converts duration to timecode format
- **XML Output**: Creates well-formatted AAF XML files
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

### Setup
```bash
# Clone or download the script
cd pythonScripts/WAVsToAAF

# Make executable (Unix/macOS)
chmod +x wav_to_aaf.py
```

## Usage

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
python wav_to_aaf.py -f input.wav output.aaf.xml
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
result = processor.process_single_file('input.wav', 'output.aaf.xml')
```

## Output Format

The generated AAF XML files contain:

### Audio Properties
- Sample rate, channels, bit depth
- Duration in seconds and timecode
- File size and timestamps

### BEXT Metadata (if present)
- Description and originator information
- Origination date and time
- Time reference and UMID
- Loudness metadata (EBU R128)

### UCS Categorization
- Automatic sound categorization using Universal Category System
- Category matching based on filename and BEXT description
- Primary and alternative category suggestions
- Match confidence scoring

### Example Output Structure
```xml
<?xml version="1.0" ?>
<AAF xmlns="http://www.aafassociation.org/aafxml" version="1.1">
  <Header>
    <Version>1.1</Version>
    <Generator>WAVsToAAF v1.0.0</Generator>
    <CreationTime>2025-11-03T...</CreationTime>
  </Header>
  <ContentStorage>
    <MasterMob MobID="urn:uuid:...">
      <Name>audio_file.wav</Name>
      <BextMetadata>
        <Description>Field recording</Description>
        <Originator>Sound Engineer</Originator>
        <OriginationDate>2025-11-03</OriginationDate>
        <!-- ... more BEXT data ... -->
      </BextMetadata>
      <UCSMetadata>
        <PrimaryCategory>
          <ID>AMBNatur</ID>
          <FullName>AMBIENCE NATURE</FullName>
          <Category>AMBIENCE</Category>
          <SubCategory>NATURE</SubCategory>
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

WAVsToAAF automatically categorizes sounds using the Universal Category System v8.2.1:

- **Automatic Detection**: Analyzes filenames and BEXT descriptions
- **753 Categories**: Complete UCS category database included
- **Smart Matching**: Keyword and pattern-based categorization
- **Multiple Suggestions**: Primary category plus alternatives
- **Confidence Scoring**: Match quality assessment

### Category Matching Process:
1. **Filename Analysis**: Extracts keywords from WAV filename
2. **BEXT Integration**: Uses BEXT description if available  
3. **Keyword Matching**: Compares against UCS synonyms and keywords
4. **Scoring Algorithm**: Calculates match confidence
5. **Result Ranking**: Returns best matches with scores

WAVsToAAF automatically detects and extracts BEXT (Broadcast Extension) chunks according to EBU R68-2000 standard:

- **Description**: Textual description of the sound
- **Originator**: Name of the originator/organization
- **Originator Reference**: Unique reference for the originator
- **Origination Date/Time**: When the material was first created
- **Time Reference**: Sample count since midnight
- **UMID**: Unique Material Identifier
- **Loudness Metadata**: EBU R128 loudness values (if present)

## Error Handling

- Gracefully handles corrupted or unsupported files
- Continues processing even if individual files fail
- Provides detailed error messages and progress feedback
- Validates input/output directories

## Limitations

- Generates simplified AAF XML (not full AAF binary format)
- BEXT parsing supports standard EBU R68-2000 format
- No support for other metadata chunks (LIST, etc.)
- Timecode assumes 25fps for frame calculations

## Compatibility

- **Python**: 3.7+
- **Platforms**: Windows, macOS, Linux
- **WAV Formats**: Standard PCM WAV files
- **Dependencies**: None (uses Python standard library)

## Version History

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
- **AAF SDK**: Full AAF binary format support (requires C++ compilation)

## Support

For issues, feature requests, or questions, please create an issue in the project repository.