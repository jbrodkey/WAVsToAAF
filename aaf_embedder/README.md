# AAF WAV/AIFF/DNxHD/HR Embedder

This command-line tool creates AAF files with embedded PCM audio (WAV, AIFF) and/or DNxHD/DNxHR video, using the official AAF SDK.

## Features
- Audio-only AAFs (WAV/AIFF, PCM)
- Video-only AAFs (DNxHD/DNxHR)
- Audio+Video AAFs (both embedded)
- Output AAF file name follows input audio/video file naming
- Only embedded essence (no external references)

## Usage
```
Usage: aaf_embedder [options]

Options:
  --audio <file.wav|file.aiff>   Input audio file (WAV or AIFF)
  --video <file.mxf>             Input video file (DNxHD/DNxHR MXF)
  --output <file.aaf>            Output AAF file (optional, defaults to input file name with .aaf extension)
  --mode <audio|video|audiovideo>  Type of AAF to create
  --help                         Show usage
```

### Examples
- Audio-only: `aaf_embedder --audio myclip.wav --mode audio`
- Video-only: `aaf_embedder --video myclip.mxf --mode video`
- Audio+Video: `aaf_embedder --audio myclip.wav --video myclip.mxf --mode audiovideo`

If `--output` is not specified, the output AAF will be named after the input file(s):
- Audio-only: `myclip.aaf`
- Video-only: `myclip.aaf`
- Audio+Video: `myclip.aaf` (uses audio file name if both provided)

## Build Instructions
1. Install the AAF SDK (https://github.com/AAFAssociation/aaf)
2. Build with CMake:
   ```
   mkdir build && cd build
   cmake ..
   make
   ```

## Requirements
- macOS (or Linux/Windows)
- C++17 or newer
- AAF SDK (built and installed)

## Notes
- Only PCM audio (WAV/AIFF) and DNxHD/DNxHR video are supported for maximum Avid compatibility.
- All essence is embedded; no external references.
- Metadata and naming conventions follow input file names.

## License
MIT
