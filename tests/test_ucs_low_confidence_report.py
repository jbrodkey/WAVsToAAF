import tempfile
from pathlib import Path
from wav_to_aaf import WAVsToAAFProcessor
import shutil
import wave
import struct


def test_low_confidence_report_written(tmp_path, tiny_wav_mono: Path):
    src_dir = tmp_path / 'src'
    out_dir = tmp_path / 'out'
    src_dir.mkdir()
    out_dir.mkdir()

    # Place a tiny wav into the source directory
    wav_path = src_dir / 'fx_door_close.wav'
    shutil.copyfile(str(tiny_wav_mono), str(wav_path))

    proc = WAVsToAAFProcessor()
    # lower the min score to 999 so all scored matches are considered low confidence
    proc._ucs_min_score = 999.0

    # Run directory processing which collects low-confidence items and writes report
    ret = proc.process_directory(str(src_dir), str(out_dir), embed_audio=False, allow_ucs_guess=True)
    assert ret == 0
    report = out_dir / 'ucs_low_confidence.csv'
    assert report.exists()
    # csv should at least contain header
    content = report.read_text()
    assert 'file,description,ucs_id,category,subcategory,score' in content
