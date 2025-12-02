#!/usr/bin/env python3
"""
Analyze AAF structure to understand Media Composer requirements
"""

import aaf2
import sys

def analyze_aaf(aaf_path):
    """Analyze and print AAF structure"""
    
    print(f"\n{'='*80}")
    print(f"Analyzing: {aaf_path}")
    print(f"{'='*80}\n")
    
    with aaf2.open(aaf_path, 'r') as f:
        print("=== Content Info ===")
        print(f"Operational Pattern: {f.content.get('OperationalPattern', 'Not set')}")
        print(f"Number of mobs: {len(f.content.mobs)}")
        
        print("\n=== Mobs ===")
        for i, mob in enumerate(f.content.mobs):
            mob_type = type(mob).__name__
            print(f"\n[{i}] {mob_type}: {mob.name}")
            print(f"    Mob ID: {mob.mob_id}")
            print(f"    Number of slots: {len(list(mob.slots))}")
            
            # Print descriptor info if it's a SourceMob
            if hasattr(mob, 'descriptor') and mob.descriptor:
                desc = mob.descriptor
                desc_type = type(desc).__name__
                print(f"    Descriptor: {desc_type}")
                
                # Print key descriptor properties
                if hasattr(desc, 'sample_rate'):
                    print(f"        Sample Rate: {desc.sample_rate}")
                if hasattr(desc, 'length'):
                    print(f"        Length: {desc.length}")
                    
                # Check for locators
                if 'Locator' in desc:
                    locators = desc['Locator']
                    print(f"        Locators: {len(locators)}")
                    for loc in locators:
                        loc_type = type(loc).__name__
                        if hasattr(loc, 'url_string'):
                            print(f"            {loc_type}: {loc.url_string}")
                        elif 'URLString' in loc:
                            print(f"            {loc_type}: {loc['URLString'].value}")
                
                # Print other descriptor properties
                for key in desc.keys():
                    if key not in ['Locator', 'SampleRate', 'Length']:
                        try:
                            val = desc[key].value
                            print(f"        {key}: {val}")
                        except:
                            pass
            
            # Print slot info
            for slot in mob.slots:
                slot_id = slot.slot_id
                slot_name = slot.name if hasattr(slot, 'name') else 'Unnamed'
                edit_rate = slot.edit_rate if hasattr(slot, 'edit_rate') else 'Not set'
                print(f"\n    Slot {slot_id}: {slot_name}")
                print(f"        Edit Rate: {edit_rate}")
                
                if slot.segment:
                    seg = slot.segment
                    seg_type = type(seg).__name__
                    print(f"        Segment: {seg_type}")
                    
                    # Print segment properties
                    if 'Length' in seg:
                        print(f"            Length: {seg['Length'].value}")
                    if 'StartTime' in seg:
                        print(f"            StartTime: {seg['StartTime'].value}")
                    if 'DataDefinition' in seg:
                        data_def = seg['DataDefinition'].value
                        print(f"            DataDefinition: {data_def}")
                    
                    # If it's a SourceClip, print source reference
                    if seg_type == 'SourceClip':
                        if 'SourceID' in seg:
                            src_id = seg['SourceID'].value
                            print(f"            SourceID: {src_id}")
                        if 'SourceMobSlotID' in seg:
                            src_slot = seg['SourceMobSlotID'].value
                            print(f"            SourceMobSlotID: {src_slot}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_aaf.py <file.aaf>")
        sys.exit(1)
    
    for aaf_file in sys.argv[1:]:
        try:
            analyze_aaf(aaf_file)
        except Exception as e:
            print(f"Error analyzing {aaf_file}: {e}")
            import traceback
            traceback.print_exc()
