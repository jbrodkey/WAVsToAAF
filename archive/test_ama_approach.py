#!/usr/bin/env python3
"""
Test script to create AAF files using pyaaf2's AMA functionality
This should be more compatible with Media Composer
"""

import aaf2
import os
import wave
import sys
from pathlib import Path

def create_ama_aaf(wav_path, output_aaf):
    """Create AAF using pyaaf2's native AMA functionality with fixes"""
    
    def probe_wav(path):
        """Create metadata structure for AMA"""
        try:
            with wave.open(path, 'rb') as w:
                return {
                    'format': {
                        'filename': path,
                        'format_name': 'wav',
                        'duration': str(w.getnframes() / w.getframerate())
                    },
                    'streams': [{
                        'codec_type': 'audio',
                        'channels': w.getnchannels(),
                        'sample_rate': str(w.getframerate()),
                        'duration_ts': w.getnframes(),
                        'codec_name': 'pcm_s16le'
                    }]
                }
        except Exception as e:
            print(f"Error probing WAV: {e}")
            return None
    
    # Create metadata
    metadata = probe_wav(wav_path)
    if not metadata:
        print(f"Failed to probe {wav_path}")
        return False
    
    try:
        with aaf2.open(output_aaf, 'w') as f:
            # Create AMA link
            mobs = f.content.create_ama_link(wav_path, metadata)
            
            if not mobs or len(mobs) < 1:
                print("Failed to create AMA link")
                return False
            
            # Get master mob and update name
            master_mob = mobs[0]
            filename = Path(wav_path).stem
            master_mob.name = filename
            
            # Fix critical issues for Media Composer compatibility
            audio_length = int(metadata['streams'][0]['duration_ts'])
            
            # Fix all mobs
            for mob in mobs:
                for slot in mob.slots:
                    # Fix slot names (Media Composer needs named slots)
                    if not slot.name or slot.name.strip() == "":
                        if slot.media_kind == 'Sound':
                            slot.name = f"Audio {slot.slot_id}"
                    
                    # Fix sequence lengths
                    if hasattr(slot, 'segment') and slot.segment:
                        seg = slot.segment
                        if hasattr(seg, 'length'):
                            seg.length = audio_length
                        if 'Length' in seg:
                            seg['Length'].value = audio_length
                        
                        # Fix component lengths
                        if hasattr(seg, 'components') and seg.components:
                            for comp in seg.components:
                                if 'Length' in comp:
                                    comp['Length'].value = audio_length
            
            # Add some basic metadata
            master_mob.comments['Source_File'] = wav_path
            master_mob.comments['Created_By'] = 'WAVsToAAF_AMA_Fixed'
            master_mob.comments['Audio_Length'] = str(audio_length)
            
            print(f"✅ Created fixed AAF with {len(mobs)} mobs")
            for i, mob in enumerate(mobs):
                print(f"   Mob {i+1}: {type(mob).__name__} - {mob.name}")
                for slot in mob.slots:
                    print(f"     Slot {slot.slot_id}: '{slot.name}' ({slot.media_kind}) - Length: {slot.segment.length if hasattr(slot.segment, 'length') else 'N/A'}")
            
            return True
            
    except Exception as e:
        print(f"Error creating AAF: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_ama_approach.py <input.wav> <output.aaf>")
        sys.exit(1)
    
    wav_file = sys.argv[1]
    aaf_file = sys.argv[2]
    
    if not os.path.exists(wav_file):
        print(f"WAV file not found: {wav_file}")
        sys.exit(1)
    
    success = create_ama_aaf(wav_file, aaf_file)
    if success:
        print(f"Successfully created: {aaf_file}")
    else:
        print("Failed to create AAF")
        sys.exit(1)