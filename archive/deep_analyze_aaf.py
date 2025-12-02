#!/usr/bin/env python3
"""
Deep analysis of AAF content properties
"""

import aaf2
import sys

def deep_analyze_aaf(aaf_path):
    """Analyze AAF content properties and metadata"""
    
    print(f"\n{'='*80}")
    print(f"Deep Analysis: {aaf_path}")
    print(f"{'='*80}\n")
    
    with aaf2.open(aaf_path, 'r') as f:
        print("=== Content Properties ===")
        for key in f.content.keys():
            try:
                val = f.content[key].value
                print(f"{key}: {val}")
            except:
                try:
                    val = f.content[key]
                    print(f"{key}: {val}")
                except:
                    print(f"{key}: <unable to read>")
        
        print("\n=== Header Properties ===")
        if hasattr(f, 'header'):
            for key in f.header.keys():
                try:
                    val = f.header[key].value
                    print(f"{key}: {val}")
                except:
                    try:
                        val = f.header[key]
                        print(f"{key}: {val}")
                    except:
                        print(f"{key}: <unable to read>")
        
        print("\n=== Composition Info ===")
        # Check if there's a composition mob
        for mob in f.content.mobs:
            if type(mob).__name__ == 'CompositionMob':
                print(f"Found CompositionMob: {mob.name}")
                print(f"  Slots: {len(list(mob.slots))}")
                for slot in mob.slots:
                    print(f"    Slot {slot.slot_id}: {slot.name}, EditRate: {slot.edit_rate}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deep_analyze_aaf.py <file.aaf>")
        sys.exit(1)
    
    for aaf_file in sys.argv[1:]:
        try:
            deep_analyze_aaf(aaf_file)
        except Exception as e:
            print(f"Error analyzing {aaf_file}: {e}")
            import traceback
            traceback.print_exc()
