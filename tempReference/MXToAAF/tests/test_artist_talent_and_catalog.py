import os
from mxto_aaf.metadata import extract_music_metadata
from mxto_aaf.utils import convert_to_wav
from mxto_aaf.aaf import create_music_aaf
import aaf2


def test_artist_and_talent_written(tmp_path):
    src = os.path.join("Sample Media", "wavTest_MX", "Abyss, The", "03 The Crane.m4a")
    md = extract_music_metadata(src)

    # For these sample files, artist info should exist
    assert md.artist is not None

    wavtmp = str(tmp_path / "t.wav")
    aafout = str(tmp_path / "out.aaf")
    convert_to_wav(src, wavtmp)
    create_music_aaf(wavtmp, md, aafout, embed=True)

    with aaf2.open(aafout, 'r') as A:
        for m in A.content.mobs:
            if type(m).__name__ == 'MasterMob':
                assert 'Artist' in m.comments
                assert 'Talent' in m.comments
                # They should be equal for this sample (album_artist isn't separate here)
                assert m.comments['Artist'] == m.comments['Talent']


def test_catalog_number_written(tmp_path):
    # 03 and 12 contain CatalogNumber in the sample set
    src = os.path.join("Sample Media", "wavTest_MX", "Abyss, The", "03 The Crane.m4a")
    md = extract_music_metadata(src)
    assert md.catalog_number is not None

    wavtmp = str(tmp_path / "t2.wav")
    aafout = str(tmp_path / "out2.aaf")
    convert_to_wav(src, wavtmp)
    create_music_aaf(wavtmp, md, aafout, embed=True)

    with aaf2.open(aafout, 'r') as A:
        for m in A.content.mobs:
            if type(m).__name__ == 'MasterMob':
                assert 'CatalogNumber' in m.comments
