#!/usr/bin/env python3
"""
WAVsToAAF GUI Launcher
Launches the GUI mode of WAVsToAAF
"""

import sys
import os

# Add the script directory to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from wav_to_aaf import launch_gui

if __name__ == "__main__":
    launch_gui()
