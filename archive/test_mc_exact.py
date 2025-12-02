#!/usr/bin/env python3
"""
Create AAF matching Media Composer's exact structure
Based on analysis of known-good MC AAFs
"""

import aaf2
import os
import wave
import sys
from pathlib import Path

def create_mc_exact_aaf(wav_path, output_aaf):
    """Create AAF structure exactly matching Media Composer exports"""
    
    try:
        # Get WAV info
        with wave.open(wav_path, 'rb') as w:
            channels = w.getnchannels()
            sample_rate = w.getframerate()
            frames = w.getnframes()
            sample_width = w.getsampwidth()
        
        filename = Path(wav_path).stem
        
        with aaf2.open(output_aaf, 'w') as f:
            # Create one SourceMob per channel (MC pattern)
            source_mobs = []
            for ch in range(channels):
                source_mob = f.create.SourceMob()
                source_mob.name = None  # MC leaves SourceMob names as None
                
                # Create PCMDescriptor (not WAVEDescriptor or SoundDescriptor!)
                pcm_descriptor = f.create.PCMDescriptor()
                pcm_descriptor['SampleRate'].value = sample_rate
                pcm_descriptor['Length'].value = frames
                pcm_descriptor['AudioSamplingRate'].value = sample_rate
                pcm_descriptor['Channels'].value = 1  # 1 channel per SourceMob
                pcm_descriptor['QuantizationBits'].value = sample_width * 8
                pcm_descriptor['BlockAlign'].value = sample_width
                pcm_descriptor['AverageBPS'].value = sample_rate * sample_width
                pcm_descriptor['ContainerFormat'].value = f.dictionary.lookup_containerdef("AAF")
                
                # Add CodecDefinition (critical for MC!)
                try:
                    codec = f.dictionary.lookup_codecdef("PCM")
                    pcm_descriptor['CodecDefinition'].value = codec
                except:
                    pass  # If codec lookup fails, continue without it
                
                # Add NetworkLocators in multiple formats for compatibility
                abs_path = os.path.abspath(wav_path)

                # 1) Properly encoded file URI (preferred)
                locator1 = f.create.NetworkLocator()
                file_url_encoded = Path(abs_path).as_uri()
                locator1['URLString'].value = file_url_encoded
                pcm_descriptor['Locator'].append(locator1)

                # 2) file://localhost absolute path (legacy macOS style)
                locator2 = f.create.NetworkLocator()
                locator2['URLString'].value = f"file://localhost{abs_path}"
                pcm_descriptor['Locator'].append(locator2)

                # 3) Plain absolute POSIX path (some tools accept this)
                locator3 = f.create.NetworkLocator()
                locator3['URLString'].value = abs_path
                pcm_descriptor['Locator'].append(locator3)

                # 4) Filename only (MC may search current folder)
                locator4 = f.create.NetworkLocator()
                locator4['URLString'].value = Path(abs_path).name
                pcm_descriptor['Locator'].append(locator4)
                
                source_mob.descriptor = pcm_descriptor
                
                # Create audio slot
                source_slot = source_mob.create_timeline_slot(sample_rate)
                source_slot.name = "Test"  # MC uses "Test" for SourceMob slots
                source_slot.edit_rate = sample_rate
                
                # Create source clip referencing file essence
                # CRITICAL: SourceMobSlotID must be 0 for file essence (not 1!)
                source_clip = f.create.SourceClip()
                source_clip['DataDefinition'].value = f.dictionary.lookup_datadef("sound")
                source_clip['Length'].value = frames
                source_clip['StartTime'].value = 0
                # Null SourceID for file essence
                source_slot.segment = source_clip
                
                source_mobs.append((source_mob, source_slot))
            
            # Create MasterMob with one slot per channel
            master_mob = f.create.MasterMob(filename)
            
            for ch, (source_mob, source_slot) in enumerate(source_mobs):
                master_slot = master_mob.create_timeline_slot(sample_rate)
                master_slot.name = "Audio Slot"  # MC uses "Audio Slot" for MasterMob
                master_slot.edit_rate = sample_rate
                
                # Source clip referencing the source mob
                master_clip = f.create.SourceClip()
                master_clip['DataDefinition'].value = f.dictionary.lookup_datadef("sound")
                master_clip['Length'].value = frames
                master_clip['StartTime'].value = 0
                master_clip['SourceID'].value = source_mob.mob_id
                master_clip['SourceMobSlotID'].value = source_slot.slot_id
                master_slot.segment = master_clip
            
            # Add mobs to content (MC order: MasterMob first, then SourceMobs)
            f.content.mobs.append(master_mob)
            for source_mob, _ in source_mobs:
                f.content.mobs.append(source_mob)
            
            print(f"✅ Created MC-exact AAF structure")
            print(f"   MasterMob: {master_mob.name} ({channels} slots)")
            print(f"   SourceMobs: {len(source_mobs)} (1 per channel)")
            print(f"   Descriptor: PCMDescriptor with CodecDefinition")
            print(f"   Audio length: {frames} frames")
            print(f"   Locators added:")
            print(f"     - {file_url_encoded}")
            print(f"     - file://localhost{abs_path}")
            print(f"     - {abs_path}")
            print(f"     - {Path(abs_path).name}")
            
            return True
            
    except Exception as e:
        print(f"Error creating MC-exact AAF: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_mc_exact.py <input.wav> <output.aaf>")
        sys.exit(1)
    
    wav_file = sys.argv[1]
    aaf_file = sys.argv[2]
    
    if not os.path.exists(wav_file):
        print(f"WAV file not found: {wav_file}")
        sys.exit(1)
    
    success = create_mc_exact_aaf(wav_file, aaf_file)
    if success:
        print(f"Successfully created: {aaf_file}")
    else:
        print("Failed to create AAF")
        sys.exit(1)
