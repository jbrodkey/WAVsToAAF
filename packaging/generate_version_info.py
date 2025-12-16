#!/usr/bin/env python3
"""Generate Windows version_info.txt file for PyInstaller from _version.py"""

import os
import sys

# Get root directory
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
version_file = os.path.join(root_dir, '_version.py')

# Extract version
version = '1.0.0'
if os.path.exists(version_file):
    with open(version_file, 'r') as f:
        for line in f:
            if '__version__' in line:
                version = line.split('=')[1].strip().strip('"').strip("'")
                break

# Parse version into components
version_parts = version.split('.')
major = version_parts[0] if len(version_parts) > 0 else '1'
minor = version_parts[1] if len(version_parts) > 1 else '0'
patch = version_parts[2] if len(version_parts) > 2 else '0'
build = version_parts[3] if len(version_parts) > 3 else '0'

# Generate version_info.txt
version_info_content = f"""# UTF-8
#
# For more details about fixed file info:
# See: https://learn.microsoft.com/en-us/windows/win32/api/verrsrc/ns-verrsrc-vs_fixedfileinfo

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
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

# Write to packaging directory
output_file = os.path.join(root_dir, 'packaging', 'version_info.txt')
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(version_info_content)

print(f"Generated {output_file} with version {version}")
