import tempfile
from pathlib import Path
from wav_to_aaf import WAVsToAAFProcessor


def test_low_confidence_report_written(tmp_path):
    src_dir = Path('spec_test_aafs')
    out_dir = tmp_path / 'out'
    out_dir.mkdir()

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
