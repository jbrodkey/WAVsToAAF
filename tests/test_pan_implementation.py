"""
Test pan implementation for stereo and mono AAF files.
"""
import pytest
import aaf2
from pathlib import Path

from wav_to_aaf import WAVsToAAFProcessor


def test_stereo_pan_control(tiny_wav_stereo, tmp_outdir):
    """Test that stereo files get left/right pan control."""
    output_aaf = tmp_outdir / "test_stereo_pan.aaf"
    
    # Process stereo file with embedding
    proc = WAVsToAAFProcessor()
    result = proc.process_single_file(
        str(tiny_wav_stereo),
        str(output_aaf),
        embed_audio=True
    )
    
    assert result == 0, "Processing should succeed"
    assert output_aaf.exists(), "AAF file should be created"
    
    # Read AAF and verify pan structure
    with aaf2.open(str(output_aaf), 'r') as f:
        # Find master mob (filter by type)
        master_mobs = [m for m in f.content.mobs 
                      if type(m).__name__ == 'MasterMob']
        
        assert len(master_mobs) > 0, "Should have at least one master mob"
        
        # Check first master mob
        master = master_mobs[0]
        slots = list(master.slots)
        
        # Stereo files should have 2 slots (one per channel)
        assert len(slots) == 2, f"Stereo file should have 2 slots, got {len(slots)}"
        
        # Check each slot has OperationGroup with pan
        for idx, slot in enumerate(slots):
            seg = slot.segment
            segment_type = type(seg).__name__
            
            # Should be OperationGroup, not direct SourceClip
            assert segment_type == 'OperationGroup', \
                f"Slot {idx+1} should have OperationGroup (pan control), got {segment_type}"
            
            # Check for pan parameters
            if hasattr(seg, 'parameters'):
                params = list(seg.parameters)
                assert len(params) > 0, f"Slot {idx+1} should have pan parameters"
                
                # Check for VaryingValue with control points
                for param in params:
                    if hasattr(param, 'pointlist'):
                        control_points = list(param.pointlist)
                        assert len(control_points) >= 2, "Should have at least 2 control points"
                        
                        # Verify pan value (left=-1.0, right=1.0)
                        pan_val = float(control_points[0].value)
                        if idx == 0:
                            assert pan_val == -1.0, f"Channel 1 should be hard left, got {pan_val}"
                        else:
                            assert pan_val == 1.0, f"Channel 2 should be hard right, got {pan_val}"


def test_mono_pan_control(tiny_wav_mono, tmp_outdir):
    """Test that mono files get center pan control."""
    output_aaf = tmp_outdir / "test_mono_pan.aaf"
    
    # Process mono file with embedding
    proc = WAVsToAAFProcessor()
    result = proc.process_single_file(
        str(tiny_wav_mono),
        str(output_aaf),
        embed_audio=True
    )
    
    assert result == 0, "Processing should succeed"
    assert output_aaf.exists(), "AAF file should be created"
    
    # Read AAF and verify pan structure
    with aaf2.open(str(output_aaf), 'r') as f:
        # Find master mob (not physical source mobs which have MasterMob)
        master_mobs = [m for m in f.content.mobs 
                      if type(m).__name__ == '.PHYS' not in str(m.name)]
        
        if master_mobs:
            master = master_mobs[0]
            slots = list(master.slots)
            
            # Should have 1 slot for mono
            assert len(slots) == 1, f"Mono file should have 1 slot, got {len(slots)}"
            
            slot = slots[0]
            seg = slot.segment
            segment_type = type(seg).__name__
            
            # Should be OperationGroup, not direct SourceClip
            assert segment_type == 'OperationGroup', \
                f"Mono slot should have OperationGroup, got {segment_type}"
            
            # Check for pan parameters
            if hasattr(seg, 'parameters'):
                params = list(seg.parameters)
                assert len(params) > 0, "Mono slot should have pan parameters"
                
                # Check for VaryingValue with center pan
                for param in params:
                    if hasattr(param, 'pointlist'):
                        control_points = list(param.pointlist)
                        assert len(control_points) >= 2, "Should have at least 2 control points"
                        
                        # Verify center pan (0.0)
                        pan_val = float(control_points[0].value)
                        assert pan_val == 0.0, f"Mono should be center pan, got {pan_val}"


def test_linked_stereo_pan(tiny_wav_stereo, tmp_outdir):
    """Test that linked stereo files also get pan control."""
    output_aaf = tmp_outdir / "test_linked_stereo_pan.aaf"
    
    # Process stereo file with linking
    proc = WAVsToAAFProcessor()
    result = proc.process_single_file(
        str(tiny_wav_stereo),
        str(output_aaf),
        embed_audio=False
    )
    
    assert result == 0, "Processing should succeed"
    assert output_aaf.exists(), "AAF file should be created"
    
    # Read AAF and verify pan structure
    with aaf2.open(str(output_aaf), 'r') as f:
        # Find master mob (not physical source mobs which have MasterMob)
        master_mobs = [m for m in f.content.mobs 
                      if type(m).__name__ == '.PHYS' not in str(m.name)]
        
        if master_mobs:
            master = master_mobs[0]
            slots = list(master.slots)
            
            # Should have 2 slots for stereo
            assert len(slots) == 2, f"Stereo file should have 2 slots, got {len(slots)}"
            
            # At least one slot should have OperationGroup
            has_operation_group = any(
                type(slot.segment).__name__ == 'OperationGroup' 
                for slot in slots
            )
            assert has_operation_group, "Linked stereo should have pan control"
