#!/usr/bin/env python3
"""
Create Avid-style embedded AAFs for each WAV in spec_test_aafs/
This script creates a MasterMob and uses MasterMob.import_audio_essence()
which writes essence data into the AAF.

Outputs go into embedded_test_aafs/avid_embedded_<wav_stem>.aaf
"""
import aaf2
from pathlib import Path
from wave import open as wave_open

SRC_DIR = Path('spec_test_aafs')
OUT_DIR = Path('embedded_test_aafs')
OUT_DIR.mkdir(parents=True, exist_ok=True)

wav_files = sorted(SRC_DIR.glob('*.wav'))
if not wav_files:
    print('No WAVs found in', SRC_DIR)
    raise SystemExit(1)

for wav in wav_files:
    stem = wav.stem
    out_file = OUT_DIR / f'avid_embedded_{stem}.aaf'
    print('Creating Avid-style embedded AAF for', wav, '->', out_file)

    # read sample rate to pass as edit_rate (keeps timeline at sample rate)
    with wave_open(str(wav),'rb') as w:
        sample_rate = w.getframerate()

    with aaf2.open(str(out_file),'w') as f:
        # create a master mob that will import essence into a source mob
        master = f.create.MasterMob(stem)
        f.content.mobs.append(master)

        try:
            # MasterMob.import_audio_essence will create a new SourceMob (physical), write essencedata
            # and create a slot on the master that references the created source mob
            master.import_audio_essence(str(wav), edit_rate=sample_rate)
            print('  embedded OK')
        except Exception as e:
            print('  embedding failed:', e)

print('Done')
