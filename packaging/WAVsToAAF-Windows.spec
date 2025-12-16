# -*- mode: python ; coding: utf-8 -*-
import os

# Get the directory containing this spec file
spec_dir = os.path.dirname(os.path.abspath(SPEC))
# Get the parent directory (WAVsToAAF root)
root_dir = os.path.dirname(spec_dir)

# Extract version from _version.py
version = '1.0.0'  # default
version_file = os.path.join(root_dir, '_version.py')
if os.path.exists(version_file):
    with open(version_file, 'r') as f:
        for line in f:
            if '__version__' in line:
                version = line.split('=')[1].strip().strip('"').strip("'")
                break

# Bundle data files and main scripts for Windows
datas = [
    (os.path.join(root_dir, 'data'), 'data'),
    (os.path.join(root_dir, 'wav_to_aaf.py'), '.'),
    (os.path.join(root_dir, '_version.py'), '.'),
    (os.path.join(root_dir, 'icons', 'win', 'WAVsToAAF.ico'), 'icons'),
    (os.path.join(root_dir, 'LICENSES.txt'), '.'),
    (os.path.join(root_dir, 'README.md'), '.'),
    (os.path.join(root_dir, 'docs', 'README_windows.md'), 'docs'),
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
    version=os.path.join(spec_dir, 'version_info.txt'),
)
