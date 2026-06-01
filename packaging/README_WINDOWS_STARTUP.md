Windows packaging notes — startup wrapper & spec suggestions

This repository ships a Windows-specific startup wrapper at:

- packaging/startup_wrapper.py

Purpose
- Ensure startup exceptions are written to a temp logfile (`%TEMP%/wavtoaaf_startup.log`) so `console=False` builds don't fail silently.

Recommended spec changes (packaging/WAVsToAAF-Windows.spec)

1) Use the wrapper as the entry script (replace the script path used by EXE()):

    # before
    script='packaging/gui_launcher.py',

    # after
    script='packaging/startup_wrapper.py',

2) Ensure `tkinterdnd2` and missing `aaf2` submodules are collected/hidden. Example additions:

    from PyInstaller.utils.hooks import collect_all
    datas_tk, binaries_tk, hiddenimports_tk = collect_all('tkinterdnd2')
    a.datas += datas_tk
    a.binaries += binaries_tk
    hiddenimports += hiddenimports_tk

    # add common aaf2 submodules that can be missed
    hiddenimports += [
        'aaf2.audio',
        'aaf2.rational',
        'aaf2.misc',
    ]

3) During debugging, consider building with `console=True` or using `--onedir` so you can see stdout/stderr while reproducing problems.

Notes
- These changes are Windows-only and should be applied only to `packaging/WAVsToAAF-Windows.spec` so the Mac build (`WAVsToAAF.spec`) remains unchanged.
- After updating the spec, rebuild and run the exe from a Windows command prompt to capture tracebacks, or inspect `%TEMP%/wavtoaaf_startup.log` if the build is `console=False`.
