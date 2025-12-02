#!/usr/bin/env python3
"""
test_avid_embedded.py

Creates an AAF mimicking Avid Media Composer's embedded export structure:
- ImportDescriptor SourceMob with locator to original WAV, Timecode slot, A1/A2 SourceClips at 24fps
- Two WAVEDescriptor SourceMobs (one per mono channel), each referencing ImportDescriptor
- MasterMob with 2 slots referencing the per-channel SourceMobs
- All slots at 24fps edit rate (project video rate)

This structure should import cleanly into MC without "video rate" warnings or CM_NO_SOURCE errors.
"""

import aaf2
from pathlib import Path
import wave
import struct
import sys
import os

# Add parent directory to path to import WAVMetadataExtractor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wav_to_aaf import WAVMetadataExtractor

# Configuration
wav_path = Path("/Users/jasonbrodkey/Documents/SFX/Test Source Files/wavTest/RockScrape 6040_75_2.wav")
output_dir = Path("/Users/jasonbrodkey/Documents/SFX/Test Source Files/Generated AAFs")
output_path = output_dir / "test_avid_embedded.aaf"

# Project settings
VIDEO_RATE = 24  # Edit rate for all slots (project timeline rate)
SAMPLE_RATE = 48000

def get_wav_info(path):
    """Extract audio parameters from WAV file."""
    with wave.open(str(path), 'rb') as w:
        return {
            'channels': w.getnchannels(),
            'sample_rate': w.getframerate(),
            'bit_depth': w.getsampwidth() * 8,
            'sample_frames': w.getnframes()
        }

def frames_to_video_ticks(audio_frames, sample_rate, video_rate):
    """Convert audio sample frames to video rate ticks."""
    duration_seconds = audio_frames / sample_rate
    return int(duration_seconds * video_rate)

def create_avid_embedded_aaf(wav_path, output_path):
    """
    Create an Avid-style embedded AAF structure with metadata.
    """
    print(f"Creating Avid-style embedded AAF from: {wav_path}")
    
    # Get audio info
    audio_info = get_wav_info(wav_path)
    print(f"Audio info: {audio_info}")
    
    # Extract metadata from WAV
    extractor = WAVMetadataExtractor()
    bext_metadata = extractor.extract_bext_chunk(str(wav_path))
    info_metadata = extractor.extract_all_metadata_chunks(str(wav_path))
    
    if bext_metadata:
        print(f"Extracted BEXT metadata: {list(bext_metadata.keys())}")
    if info_metadata:
        print(f"Extracted INFO metadata: {list(info_metadata.keys())}")
    
    # Calculate lengths
    audio_frames = audio_info['sample_frames']
    video_length = frames_to_video_ticks(audio_frames, audio_info['sample_rate'], VIDEO_RATE)
    
    print(f"Audio frames: {audio_frames}")
    print(f"Video length (at {VIDEO_RATE}fps): {video_length}")
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create AAF file
    with aaf2.open(output_path, 'w') as f:
        
        # === 1. Create ImportDescriptor SourceMob ===
        # This mob represents the original file with locator
        import_mob = f.create.SourceMob()
        import_mob.name = wav_path.name
        
        # Create ImportDescriptor
        import_desc = f.create.ImportDescriptor()
        
        # Add locator with Macintosh HD prefix (Avid convention on macOS)
        locator_url = f"file:///Macintosh%20HD{wav_path.as_posix()}"
        print(f"Locator URL: {locator_url}")
        
        locator = f.create.NetworkLocator()
        locator['URLString'].value = locator_url
        import_desc.locator.append(locator)
        
        import_mob.descriptor = import_desc
        
        # Add Slot 1 (A1) - SourceClip with nil source (file essence)
        slot1 = import_mob.create_timeline_slot(VIDEO_RATE)
        clip1 = f.create.SourceClip()
        clip1['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
        clip1['Length'].value = video_length
        clip1['StartTime'].value = 0
        # Nil SourceID for file essence (pyaaf2 leaves it null by default)
        slot1.segment = clip1
        slot1.name = wav_path.name
        
        # Add Slot 2 (Timecode)
        slot2 = import_mob.create_timeline_slot(VIDEO_RATE)
        tc = f.create.Timecode(length=video_length)
        tc['Start'].value = 0
        tc['FPS'].value = VIDEO_RATE
        slot2.segment = tc
        
        # Add Slot 3 (A2) - second audio channel
        slot3 = import_mob.create_timeline_slot(VIDEO_RATE)
        clip3 = f.create.SourceClip()
        clip3['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
        clip3['Length'].value = video_length
        clip3['StartTime'].value = 0
        # Nil SourceID for file essence
        slot3.segment = clip3
        slot3.name = wav_path.name
        
        f.content.mobs.append(import_mob)
        print(f"Created ImportDescriptor mob: {import_mob.mob_id}")
        
        # === 2. Create per-channel WAVEDescriptor SourceMobs ===
        channel_mobs = []
        
        for ch_idx in range(2):  # Stereo -> 2 mono mobs
            ch_mob = f.create.SourceMob()
            
            # Create WAVEDescriptor
            wave_desc = f.create.WAVEDescriptor()
            wave_desc['SampleRate'].value = audio_info['sample_rate']
            wave_desc['Length'].value = audio_frames
            
            # Set ContainerFormat to AAF (embedded)
            container_def = f.dictionary.lookup_containerdef('AAF')
            wave_desc['ContainerFormat'].value = container_def
            
            # Create minimal WAVEDescriptor Summary (required property)
            # This is a RIFF WAVE header structure
            summary = bytearray()
            summary.extend(b'RIFF')
            summary.extend(struct.pack('<I', 0))  # Chunk size (placeholder)
            summary.extend(b'WAVE')
            summary.extend(b'fmt ')
            summary.extend(struct.pack('<I', 16))  # fmt chunk size
            summary.extend(struct.pack('<H', 1))   # PCM format
            summary.extend(struct.pack('<H', 1))   # Mono
            summary.extend(struct.pack('<I', audio_info['sample_rate']))
            bytes_per_sec = audio_info['sample_rate'] * (audio_info['bit_depth'] // 8)
            summary.extend(struct.pack('<I', bytes_per_sec))
            summary.extend(struct.pack('<H', audio_info['bit_depth'] // 8))
            summary.extend(struct.pack('<H', audio_info['bit_depth']))
            summary.extend(b'data')
            summary.extend(struct.pack('<I', audio_frames * (audio_info['bit_depth'] // 8)))
            wave_desc['Summary'].value = bytes(summary)
            
            # Optional: Add self-referencing locator (points to output AAF)
            # Avid does this for embedded media
            locator = f.create.NetworkLocator()
            locator['URLString'].value = f"file:///Macintosh%20HD{output_path.as_posix()}"
            wave_desc.locator.append(locator)
            
            ch_mob.descriptor = wave_desc
            
            # Create slot referencing ImportDescriptor mob
            # Slot 1 references ImportDescriptor slot 1 (ch 0) or slot 3 (ch 1)
            import_slot_id = 1 if ch_idx == 0 else 3
            
            slot = ch_mob.create_timeline_slot(VIDEO_RATE)
            clip = f.create.SourceClip()
            clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
            clip['Length'].value = video_length
            clip['StartTime'].value = 0
            clip['SourceID'].value = import_mob.mob_id
            clip['SourceMobSlotID'].value = import_slot_id
            slot.segment = clip
            
            f.content.mobs.append(ch_mob)
            channel_mobs.append(ch_mob)
            print(f"Created WAVEDescriptor mob (ch{ch_idx+1}): {ch_mob.mob_id}")
        
        # === 3. Create MasterMob ===
        master_mob = f.create.MasterMob()
        master_mob.name = wav_path.stem  # Just the base filename, no .Exported.01 suffix
        
        # Add 2 slots, each referencing one channel mob
        for ch_idx, ch_mob in enumerate(channel_mobs):
            slot = master_mob.create_timeline_slot(VIDEO_RATE)
            clip = f.create.SourceClip()
            clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
            clip['Length'].value = video_length
            clip['StartTime'].value = 0
            clip['SourceID'].value = ch_mob.mob_id
            clip['SourceMobSlotID'].value = 1
            slot.segment = clip
            slot.name = wav_path.name
        
        # === 4. Add metadata to MasterMob ===
        # Add BEXT metadata as comments
        if bext_metadata:
            if bext_metadata.get('description'):
                master_mob.comments['BEXT_Description'] = bext_metadata['description']
            if bext_metadata.get('originator'):
                master_mob.comments['BEXT_Originator'] = bext_metadata['originator']
            if bext_metadata.get('originator_reference'):
                master_mob.comments['BEXT_Originator_Reference'] = bext_metadata['originator_reference']
            if bext_metadata.get('origination_date'):
                master_mob.comments['BEXT_Origination_Date'] = bext_metadata['origination_date']
            if bext_metadata.get('origination_time'):
                master_mob.comments['BEXT_Origination_Time'] = bext_metadata['origination_time']
            if bext_metadata.get('time_reference'):
                master_mob.comments['BEXT_Time_Reference'] = str(bext_metadata['time_reference'])
            if bext_metadata.get('umid'):
                master_mob.comments['BEXT_UMID'] = bext_metadata['umid']
            print(f"Added BEXT metadata to MasterMob")
        
        # Add INFO metadata as comments
        if info_metadata:
            info_mappings = {
                'IART': 'INFO_Artist',
                'ICMT': 'INFO_Comment',
                'ICOP': 'INFO_Copyright',
                'ICRD': 'INFO_Creation_Date',
                'IENG': 'INFO_Engineer',
                'IGNR': 'INFO_Genre',
                'IKEY': 'INFO_Keywords',
                'INAM': 'INFO_Title',
                'IPRD': 'INFO_Product',
                'ISBJ': 'INFO_Subject',
                'ISFT': 'INFO_Software',
                'ISRC': 'INFO_Source'
            }
            
            for chunk_id, value in info_metadata.items():
                if value:
                    comment_key = info_mappings.get(chunk_id, f'INFO_{chunk_id}')
                    master_mob.comments[comment_key] = str(value)
            print(f"Added INFO metadata to MasterMob")
        
        f.content.mobs.append(master_mob)
        print(f"Created MasterMob: {master_mob.mob_id}")
        
    print(f"\nAAF created successfully: {output_path}")
    print(f"Structure: MasterMob -> 2x WAVEDescriptor SourceMobs -> ImportDescriptor SourceMob -> file")
    print(f"All slots at {VIDEO_RATE}fps edit rate")
    print(f"Metadata attached: BEXT={bool(bext_metadata)}, INFO={bool(info_metadata)}")

if __name__ == '__main__':
    create_avid_embedded_aaf(wav_path, output_path)
