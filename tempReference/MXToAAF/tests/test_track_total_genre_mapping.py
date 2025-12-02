import os
from mxto_aaf.metadata import extract_music_metadata
from mxto_aaf.utils import convert_to_wav
from mxto_aaf.aaf import create_music_aaf
import aaf2


def test_track_and_total_and_genre_written(tmp_path):
    src = os.path.join("Sample Media", "wavTest_MX", "AC_DC", "Back In Black", "06 Back In Black.m4a")
    wavtmp = str(tmp_path / "tmp.wav")
    aafout = str(tmp_path / "out.aaf")

    md = extract_music_metadata(src)
    # ensure extractor captured the track details; genre may be absent in some files
    assert md.track is not None
    # total_tracks is optional depending on tag format, don't require it strictly
    # genre may be absent — only assert later that if it exists it ends up in the AAF

    # convert to wav and write aaf, then inspect MasterMob for keys
    convert_to_wav(src, wavtmp)
    create_music_aaf(wavtmp, md, aafout, embed=True)

    with aaf2.open(aafout, 'r') as A:
        found = False
        for m in A.content.mobs:
            if type(m).__name__ == 'MasterMob':
                found = True
                assert 'TrackName' in m.comments
                assert 'Artist' in m.comments
                assert 'TrackNumber' in m.comments
                # total tracks may not be present in tags for all files, only assert if parsed
                if md.total_tracks is not None:
                    assert 'TotalTracks' in m.comments
                # genre may also be absent; ensure that if it was extracted it is written
                if md.genre is not None:
                    assert 'Genre' in m.comments
        assert found
