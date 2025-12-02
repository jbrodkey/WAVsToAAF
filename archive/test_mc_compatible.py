#!/usr/bin/env python3
"""
Media Composer compatible AAF creation
Focuses on proper media linking to avoid CM_NO_SOURCE errors
"""

import aaf2
import os
import wave
import sys
from pathlib import Path

def create_mc_compatible_aaf(wav_path, output_aaf):
    """Create AAF structure specifically for Media Composer compatibility"""
    
    try:
        # Get WAV info
        with wave.open(wav_path, 'rb') as w:
            channels = w.getnchannels()
            sample_rate = w.getframerate()
            frames = w.getnframes()
            sample_width = w.getsampwidth()
        
        filename = Path(wav_path).stem
        
        with aaf2.open(output_aaf, 'w') as f:
            # Create TapeMob first (lowest level - represents physical media)
            tape_mob = f.create.SourceMob()
            tape_mob.name = f"{filename}_Tape"
            
            # Create WAV descriptor for tape mob
            wave_descriptor = f.create.WAVEDescriptor()
            wave_descriptor['SampleRate'].value = sample_rate
            wave_descriptor['Length'].value = frames
            wave_descriptor['ContainerFormat'].value = f.dictionary.lookup_containerdef("AAF")
            
            # Create absolute path locator for Media Composer
            locator = f.create.NetworkLocator()
            # Use absolute path with file:// protocol
            abs_path = os.path.abspath(wav_path)
            file_url = f"file://{abs_path}"
            locator['URLString'].value = file_url
            wave_descriptor['Locator'].append(locator)
            
            # Create proper WAV summary
            import struct
            fmt_data = struct.pack('<HHIIHH', 
                                 1,  # format tag (PCM)
                                 channels,  # channels
                                 sample_rate,  # sample rate
                                 sample_rate * channels * sample_width,  # byte rate
                                 channels * sample_width,  # block align
                                 sample_width * 8)  # bits per sample
            wave_descriptor['Summary'].value = fmt_data
            
            tape_mob.descriptor = wave_descriptor
            
            # Create audio slot for tape mob with explicit edit rate
            tape_slot = tape_mob.create_timeline_slot(sample_rate)
            tape_slot.name = "A1"  # Standard audio track name
            tape_slot.edit_rate = sample_rate

            # Create source clip for tape (references file essence)
            tape_source_clip = f.create.SourceClip()
            tape_source_clip['DataDefinition'].value = f.dictionary.lookup_datadef("sound")
            tape_source_clip['Length'].value = frames
            tape_source_clip['StartTime'].value = 0
            tape_source_clip['SourceID'].value = tape_mob.mob_id  # Self-reference for file essence
            tape_source_clip['SourceMobSlotID'].value = tape_slot.slot_id
            tape_slot.segment = tape_source_clip

            # Add a Timecode slot to TapeMob (Media Composer expects this)
            tc_slot = tape_mob.create_timeline_slot(sample_rate)
            tc_slot.name = "TC1"
            tc_slot.edit_rate = sample_rate
            timecode = f.create.Timecode()
            timecode['Start'].value = 0
            timecode['Length'].value = frames
            tc_slot.segment = timecode
            
            # Create SourceMob (middle level)
            source_mob = f.create.SourceMob()
            source_mob.name = f"{filename}_Source"
            
            # Source mob gets physical descriptor (no file locator)
            source_descriptor = f.create.SoundDescriptor()
            source_descriptor['SampleRate'].value = sample_rate
            source_descriptor['Length'].value = frames
            source_descriptor['AudioSamplingRate'].value = sample_rate
            source_descriptor['Channels'].value = channels
            source_descriptor['QuantizationBits'].value = sample_width * 8
            source_mob.descriptor = source_descriptor
            
            # Create audio slot for source mob with explicit edit rate
            source_slot = source_mob.create_timeline_slot(sample_rate)
            source_slot.name = "A1"
            source_slot.edit_rate = sample_rate

            # Source clip that references tape mob
            source_source_clip = f.create.SourceClip()
            source_source_clip['DataDefinition'].value = f.dictionary.lookup_datadef("sound")
            source_source_clip['Length'].value = frames
            source_source_clip['StartTime'].value = 0
            source_source_clip['SourceID'].value = tape_mob.mob_id
            source_source_clip['SourceMobSlotID'].value = tape_slot.slot_id
            source_slot.segment = source_source_clip
            
            # Create MasterMob (top level)
            master_mob = f.create.MasterMob(filename)
            
            # Create audio slot for master mob with explicit edit rate
            master_slot = master_mob.create_timeline_slot(sample_rate)
            master_slot.name = "A1"
            master_slot.edit_rate = sample_rate

            # Source clip that references source mob
            master_source_clip = f.create.SourceClip()
            master_source_clip['DataDefinition'].value = f.dictionary.lookup_datadef("sound")
            master_source_clip['Length'].value = frames
            master_source_clip['StartTime'].value = 0
            master_source_clip['SourceID'].value = source_mob.mob_id
            master_source_clip['SourceMobSlotID'].value = source_slot.slot_id
            master_slot.segment = master_source_clip
            
            # Add mobs to content in order
            f.content.mobs.append(tape_mob)
            f.content.mobs.append(source_mob)
            f.content.mobs.append(master_mob)
            
            print(f"✅ Created Media Composer compatible AAF with 3 mobs")
            print(f"   MasterMob: {master_mob.name}")
            print(f"   SourceMob: {source_mob.name}")
            print(f"   TapeMob: {tape_mob.name}")
            print(f"   Audio length: {frames} frames")
            print(f"   Locator: {file_url}")
            
            return True
            
    except Exception as e:
        print(f"Error creating MC compatible AAF: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_mc_compatible.py <input.wav> <output.aaf>")
        sys.exit(1)
    
    wav_file = sys.argv[1]
    aaf_file = sys.argv[2]
    
    if not os.path.exists(wav_file):
        print(f"WAV file not found: {wav_file}")
        sys.exit(1)
    
    success = create_mc_compatible_aaf(wav_file, aaf_file)
    if success:
        print(f"Successfully created: {aaf_file}")
    else:
        print("Failed to create AAF")
        sys.exit(1)