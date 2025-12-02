import json
from pathlib import Path
from mxto_aaf import cli


def test_tag_map_applied(tmp_path):
    # use a real sample file (exists in workspace) and the example_tag_map
    sample = '/Users/jasonbrodkey/Documents/SFX/pythonScripts/MXToAAF/Sample Media/wavTest_MX/AC_DC/Back In Black/06 Back In Black.m4a'
    assert Path(sample).exists()

    out = tmp_path / 'mapped.aaf'
    # example_tag_map.json lives at the MXToAAF project root
    tfile = Path(__file__).parents[1] / 'example_tag_map.json'
    assert tfile.exists(), 'example_tag_map.json must exist in MXToAAF project root for this test'

    rc = cli.main([sample, '--dry-run', '-o', str(out), '--tag-map', str(tfile)])
    assert rc == 0
    manifest = out.with_suffix(out.suffix + '.manifest.json')
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    # ensure the aaf_metadata has keys from the tag map values (like 'Avid Title' or 'TrackName')
    assert 'aaf_metadata' in data
    assert isinstance(data['aaf_metadata'], dict)
