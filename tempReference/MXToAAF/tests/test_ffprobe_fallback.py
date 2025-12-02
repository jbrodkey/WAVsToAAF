import os
from mxto_aaf.metadata import extract_music_metadata


def test_ffprobe_reads_m4a_tags():
    path = os.path.join("Sample Media", "wavTest_MX", "AC_DC", "Back In Black", "06 Back In Black.m4a")
    md = extract_music_metadata(path)

    # These sample files in the repository contain real music metadata —
    # ffprobe fallback should pick them up even when mutagen isn't installed.
    assert md.track_name and "Back In Black" in md.track_name
    assert md.talent and len(md.talent) > 0
    assert md.album and "Back In Black" in md.album
    # composer may include multiple names — just ensure it's present
    assert md.composer and len(md.composer) > 0
    # duration should resolve either from mutagen or ffprobe
    assert md.duration is not None
