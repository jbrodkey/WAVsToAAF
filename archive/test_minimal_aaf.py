#!/usr/bin/env python3
"""
Minimal AAF creation for Media Composer compatibility
Based on working AAF examples and Media Composer requirements
"""

import aaf2
import os
import wave
import sys
from pathlib import Path

def create_minimal_aaf(wav_path, output_aaf):
    """Create minimal AAF structure that Media Composer can import"""
    
    try:
        # Get WAV info
        with wave.open(wav_path, 'rb') as w:
            channels = w.getnchannels()
            sample_rate = w.getframerate()
            frames = w.getnframes()
            sample_width = w.getsampwidth()
        
        filename = Path(wav_path).stem
        
        with aaf2.open(output_aaf, 'w') as f:
            # Create master mob (simplest possible structure)
            master_mob = f.create.MasterMob(filename)
            
            # Create source mob
            source_mob = f.create.SourceMob()
            source_mob.name = f"{filename}_Source"
            
            # Create WAVE descriptor
            wave_descriptor = f.create.WAVEDescriptor()
            wave_descriptor['SampleRate'].value = sample_rate
            wave_descriptor['Length'].value = frames
            wave_descriptor['ContainerFormat'].value = f.dictionary.lookup_containerdef("AAF")
            
            # Add NetworkLocator
            locator = f.create.NetworkLocator()
            abs_path = os.path.abspath(wav_path)
            file_url = Path(abs_path).as_uri()
            locator['URLString'].value = file_url
            wave_descriptor['Locator'].append(locator)
            
            # Create minimal WAV summary
            import struct
            fmt_data = struct.pack('<HHIIHH', 
                                 1,  # format tag (PCM)
                                 channels,  # channels
                                 sample_rate,  # sample rate
                                 sample_rate * channels * sample_width,  # byte rate
                                 channels * sample_width,  # block align
                                 sample_width * 8)  # bits per sample
            wave_descriptor['Summary'].value = fmt_data
            
            # Set descriptor on source mob
            source_mob.descriptor = wave_descriptor
            
            # Create ONE audio slot for source mob (mono approach)
            source_slot = source_mob.create_timeline_slot(sample_rate)
            source_slot.name = "Audio"
            
            # Create source clip for source slot (references file essence)
            source_source_clip = f.create.SourceClip()
            source_source_clip['DataDefinition'].value = f.dictionary.lookup_datadef("sound")
            source_source_clip['Length'].value = frames
            source_source_clip['StartTime'].value = 0
            # For file essence, leave SourceID as null
            source_slot.segment = source_source_clip
            
            # Create ONE audio slot for master mob (mono approach)
            master_slot = master_mob.create_timeline_slot(sample_rate)
            master_slot.name = "Audio"
            
            # Create source clip that references the source mob
            master_source_clip = f.create.SourceClip()
            master_source_clip['DataDefinition'].value = f.dictionary.lookup_datadef("sound")
            master_source_clip['Length'].value = frames
            master_source_clip['StartTime'].value = 0
            master_source_clip['SourceID'].value = source_mob.mob_id
            master_source_clip['SourceMobSlotID'].value = source_slot.slot_id
            master_slot.segment = master_source_clip
            
            # Add mobs to content
            f.content.mobs.append(master_mob)
            f.content.mobs.append(source_mob)
            
            print(f"✅ Created minimal AAF with 2 mobs")
            print(f"   MasterMob: {master_mob.name} (1 slot)")
            print(f"   SourceMob: {source_mob.name} (1 slot)")
            print(f"   Audio length: {frames} frames")
            
            return True
            
    except Exception as e:
        print(f"Error creating minimal AAF: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_minimal_aaf.py <input.wav> <output.aaf>")
        sys.exit(1)
    
    wav_file = sys.argv[1]
    aaf_file = sys.argv[2]
    
    if not os.path.exists(wav_file):
        print(f"WAV file not found: {wav_file}")
        sys.exit(1)
    
    success = create_minimal_aaf(wav_file, aaf_file)
    if success:
        print(f"Successfully created: {aaf_file}")
    else:
        print("Failed to create AAF")
        sys.exit(1)