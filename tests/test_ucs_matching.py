from wav_to_aaf import UCSProcessor
from pathlib import Path


def test_ucs_fuzzy_matching_by_default():
    u = UCSProcessor()
    # Use test WAV metadata: filename + description
    res = u.categorize_sound('chicken_cackle_01.wav', 'Animals, birds, chicken cackle')
    assert res and 'primary_category' in res


def test_ucs_exact_only_mode():
    u = UCSProcessor()
    # If allow_guess is False and filename doesn't start with a UCS ID, no match should be returned
    res = u.categorize_sound('chicken_cackle_01.wav', 'Animals, birds, chicken cackle', allow_guess=False)
    assert res == {}

    # Exact ID prefix should still match in exact-only mode
    res2 = u.categorize_sound('TOONAnml_chicken_cackle.wav', 'Animals, birds, chicken cackle', allow_guess=False)
    assert res2 and 'primary_category' in res2
    assert res2['primary_category']['id'] == 'TOONAnml'
