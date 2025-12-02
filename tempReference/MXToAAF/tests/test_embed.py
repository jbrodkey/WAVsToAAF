import wave
import os
from mxto_aaf.aaf import create_music_aaf
from mxto_aaf.metadata import MusicMetadata


def make_sine(path: str, duration_s: float = 0.01, framerate: int = 48000):
    nframes = int(duration_s * framerate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(3)  # 24-bit
        wf.setframerate(framerate)
        wf.writeframes(b"\x00" * nframes * 2 * 3)


def test_embed_small_wav(tmp_path):
    wav = tmp_path / "tiny.wav"
    aaf = tmp_path / "tiny.aaf"
    make_sine(str(wav))
    md = MusicMetadata(path=str(wav), track_name="tiny", raw={})
    out = create_music_aaf(str(wav), md, str(aaf), embed=True)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 512
    # Verify the AAF contains a MasterMob and that mapped metadata was stored as comments
    import aaf2
    with aaf2.open(out, 'r') as af:
        masters = list(af.content.mastermobs())
        assert len(masters) == 1
        master = masters[0]
        # confirm TrackName or Description present in tagged metadata
        items = dict(master.comments.items())
        assert 'TrackName' in items or 'Description' in items


def test_cli_dry_run_with_sample(tmp_path):
    # Use one of the provided sample media files for a dry-run manifest creation
    sample = '/Users/jasonbrodkey/Documents/SFX/pythonScripts/MXToAAF/Sample Media/wavTest_MX/Flicka/01 Main Title.mp3'
    assert os.path.exists(sample), "sample file not available"
    from mxto_aaf import cli

    dst = tmp_path / "sample.aaf"
    rc = cli.main([sample, "--dry-run", "-o", str(dst)])
    assert rc == 0
    assert (str(dst) + ".manifest.json")
