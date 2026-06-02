# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

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

# Generate version_info.txt for PyInstaller if needed.
version_info_path = os.path.join(spec_dir, 'version_info.txt')
version_info_content = f"""# UTF-8
#
# For more details about fixed file info:
# See: https://learn.microsoft.com/en-us/windows/win32/api/verrsrc/ns-verrsrc-vs_fixedfileinfo

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version.split('.')[0]}, {version.split('.')[1] if len(version.split('.')) > 1 else 0}, {version.split('.')[2] if len(version.split('.')) > 2 else 0}, {version.split('.')[3] if len(version.split('.')) > 3 else 0}),
    prodvers=({version.split('.')[0]}, {version.split('.')[1] if len(version.split('.')) > 1 else 0}, {version.split('.')[2] if len(version.split('.')) > 2 else 0}, {version.split('.')[3] if len(version.split('.')) > 3 else 0}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Jason Brodkey'),
        StringStruct(u'FileDescription', u'Convert WAV files to Advanced Authoring Format (AAF)'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'WAVsToAAF'),
        StringStruct(u'LegalCopyright', u'© 2025 Jason Brodkey'),
        StringStruct(u'OriginalFilename', u'WAVsToAAF.exe'),
        StringStruct(u'ProductName', u'WAVsToAAF'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
with open(version_info_path, 'w', encoding='utf-8') as _vf:
    _vf.write(version_info_content)

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

# Collect tkinterdnd2 resources if available (Windows drag-and-drop support)
try:
    datas_tk, binaries_tk, hiddenimports_tk = collect_all('tkinterdnd2')
except Exception:
    datas_tk, binaries_tk, hiddenimports_tk = [], [], []

a = Analysis(
    [os.path.join(spec_dir, 'startup_wrapper.py')],
    pathex=[root_dir],
    binaries=binaries_tk,
    datas=datas + datas_tk,
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
        'aaf2.audio',
        'wav_to_aaf_gui',
        'xml.etree.ElementTree',
        'webbrowser',
        'threading',
        'subprocess',
        'struct',
        'io',
        'tkinterdnd2',
    ] + hiddenimports_tk,
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
