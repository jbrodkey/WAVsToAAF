#!/usr/bin/env python3
"""
WAVsToAAF GUI - Convenience launcher for the Graphical User Interface

Copyright (c) 2025 Jason Brodkey. All rights reserved.

This is a thin wrapper that launches the GUI mode of wav_to_aaf.py.
For the same functionality, you can also run:
    python wav_to_aaf.py --gui

Author: Jason Brodkey
Version: 1.0.0
Date: 2025-11-04
"""

import sys
import os

# Add the script directory to the path to ensure wav_to_aaf can be imported
sys.path.insert(0, os.path.dirname(__file__))

try:
    from wav_to_aaf import launch_gui
    
    if __name__ == "__main__":
        launch_gui()
        
except ImportError as e:
    print(f"Error: Could not import wav_to_aaf module: {e}")
    print("Make sure wav_to_aaf.py is in the same directory as this file.")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

