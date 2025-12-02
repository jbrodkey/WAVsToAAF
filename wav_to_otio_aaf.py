#!/usr/bin/env python3
"""
WAV to OTIO Converter for AAF Generation

Creates OpenTimelineIO files from WAV files, then uses Avid's AAFOTIOConverter
to generate Avid-compatible AAF files.

Usage:
    python wav_to_otio_aaf.py input_directory output_directory
"""

import os
import sys
import argparse
from pathlib import Path
import opentimelineio as otio
import wave

def get_wav_duration(wav_path):
    """Get duration of WAV file in seconds."""
    with wave.open(str(wav_path), 'rb') as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        return frames / rate if rate else 0

def create_otio_from_wavs(wav_files, output_otio_path):
    """Create OTIO timeline from list of WAV files."""
    timeline = otio.schema.Timeline(name="WAVs Timeline")

    # Create a track for audio
    track = otio.schema.Track(name="Audio Track", kind="Audio")
    timeline.tracks.append(track)

    for wav_path in wav_files:
        duration = get_wav_duration(wav_path)
        if duration > 0:
            # Create external reference to WAV
            media_ref = otio.schema.ExternalReference(
                target_url=str(wav_path),
                available_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, 1),
                    duration=otio.opentime.RationalTime(duration, 1)
                )
            )

            # Create clip
            clip = otio.schema.Clip(
                name=wav_path.stem,
                media_reference=media_ref,
                source_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, 1),
                    duration=otio.opentime.RationalTime(duration, 1)
                )
            )

            # Add mob_id metadata (required for AAF conversion)
            import uuid
            clip.metadata['mob_id'] = str(uuid.uuid4())

            track.append(clip)

    # Write OTIO file
    otio.adapters.write_to_file(timeline, output_otio_path)
    print(f"Created OTIO file: {output_otio_path}")
    return output_otio_path

def convert_otio_to_aaf(otio_path, aaf_path):
    """Use OTIO AAF adapter to convert OTIO to AAF."""
    try:
        timeline = otio.adapters.read_from_file(otio_path)
        otio.adapters.write_to_file(timeline, aaf_path, adapter_name='AAF')
        print(f"Successfully created AAF: {aaf_path}")
        return True
    except Exception as e:
        print(f"Failed to create AAF: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Convert WAV files to AAF via OTIO")
    parser.add_argument('input_dir', help='Directory containing WAV files')
    parser.add_argument('output_dir', help='Output directory for AAF files')
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all WAV files
    wav_files = list(input_dir.glob('*.wav'))
    if not wav_files:
        print(f"No WAV files found in {input_dir}")
        return

    print(f"Found {len(wav_files)} WAV files")

    # Create OTIO file
    otio_path = output_dir / "wavs_timeline.otio"
    create_otio_from_wavs(wav_files, otio_path)

    # Convert to AAF
    aaf_path = output_dir / "wavs_timeline.aaf"
    convert_otio_to_aaf(otio_path, aaf_path)

if __name__ == "__main__":
    main()