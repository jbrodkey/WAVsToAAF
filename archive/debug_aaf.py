#!/usr/bin/env python3
"""Debug AAF structure"""

import aaf2

aaf_path = "/Users/jasonbrodkey/Documents/SFX/Test Source Files/Generated AAFs/test_avid_embedded.aaf"

with aaf2.open(aaf_path, 'r') as f:
    print("=== AAF Structure Debug ===\n")
    
    for mob in f.content.mobs:
        print(f"{mob.__class__.__name__}: {mob.name}")
        print(f"  MobID: {mob.mob_id}")
        print(f"  Type: {type(mob)}")
        print(f"  Has comments attr: {hasattr(mob, 'comments')}")
        
        if hasattr(mob, 'comments'):
            print(f"  Comments type: {type(mob.comments)}")
            print(f"  Comments dir: {[x for x in dir(mob.comments) if not x.startswith('_')]}")
            
            # Try different ways to access
            try:
                print(f"  Try iteration:")
                count = 0
                for item in mob.comments:
                    print(f"    Item {count}: {type(item)} - {item}")
                    count += 1
                    if count > 5:
                        print("    ...")
                        break
            except Exception as e:
                print(f"    Error iterating: {e}")
            
            # Try getting property
            try:
                if hasattr(mob, 'Attributes'):
                    print(f"  Attributes: {mob['Attributes']}")
            except Exception as e:
                print(f"  No Attributes: {e}")
                
        print()
