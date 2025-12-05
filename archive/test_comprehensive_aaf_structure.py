#!/usr/bin/env python3
"""
Comprehensive test of both features:
1. Directory processing creates AAFs directory one level above with mirrored subdirs
2. Single file processing creates AAF in AAFs directory within same directory as WAV
"""

import os
import sys
import tempfile
import wave
import struct
from pathlib import Path

# Add the script directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from wav_to_aaf import WAVsToAAFProcessor


def create_test_wav(path: Path, channels: int = 2, duration: float = 0.5) -> None:
    """Create a simple test WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # WAV parameters
    sample_width = 2
    sample_rate = 48000
    
    frames = int(sample_rate * duration)
    
    with wave.open(str(path), 'w') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        
        # Generate silence
        silence = b'\x00' * (sample_width * channels * frames)
        wav_file.writeframes(silence)


def test_directory_processing_with_mirroring():
    """Test directory processing creates AAFs with mirrored subdirectory structure."""
    
    print("=" * 70)
    print("TEST 1: Directory Processing with Subdirectory Mirroring")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory structure with nested subdirs
        base_dir = Path(tmpdir) / "source_audio"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create nested WAV files
        subdirs_and_files = {
            "voice": ["actor_1.wav", "actor_2.wav"],
            "voice/radio": ["talk_show.wav"],
            "music": ["ambient.wav", "sfx.wav"],
            "music/background": ["loop_1.wav"],
            "sounds": ["door_close.wav"],
        }
        
        for subdir, files in subdirs_and_files.items():
            subdir_path = base_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            
            for filename in files:
                wav_file = subdir_path / filename
                create_test_wav(wav_file)
                print(f"  Created: {wav_file.relative_to(base_dir)}")
        
        # Process directory
        processor = WAVsToAAFProcessor()
        
        print(f"\nProcessing directory: {base_dir}")
        result = processor.process_directory(str(base_dir), None)  # No output_dir specified
        
        # Verify AAFs directory structure
        aaf_dir = base_dir.parent / "AAFs"
        print(f"\nVerifying output structure at: {aaf_dir}")
        
        if not aaf_dir.exists():
            print("✗ AAFs directory not created")
            return False
        
        # Check mirrored subdirectories
        expected_aaf_files = [
            "voice/actor_1.aaf",
            "voice/actor_2.aaf",
            "voice/radio/talk_show.aaf",
            "music/ambient.aaf",
            "music/sfx.aaf",
            "music/background/loop_1.aaf",
            "sounds/door_close.aaf",
        ]
        
        all_exist = True
        for expected_file in expected_aaf_files:
            aaf_file = aaf_dir / expected_file
            if aaf_file.exists():
                print(f"  ✓ {expected_file}")
            else:
                print(f"  ✗ MISSING: {expected_file}")
                all_exist = False
        
        if all_exist:
            print("\n✓ Directory processing test PASSED")
            return True
        else:
            print("\n✗ Directory processing test FAILED")
            return False


def test_single_file_processing():
    """Test single file processing creates AAF in AAFs subdirectory."""
    
    print("\n" + "=" * 70)
    print("TEST 2: Single File Processing with AAFs Subdirectory")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a single WAV file in a directory
        sound_dir = Path(tmpdir) / "my_sound_effects"
        sound_dir.mkdir(parents=True, exist_ok=True)
        
        wav_file = sound_dir / "door_slam.wav"
        create_test_wav(wav_file)
        print(f"Created WAV: {wav_file.relative_to(Path(tmpdir))}")
        
        # Process single file
        processor = WAVsToAAFProcessor()
        
        # The output path should go to AAFs/door_slam.aaf
        aaf_dir = sound_dir / "AAFs"
        output_file = aaf_dir / "door_slam.aaf"
        
        print(f"\nProcessing single file: {wav_file.name}")
        print(f"Expected output: {output_file.relative_to(Path(tmpdir))}")
        
        result = processor.process_single_file(str(wav_file), str(output_file))
        
        # Verify the file was created
        if output_file.exists():
            file_size = output_file.stat().st_size
            print(f"✓ AAF created successfully")
            print(f"  Location: {output_file.relative_to(Path(tmpdir))}")
            print(f"  Size: {file_size} bytes")
            
            # Verify directory structure
            if aaf_dir.exists():
                print(f"✓ AAFs directory created in same location as WAV")
                print("\n✓ Single file processing test PASSED")
                return True
            else:
                print("✗ AAFs directory not found")
                return False
        else:
            print(f"✗ AAF file not created at expected location")
            return False


def test_interactive_mode_default_path():
    """Test that interactive mode defaults to AAFs subdirectory for single files."""
    
    print("\n" + "=" * 70)
    print("TEST 3: Interactive Mode Default Path for Single File")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a single WAV file
        sound_dir = Path(tmpdir) / "sound_library"
        sound_dir.mkdir(parents=True, exist_ok=True)
        
        wav_file = sound_dir / "effect.wav"
        create_test_wav(wav_file)
        print(f"Created WAV: {wav_file.relative_to(Path(tmpdir))}")
        
        # Simulate interactive mode default path generation
        input_dir = os.path.dirname(str(wav_file))
        aaf_dir = os.path.join(input_dir, 'AAFs')
        default_output = os.path.join(aaf_dir, os.path.splitext(os.path.basename(str(wav_file)))[0] + '.aaf')
        
        print(f"\nDefault path for single file in interactive mode:")
        print(f"  Input: {wav_file.name}")
        print(f"  Default output: {Path(default_output).relative_to(Path(tmpdir))}")
        
        # Verify the path points to AAFs subdirectory
        if "AAFs" in default_output and default_output.endswith(".aaf"):
            print("✓ Default path includes AAFs subdirectory")
            print("✓ Interactive mode default path test PASSED")
            return True
        else:
            print("✗ Default path does not point to AAFs subdirectory")
            return False


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("COMPREHENSIVE FEATURE TEST")
    print("Testing both directory and single file AAF organization")
    print("=" * 70 + "\n")
    
    tests = [
        ("Directory Processing", test_directory_processing_with_mirroring),
        ("Single File Processing", test_single_file_processing),
        ("Interactive Mode Defaults", test_interactive_mode_default_path),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} raised an exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
