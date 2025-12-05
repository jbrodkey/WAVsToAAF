# -*- mode: python ; coding: utf-8 -*-
import os

# Get the directory containing this spec file
spec_dir = os.path.dirname(os.path.abspath(SPEC))
# Get the parent directory (WAVsToAAF root)
root_dir = os.path.dirname(spec_dir)

# Bundle data files and main scripts for Windows
datas = [
    (os.path.join(root_dir, 'data'), 'data'),
    (os.path.join(root_dir, 'wav_to_aaf.py'), '.'),
    (os.path.join(root_dir, '_version.py'), '.'),
]

a = Analysis(
    [os.path.join(spec_dir, 'gui_launcher.py')],
    pathex=[root_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.font',
        'tkinter.scrolledtext',
        'aaf2',
        'aaf2.auid',
        'aaf2.rational',
        'aaf2.misc',
        'xml.etree.ElementTree',
        'webbrowser',
        'threading',
        'subprocess',
        'struct',
        'io',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WAVsToAAF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(root_dir, 'icons', 'win', 'WAVsToAAF.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WAVsToAAF',
)
