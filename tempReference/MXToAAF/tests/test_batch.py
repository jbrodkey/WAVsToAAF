from pathlib import Path
from mxto_aaf.batch import process_directory


SAMPLES_DIR = Path('/Users/jasonbrodkey/Documents/SFX/pythonScripts/MXToAAF/Sample Media/wavTest_MX')


def test_process_directory_creates_manifests(tmp_path):
    assert SAMPLES_DIR.exists()
    out = tmp_path / 'out'
    r = process_directory(SAMPLES_DIR, out, recursive=True, embed=False, max_files=3)
    assert len(r) == 3
    # check that manifests were written
    for p in out.iterdir():
        assert p.suffix in {'.aaf', '.json', '.manifest.json'} or p.suffix == '.aaf'
