from wav_to_aaf import WAVsToAAFProcessor
from pathlib import Path
import tempfile


def test_info_metadata_overrides_fuzzy():
    proc = WAVsToAAFProcessor()
    # Provide filename that doesn't start with UCS ID; set info metadata containing category/subcategory
    res = proc._resolve_ucs_metadata('random_sound.wav', 'some description', {'Category': 'TESTCAT', 'SubCategory': 'TESTSUB'}, {})
    assert res and 'primary_category' in res
    assert res['primary_category']['category'] == 'TESTCAT'
    assert res['primary_category']['subcategory'] == 'TESTSUB'


def test_info_ucsid_preferred_and_score100():
    proc = WAVsToAAFProcessor()
    res = proc._resolve_ucs_metadata('random_sound.wav', 'desc', {'UCS_ID': 'MYID', 'Category': 'C', 'SubCategory': 'S'}, {})
    assert res['primary_category']['id'] == 'MYID'
    assert float(res['primary_category']['score']) == 100.0
