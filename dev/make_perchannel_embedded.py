#!/usr/bin/env python3
"""
Create AAFs that embed audio one-mono-channel-per-SourceMob (Avid-style) for each WAV in spec_test_aafs.
Resulting files are saved to embedded_test_aafs/perchannel_<wav_stem>.aaf
"""
from pathlib import Path
import wave, tempfile, os
import aaf2

SRC = Path('spec_test_aafs')
OUT = Path('embedded_test_aafs')
OUT.mkdir(parents=True, exist_ok=True)

wav_files = sorted(SRC.glob('*.wav'))
if not wav_files:
    print('No wavs found')
    raise SystemExit(1)

for wav in wav_files:
    stem = wav.stem
    out_file = OUT / f'perchannel_embedded_{stem}.aaf'
    print('Processing', wav)

    with wave.open(str(wav),'rb') as r:
        nch = r.getnchannels()
        sampwidth = r.getsampwidth()
        framerate = r.getframerate()
        nframes = r.getnframes()
        frames = r.readframes(nframes)

    # If mono, just embed like the normal helper (one track)
    if nch == 1:
        with aaf2.open(str(out_file),'w') as f:
            master = f.create.MasterMob(stem)
            f.content.mobs.append(master)
            master.import_audio_essence(str(wav), edit_rate=framerate)
            print('  mono embedded ->', out_file)
        continue

    # split per channel
    bytes_per_frame = sampwidth * nch
    # pre-allocate arrays for each channel
    channels_data = [bytearray() for _ in range(nch)]

    for i in range(nframes):
        off = i * bytes_per_frame
        for c in range(nch):
            start = off + c * sampwidth
            channels_data[c].extend(frames[start:start+sampwidth])

    # create temporary mono wav files
    tmp_paths = []
    try:
        for cidx, chdata in enumerate(channels_data, start=1):
            tmpd = tempfile.NamedTemporaryFile(prefix=f'{stem}_ch{cidx}_', suffix='.wav', delete=False)
            tmp_paths.append(Path(tmpd.name))
            tmpd.close()
            with wave.open(str(tmp_paths[-1]), 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(sampwidth)
                w.setframerate(framerate)
                w.writeframes(bytes(chdata))

        # create AAF and import each mono channel as separate source mob (and create master slots for each)
        with aaf2.open(str(out_file),'w') as f:
            master = f.create.MasterMob(stem)
            f.content.mobs.append(master)
            for chfile in tmp_paths:
                try:
                    master.import_audio_essence(str(chfile), edit_rate=framerate)
                except Exception as e:
                    print('  embedding channel failed:', e)
            print('  per-channel embedded ->', out_file)

    finally:
        # clean up temp files
        for p in tmp_paths:
            try:
                os.unlink(p)
            except Exception:
                pass

print('Done')
