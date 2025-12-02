import json
import os
from pathlib import Path
from mxto_aaf import cli


SAMPLES_DIR = Path('/Users/jasonbrodkey/Documents/SFX/pythonScripts/MXToAAF/Sample Media/wavTest_MX')


def _iter_audio_files(root: Path, max_files: int = 6):
    exts = {'.mp3', '.m4a', '.wav', '.aif', '.aiff'}
    count = 0
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in exts:
            yield p
            count += 1
            if count >= max_files:
                return


def test_dry_run_manifests_for_samples(tmp_path):
    assert SAMPLES_DIR.exists(), "Sample Media folder not found"
    files = list(_iter_audio_files(SAMPLES_DIR, max_files=8))
    assert files, "No audio files found in sample media"

    for src in files:
        out = tmp_path / (src.stem + '.aaf')
        rc = cli.main([str(src), '--dry-run', '-o', str(out)])
        assert rc == 0
        manifest = out.with_suffix(out.suffix + '.manifest.json')
        assert manifest.exists(), f"Manifest not written for {src}"
        data = json.loads(manifest.read_text())
        assert data['source'] == str(src)
        # Ensure metadata block exists
        assert 'metadata' in data
        # Track name must be present (fallback to filename)
        assert data['metadata'].get('track_name') is not None
