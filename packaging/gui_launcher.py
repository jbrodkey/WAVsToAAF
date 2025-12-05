#!/usr/bin/env python3
"""
WAVsToAAF GUI Launcher for PyInstaller
This imports the main wav_to_aaf module so PyInstaller can analyze all dependencies
"""

import sys

# Import main module - PyInstaller will trace all dependencies from here
import wav_to_aaf

if __name__ == "__main__":
    wav_to_aaf.launch_gui()
