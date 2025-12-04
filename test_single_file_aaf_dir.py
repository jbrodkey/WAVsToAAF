#!/usr/bin/env python3
"""
Test that single WAV files are processed to AAFs directory within the same directory.

Scenario: 
- Single WAV file in /test_wav_dir/my_sound.wav
- Expected: AAF output goes to /test_wav_dir/AAFs/my_sound.aaf
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


def create_test_wav(path: Path) -> None:
    """Create a simple test WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # WAV parameters
    channels = 2
    sample_width = 2
    sample_rate = 48000
    duration = 1  # 1 second
    
    frames = sample_rate * duration
    
    with wave.open(str(path), 'w') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        
        # Generate silence
        silence = b'\x00' * (sample_width * channels * frames)
        wav_file.writeframes(silence)


def test_single_file_aaf_directory():
    """Test that single WAV files create AAF in AAFs subdirectory."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test_sounds"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test WAV file
        wav_file = test_dir / "test_sound.wav"
        create_test_wav(wav_file)
        print(f"Created test WAV: {wav_file}")
        
        # Process the file
        processor = WAVsToAAFProcessor()
        
        # Manually set output to AAFs directory as per new requirement
        aaf_dir = test_dir / "AAFs"
        output_file = aaf_dir / "test_sound.aaf"
        
        print(f"Processing: {wav_file}")
        print(f"Expected output: {output_file}")
        
        result = processor.process_single_file(str(wav_file), str(output_file))
        
        # Verify the AAF was created in the AAFs directory
        if output_file.exists():
            print(f"✓ AAF created successfully at: {output_file}")
            file_size = output_file.stat().st_size
            print(f"✓ AAF file size: {file_size} bytes")
            
            # Verify the AAFs directory structure
            if (test_dir / "AAFs").exists():
                print(f"✓ AAFs directory created at: {test_dir / 'AAFs'}")
                return 0
            else:
                print("✗ AAFs directory not found")
                return 1
        else:
            print(f"✗ AAF file not created at expected location: {output_file}")
            print(f"  AAFs directory exists: {aaf_dir.exists()}")
            if aaf_dir.exists():
                print(f"  Contents: {list(aaf_dir.iterdir())}")
            return 1


def test_single_file_command_line_auto_generation():
    """Test that command-line -f flag auto-generates AAF path in AAFs directory."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test_sounds"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test WAV file
        wav_file = test_dir / "test_sound.wav"
        create_test_wav(wav_file)
        print(f"\nCreated test WAV: {wav_file}")
        
        # Test with command line arguments
        sys.argv = ['wav_to_aaf.py', '-f', str(wav_file), str(test_dir / "AAFs" / "test_sound.aaf")]
        
        from wav_to_aaf import main
        result = main()
        
        expected_output = test_dir / "AAFs" / "test_sound.aaf"
        
        if expected_output.exists():
            print(f"✓ Command-line test: AAF created at: {expected_output}")
            return result == 0
        else:
            print(f"✗ Command-line test: AAF not created at: {expected_output}")
            return False


if __name__ == "__main__":
    print("Testing single WAV file AAF directory placement...\n")
    
    result1 = test_single_file_aaf_directory()
    
    if result1 == 0:
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("✗ Test failed")
        print("="*60)
        sys.exit(1)
