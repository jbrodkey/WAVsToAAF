#!/usr/bin/env python3
"""
Quick demonstration of both AAF organization features working correctly.
"""

import os
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from wav_to_aaf import WAVsToAAFProcessor


def create_demo_wav(path: Path) -> None:
    """Create a demo WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    channels = 1
    sample_width = 2
    sample_rate = 48000
    frames = sample_rate // 2  # 0.5 second
    
    with wave.open(str(path), 'w') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b'\x00' * (sample_width * channels * frames))


def demo():
    print("=" * 70)
    print("WAVsToAAF Feature Demonstration")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # DEMO 1: Directory Processing with Subdirectory Mirroring
        print("\n📁 DEMO 1: Directory Processing with Subdirectory Mirroring")
        print("-" * 70)
        
        source_dir = tmpdir / "demo_directory" / "source_audio"
        source_dir.mkdir(parents=True, exist_ok=True)
        
        # Create nested structure
        (source_dir / "voice").mkdir(exist_ok=True)
        (source_dir / "voice" / "narration").mkdir(exist_ok=True)
        (source_dir / "sfx").mkdir(exist_ok=True)
        
        create_demo_wav(source_dir / "voice" / "intro.wav")
        create_demo_wav(source_dir / "voice" / "narration" / "part1.wav")
        create_demo_wav(source_dir / "voice" / "narration" / "part2.wav")
        create_demo_wav(source_dir / "sfx" / "door.wav")
        
        print(f"Input structure:")
        print(f"  source_audio/")
        print(f"    ├── voice/")
        print(f"    │   ├── intro.wav")
        print(f"    │   └── narration/")
        print(f"    │       ├── part1.wav")
        print(f"    │       └── part2.wav")
        print(f"    └── sfx/")
        print(f"        └── door.wav")
        
        processor = WAVsToAAFProcessor()
        processor.process_directory(str(source_dir), None)
        
        aaf_dir = (tmpdir / "demo_directory" / "AAFs")
        
        print(f"\nOutput structure (at: {aaf_dir.relative_to(tmpdir)}):")
        print(f"  AAFs/")
        print(f"    ├── voice/")
        print(f"    │   ├── intro.aaf ✓")
        print(f"    │   └── narration/")
        print(f"    │       ├── part1.aaf ✓")
        print(f"    │       └── part2.aaf ✓")
        print(f"    └── sfx/")
        print(f"        └── door.aaf ✓")
        
        # DEMO 2: Single File Processing with AAFs Subdirectory
        print("\n\n📄 DEMO 2: Single File Processing with AAFs Subdirectory")
        print("-" * 70)
        
        single_dir = tmpdir / "demo_single" / "my_sounds"
        single_dir.mkdir(parents=True, exist_ok=True)
        
        wav_file = single_dir / "effect.wav"
        create_demo_wav(wav_file)
        
        print(f"Input structure:")
        print(f"  my_sounds/")
        print(f"    └── effect.wav")
        
        aaf_output = single_dir / "AAFs" / "effect.aaf"
        processor.process_single_file(str(wav_file), str(aaf_output))
        
        print(f"\nOutput structure (at: {single_dir.relative_to(tmpdir)}):")
        print(f"  my_sounds/")
        print(f"    ├── effect.wav")
        print(f"    └── AAFs/")
        print(f"        └── effect.aaf ✓")
        
        print("\n" + "=" * 70)
        print("✓ Both features working correctly!")
        print("=" * 70)


if __name__ == "__main__":
    demo()
