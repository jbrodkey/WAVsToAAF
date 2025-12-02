#!/usr/bin/env python3
"""Quick script to inspect AAF metadata fields"""

import aaf2

aaf_path = "/Users/jasonbrodkey/Documents/SFX/Test Source Files/Generated AAFs/test_avid_embedded.aaf"

with aaf2.open(aaf_path, 'r') as f:
    print("=== AAF Metadata Inspector ===\n")
    
    for mob in f.content.mobs:
        if isinstance(mob, aaf2.mobs.MasterMob):
            print(f"MasterMob: {mob.name}")
            print(f"MobID: {mob.mob_id}")
            
            # Get all comments using helper's items() API
            comment_dict = {}
            try:
                items = mob.comments.items()
                for k, v in items:
                    comment_dict[str(k)] = str(v)
            except Exception as e:
                print(f"  Warning: could not read comments via items(): {e}")
                # Fallback: try get common keys if any were set
                for k in ['Name','Filename','FilePath','SampleRate','BitDepth','Channels','Number of Frames',
                          'AudioFormat','Tracks','Duration','Start','End','Tape','Description','Keywords',
                          'Originator','OriginatorReference','Origination Date','Origination Time','Category',
                          'SubCategory','UCS ID','StartTC_24fps']:
                    try:
                        val = mob.comments.get(k)
                        if val is not None:
                            comment_dict[k] = str(val)
                    except Exception:
                        pass
            
            print(f"\nMetadata Fields ({len(comment_dict)} total):")
            print("-" * 80)
            
            # Sort fields for easier reading
            sorted_fields = sorted(comment_dict.items())
            
            for key, value in sorted_fields:
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 60:
                    value_str = value_str[:57] + "..."
                print(f"  {key:30} = {value_str}")
            
            print("\n" + "=" * 80)
            print("\nField Categories:")
            
            # Categorize fields
            bext_fields = [k for k in comment_dict.keys() if k.startswith('BEXT_')]
            info_fields = [k for k in comment_dict.keys() if k.startswith('INFO_')]
            ucs_fields = [k for k in comment_dict.keys() if k.startswith('UCS_')]
            ale_fields = [k for k in comment_dict.keys() if k in [
                'Name', 'Filename', 'FilePath', 'Start', 'End', 'Tracks', 'AudioFormat',
                'SampleRate', 'BitDepth', 'Channels', 'Duration', 'Number of Frames',
                'Tape', 'Description', 'Keywords', 'Originator', 'OriginatorReference',
                'Origination Date', 'Origination Time', 'Category', 'SubCategory', 'UCS ID',
                'StartTC_24fps'
            ]]
            
            print(f"\n  BEXT fields: {len(bext_fields)}")
            print(f"    {', '.join(bext_fields[:5])}{'...' if len(bext_fields) > 5 else ''}")
            
            print(f"\n  INFO fields: {len(info_fields)}")
            print(f"    {', '.join(info_fields[:5])}{'...' if len(info_fields) > 5 else ''}")
            
            print(f"\n  UCS fields: {len(ucs_fields)}")
            print(f"    {', '.join(ucs_fields)}")
            
            print(f"\n  ALE-style fields: {len(ale_fields)}")
            for field in ale_fields:
                value = comment_dict.get(field, '')
                value_str = str(value)[:40]
                print(f"    {field:25} = {value_str}")
            
            break
