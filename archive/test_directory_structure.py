#!/usr/bin/env python3
"""
Test script to demonstrate the new directory structure feature for WAVsToAAF.

This script creates a test directory structure with sample WAVs in subdirectories,
then processes them to show how the AAFs directory mirrors the input structure.

Usage:
    python test_directory_structure.py
"""

import os
import tempfile
import shutil
from pathlib import Path
from wav_to_aaf import WAVsToAAFProcessor
import wave
import struct

def create_test_wav(filepath: str, duration: float = 1.0, sample_rate: int = 48000):
    """Create a simple test WAV file with a sine wave tone."""
    import math
    
    # Create directory if needed
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    # Generate sine wave samples (440 Hz tone)
    num_samples = int(sample_rate * duration)
    frequency = 440  # Hz
    amplitude = 32767 // 2  # Half max to avoid clipping
    
    samples = []
    for i in range(num_samples):
        sample = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(sample)
    
    # Write WAV file
    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        # Pack samples as bytes
        for sample in samples:
            # Convert to signed 16-bit little-endian
            wav_file.writeframes(struct.pack('<h', sample))

def main():
    # Create a temporary test directory
    test_dir = tempfile.mkdtemp(prefix="wav_structure_test_")
    print(f"Created test directory: {test_dir}")
    
    try:
        # Create subdirectory structure with WAVs
        subdirs = [
            'sounds/effects/impact',
            'sounds/effects/foley',
            'sounds/ambience/outdoor',
            'sounds/ambience/indoor',
            'music/background',
        ]
        
        wav_files_created = []
        
        for subdir in subdirs:
            full_dir = os.path.join(test_dir, subdir)
            Path(full_dir).mkdir(parents=True, exist_ok=True)
            
            # Create 2 test WAVs in each directory
            for i in range(1, 3):
                wav_file = os.path.join(full_dir, f"test_sound_{i}.wav")
                create_test_wav(wav_file, duration=0.1)
                wav_files_created.append(wav_file)
                print(f"  Created: {os.path.relpath(wav_file, test_dir)}")
        
        print(f"\nCreated {len(wav_files_created)} test WAV files")
        print("\nTest directory structure:")
        print_tree(test_dir, prefix="  ")
        
        # Now process the directory
        print("\n" + "="*70)
        print("Processing directory with WAVsToAAF...")
        print("="*70 + "\n")
        
        processor = WAVsToAAFProcessor()
        
        # Process without specifying output dir (should create AAFs one level above)
        result = processor.process_directory(
            test_dir, 
            "",  # Empty output_dir to trigger default behavior
            fps=24,
            embed_audio=True
        )
        
        # Show the resulting directory structure
        aaf_dir = os.path.join(os.path.dirname(test_dir), 'AAFs')
        
        print("\n" + "="*70)
        print("Resulting directory structure:")
        print("="*70 + "\n")
        
        if os.path.exists(aaf_dir):
            print(f"AAFs directory created at: {aaf_dir}")
            print("\nStructure:")
            print_tree(aaf_dir, prefix="  ")
        else:
            print("WARNING: AAFs directory was not created!")
        
        print("\n" + "="*70)
        if result == 0:
            print("SUCCESS: Processing completed without errors!")
        else:
            print(f"ERROR: Processing failed with code {result}")
        print("="*70)
        
    finally:
        # Cleanup test directory
        shutil.rmtree(test_dir, ignore_errors=True)
        print(f"\nCleaned up test directory: {test_dir}")

def print_tree(directory: str, prefix: str = "", max_depth: int = 5, current_depth: int = 0):
    """Print directory tree structure."""
    if current_depth >= max_depth:
        return
    
    try:
        entries = sorted(os.listdir(directory))
    except PermissionError:
        return
    
    dirs = [e for e in entries if os.path.isdir(os.path.join(directory, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(directory, e))]
    
    # Print directories
    for i, d in enumerate(dirs):
        is_last = (i == len(dirs) - 1) and len(files) == 0
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{d}/")
        
        next_prefix = prefix + ("    " if is_last else "│   ")
        print_tree(os.path.join(directory, d), next_prefix, max_depth, current_depth + 1)
    
    # Print files
    for i, f in enumerate(files):
        is_last = i == len(files) - 1
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{f}")

if __name__ == "__main__":
    main()
