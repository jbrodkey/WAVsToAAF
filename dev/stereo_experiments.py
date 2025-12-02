#!/usr/bin/env python3
"""
Create a few stereo-embedded AAF variants for each stereo WAV in spec_test_aafs/
Variants created per WAV (channels>1):
  - variant_A: single PCMDescriptor (default embed-stereo)
  - variant_B: same as A but set descriptor.ContainerFormat to OMF
  - variant_C: single SourceMob (PCMDescriptor) but MasterMob gets two slots both referencing source mob slot 1

Outputs: embedded_test_aafs/variants/<variant>_<wav_stem>.aaf
"""
import aaf2
from pathlib import Path
import wave

SRC = Path('spec_test_aafs')
OUT_DIR = Path('embedded_test_aafs/variants')
OUT_DIR.mkdir(parents=True, exist_ok=True)

wav_files = sorted([p for p in SRC.glob('*.wav')])
if not wav_files:
    print('No WAVs found in', SRC)
    raise SystemExit(1)

for wav in wav_files:
    with wave.open(str(wav),'rb') as r:
        ch = r.getnchannels()
    if ch < 2:
        continue
    stem = wav.stem.replace(' ','_')

    print('===', wav.name)

    # Variant A: default multi-channel embed (single slot)
    out_a = OUT_DIR / f'variant_A_{stem}.aaf'
    with aaf2.open(out_a,'w') as f:
        master = f.create.MasterMob(stem)
        f.content.mobs.append(master)
        # import into a single SourceMob
        phys = f.create.SourceMob(stem + '.PHYS')
        f.content.mobs.append(phys)
        phys.import_audio_essence(str(wav), edit_rate=None)
        # master: single slot pointing to phys slot 1
        slot = master.create_timeline_slot(48000)
        sc = f.create.SourceClip()
        sc['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
        sc['Length'].value = phys.descriptor['Length'].value
        sc['StartTime'].value = 0
        sc['SourceID'].value = phys.mob_id
        sc['SourceMobSlotID'].value = 1
        slot.segment = sc
    print('  wrote', out_a)

    # Variant B: set ContainerFormat on descriptor to 'OMF'
    out_b = OUT_DIR / f'variant_B_{stem}.aaf'
    with aaf2.open(out_b,'w') as f:
        master = f.create.MasterMob(stem)
        f.content.mobs.append(master)
        phys = f.create.SourceMob(stem + '.PHYS')
        f.content.mobs.append(phys)
        phys.import_audio_essence(str(wav), edit_rate=None)
        # try to force container format on descriptor
        try:
            phys.descriptor['ContainerFormat'].value = f.dictionary.lookup_containerdef('OMF')
        except Exception:
            pass
        slot = master.create_timeline_slot(48000)
        sc = f.create.SourceClip()
        sc['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
        sc['Length'].value = phys.descriptor['Length'].value
        sc['StartTime'].value = 0
        sc['SourceID'].value = phys.mob_id
        sc['SourceMobSlotID'].value = 1
        slot.segment = sc
    print('  wrote', out_b)

    # Variant C: master has two slots both referencing the one phys source
    out_c = OUT_DIR / f'variant_C_{stem}.aaf'
    with aaf2.open(out_c,'w') as f:
        master = f.create.MasterMob(stem)
        f.content.mobs.append(master)
        phys = f.create.SourceMob(stem + '.PHYS')
        f.content.mobs.append(phys)
        phys.import_audio_essence(str(wav), edit_rate=None)
        # create two master slots both referencing phys
        for i in range(2):
            slot = master.create_timeline_slot(48000)
            sc = f.create.SourceClip()
            sc['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
            sc['Length'].value = phys.descriptor['Length'].value
            sc['StartTime'].value = 0
            sc['SourceID'].value = phys.mob_id
            sc['SourceMobSlotID'].value = 1
            slot.segment = sc
    print('  wrote', out_c)

print('Done')
