import os
from pathlib import Path
import tempfile

from wav_to_aaf import WAVsToAAFProcessor


def test_embedding_generated_wav_created(tiny_wav_mono: Path, tmp_outdir: Path):
    proc = WAVsToAAFProcessor()
    outpath = tmp_outdir / 'tiny.aaf'
    ret = proc.process_single_file(str(tiny_wav_mono), str(outpath), embed_audio=True)
    assert ret == 0
    assert outpath.exists() and outpath.stat().st_size > 0


def test_reject_non_wav_input(dummy_nonwav: Path, tmp_outdir: Path):
    proc = WAVsToAAFProcessor()
    outpath = tmp_outdir / 'dummy.aaf'
    ret = proc.process_single_file(str(dummy_nonwav), str(outpath), embed_audio=True)
    assert ret != 0
    assert not outpath.exists()
