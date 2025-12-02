#!/usr/bin/env python3
import aaf2, glob
for f in glob.glob('embedded_test_aafs/*.aaf'):
    print('---', f)
    with aaf2.open(f,'r') as file:
        ed=list(file.content.essencedata)
        print('essencedata count:',len(ed))
        for mob in file.content.mobs:
            try:
                desc = mob.descriptor
            except Exception:
                desc = None
            ch = None
            length = None
            tname = None
            if desc is not None:
                tname = type(desc).__name__
                try:
                    ch = desc['Channels'].value
                except Exception:
                    ch = None
                try:
                    length = desc['length']
                except Exception:
                    length = None
            print(' mob',mob.name, tname, 'Channels->', ch, 'length->', length)
