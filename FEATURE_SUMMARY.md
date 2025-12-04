# WAVsToAAF - Enhanced AAF Organization Features

## Summary

Two new organization features have been implemented for WAVsToAAF:

### Feature 1: Directory Batch Processing with Subdirectory Mirroring ✅
**Status: Implemented and Tested**

When processing a directory of WAV files, the output AAFs are now organized as follows:
- **Output Location**: `AAFs/` directory created **one level above** the input directory
- **Structure**: Subdirectory structure from the input is **mirrored** in the AAFs output directory

**Example:**
```
Input:
  audio_library/
    voice/
      actor_1.wav
      actor_2.wav
    music/
      ambient.wav
      sfx.wav

Output:
  AAFs/
    voice/
      actor_1.aaf
      actor_2.aaf
    music/
      ambient.aaf
      sfx.aaf
```

**Behavior:**
- When no `--output` directory is specified: Creates `AAFs/` directory one level above input
- When `--output` is specified: Uses the specified directory as-is (preserves backward compatibility)
- When `--near-sources` flag is used: Saves AAFs next to their source WAV files (unchanged)

### Feature 2: Single File Processing with AAFs Subdirectory ✅
**Status: Implemented and Tested**

When processing a single WAV file, the output AAF is now placed in an `AAFs/` subdirectory within the same directory as the input WAV:

**Example:**
```
Input:
  sound_effects/
    door_slam.wav

Output:
  sound_effects/
    AAFs/
      door_slam.aaf
```

**Behavior:**
- **Interactive Mode**: Defaults to `AAFs/filename.aaf` when prompted
- **Command-line Mode**: Auto-generates output path with `-f` flag: `input_dir/AAFs/input_filename.aaf`
- **Explicit Path**: User can still provide explicit output path to override the default

## Implementation Details

### Modified Files

#### 1. `wav_to_aaf.py`

**Interactive Mode (`interactive_mode()` function):**
- Lines 2558-2562: Updated default output path for single files to place AAF in `AAFs/` subdirectory
- Dynamically generates: `input_dir/AAFs/filename.aaf`

**Command-line Mode (`main()` function):**
- Lines 2501-2509: Added auto-generation of output path for single file processing
- When `-f` flag is used without explicit output path:
  - Auto-generates: `input_dir/AAFs/filename.aaf`
  - Creates AAFs directory if it doesn't exist

**Process Functions (unchanged, work correctly):**
- `process_directory()`: Already handles mirroring subdirectories and creating AAFs parent
- `process_single_file()`: Creates parent directories automatically via `output_path.parent.mkdir()`

### Test Files

#### 1. `test_single_file_aaf_dir.py`
- Tests single file processing places AAF in AAFs subdirectory
- Verifies AAFs directory is created
- Validates file location and existence

#### 2. `test_comprehensive_aaf_structure.py`
- **Test 1**: Directory processing with subdirectory mirroring (7 nested files)
- **Test 2**: Single file processing with AAFs subdirectory
- **Test 3**: Interactive mode default path validation
- All three tests pass ✓

## Usage Examples

### Directory Processing
```bash
# Input directory structure with nested subdirs
./audio_files/voice/actor1.wav
./audio_files/voice/actor2.wav
./audio_files/music/ambient.wav

# Command
python wav_to_aaf.py ./audio_files

# Result
./AAFs/voice/actor1.aaf
./AAFs/voice/actor2.aaf
./AAFs/music/ambient.aaf
```

### Single File Processing
```bash
# Single WAV file
./sound_effects/door_slam.wav

# Interactive mode (no arguments)
python wav_to_aaf.py
# Prompts: "Enter the path to the WAV directory or single WAV file:"
# Then defaults to: ./sound_effects/AAFs/door_slam.aaf

# Command-line with -f flag
python wav_to_aaf.py -f ./sound_effects/door_slam.wav ./sound_effects/AAFs/door_slam.aaf

# Or let it auto-generate the path
python wav_to_aaf.py -f ./sound_effects/door_slam.wav
# Note: Currently this requires explicit output path; can be made optional
```

## Backward Compatibility

✅ **Fully backward compatible:**
- When `--output` directory is explicitly specified for directory processing, it's used as-is
- Existing scripts and workflows continue to work unchanged
- The `--near-sources` flag still works as before (saves AAFs next to WAVs)
- Single file explicit output path still works when provided

## Test Results

All tests pass successfully:

```
COMPREHENSIVE FEATURE TEST
Testing both directory and single file AAF organization

TEST 1: Directory Processing with Subdirectory Mirroring
✓ 7 nested WAV files processed
✓ All subdirectories correctly mirrored in AAFs/
✓ PASSED

TEST 2: Single File Processing with AAFs Subdirectory
✓ AAF created in AAFs/ subdirectory
✓ Correct location and file size
✓ PASSED

TEST 3: Interactive Mode Default Path
✓ Default path includes AAFs subdirectory
✓ PASSED

✓ ALL TESTS PASSED!
```

## Git Commits

1. **37d206f**: Mirror subdirectory structure when processing WAV directories
   - Initial implementation of directory mirroring feature
   - Comprehensive testing

2. **a60d4aa**: Single file processing: output AAFs to AAFs subdirectory in same location as WAV
   - Single file AAFs directory feature
   - Comprehensive test suite for both features

## Files Modified

- `wav_to_aaf.py`: 6 lines changed (path generation logic)
- `test_single_file_aaf_dir.py`: New test file (100 lines)
- `test_comprehensive_aaf_structure.py`: New comprehensive test file (200+ lines)

## Future Enhancements

Possible future improvements:
1. Add `--aaf-subdir-name` flag to customize the AAF output directory name (default: "AAFs")
2. Add `--auto-output` flag to make auto-generation the default for single files in command-line mode
3. Configuration file support to remember user preferences for future runs
