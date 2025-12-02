import tempfile
from pathlib import Path
import wave
import struct
import pytest


def _write_tiny_wav(path: Path, duration_sec: float = 0.01, sample_rate: int = 48000, channels: int = 1):
    frames = max(1, int(duration_sec * sample_rate))
    sampwidth = 2  # 16-bit PCM
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(sample_rate)
        frame = struct.pack('<h', 0)
        data = frame * channels * frames
        w.writeframes(data)


@pytest.fixture
def tmp_outdir() -> Path:
    return Path(tempfile.mkdtemp(prefix='w2a_out_'))


@pytest.fixture
def tiny_wav_mono() -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix='w2a_wav_'))
    wav = tmpdir / 'tiny_mono.wav'
    _write_tiny_wav(wav, channels=1)
    return wav


@pytest.fixture
def tiny_wav_stereo() -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix='w2a_wav_'))
    wav = tmpdir / 'tiny_stereo.wav'
    _write_tiny_wav(wav, channels=2)
    return wav


@pytest.fixture
def dummy_nonwav() -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix='w2a_wav_'))
    f = tmpdir / 'dummy.mp3'
    f.write_text('not a real mp3')
    return f
import sys
import os

# Ensure the local aaf2 implementation in 'aaf python stuff' (repo path) is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOCAL_AAF2 = os.path.join(ROOT, 'aaf python stuff')
if os.path.isdir(LOCAL_AAF2) and LOCAL_AAF2 not in sys.path:
    sys.path.insert(0, LOCAL_AAF2)
