import os
import pytest

mutagen = pytest.importorskip("mutagen")

from mxto_aaf.metadata import extract_music_metadata


def test_mutagen_reads_mp3_and_m4a():
    # ensure mutagen can parse our sample MP3 and M4A
    mp3 = os.path.join("Sample Media", "wavTest_MX", "Flicka", "01 Main Title.mp3")
    m4a = os.path.join("Sample Media", "wavTest_MX", "AC_DC", "Back In Black", "06 Back In Black.m4a")

    for p in (mp3, m4a):
        assert os.path.exists(p), f"sample file missing: {p}"
        md = extract_music_metadata(p)
        # Basic expectations — files should have title and album/artist metadata
        assert md.track_name and len(md.track_name) > 0
        assert md.talent and len(md.talent) > 0
        assert md.album and len(md.album) > 0
