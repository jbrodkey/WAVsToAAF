"""Windows startup wrapper that logs uncaught startup exceptions to a temp file.

This file is intended to be used as the PyInstaller entry script for Windows
builds (replace the spec's script with this file). It attempts to import the
normal GUI launcher and call it; if any import or startup exception occurs it
writes a traceback to %TEMP%/wavtoaaf_startup.log so failures aren't silent.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import datetime


def _log_path() -> str:
    """Return the path to the startup log file for the current platform."""
    tdir = tempfile.gettempdir()
    return os.path.join(tdir, "wavtoaaf_startup.log")


def _write_log(header: str, tb: str) -> None:
    path = _log_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"{header} -- {datetime.utcnow().isoformat()} UTC\n")
            f.write(tb)
            f.write("\n")
    except Exception:
        # If logging fails, fall back to stderr.
        try:
            sys.stderr.write(header + "\n")
            sys.stderr.write(tb + "\n")
        except Exception:
            pass


def main() -> None:
    """Attempt to start the real GUI launcher and capture any startup errors.

    This wrapper intentionally writes full tracebacks to a temp file so that
    Windows builds with `console=False` don't fail silently.
    """
    try:
        # Ensure the project root is importable for source and frozen builds.
        packaging_dir = os.path.abspath(os.path.dirname(__file__))
        project_root = os.path.abspath(os.path.join(packaging_dir, os.pardir))
        sys.path.insert(0, packaging_dir)
        sys.path.insert(0, project_root)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            sys.path.insert(0, sys._MEIPASS)

        import wav_to_aaf

        # If the user explicitly asked for GUI mode, prefer that.
        if '--gui' in sys.argv:
            try:
                sys.argv.remove('--gui')
            except ValueError:
                pass
            if hasattr(wav_to_aaf, "launch_gui") and callable(wav_to_aaf.launch_gui):
                wav_to_aaf.launch_gui()
                return

        # If any CLI arguments are present (including --version), prefer the
        # command-line entrypoint `main()` so non-interactive checks work.
        if len(sys.argv) > 1:
            if hasattr(wav_to_aaf, "main") and callable(wav_to_aaf.main):
                # Return/exit with the same code as main() when possible.
                try:
                    rc = wav_to_aaf.main()
                    if isinstance(rc, int):
                        sys.exit(rc)
                    return
                except SystemExit:
                    raise
                except Exception:
                    # Let the outer exception handler record the traceback
                    raise

        # No CLI args provided: fall back to GUI if available.
        if hasattr(wav_to_aaf, "launch_gui") and callable(wav_to_aaf.launch_gui):
            wav_to_aaf.launch_gui()
            return

        module_file = getattr(wav_to_aaf, '__file__', '<unknown>')
        available = [name for name in ('launch_gui', 'main') if hasattr(wav_to_aaf, name)]

        try:
            import wav_to_aaf_gui
            if hasattr(wav_to_aaf_gui, "launch_gui") and callable(wav_to_aaf_gui.launch_gui):
                wav_to_aaf_gui.launch_gui()
                return
        except Exception:
            pass

        raise RuntimeError(
            f"wav_to_aaf has no callable launch entry point; module file={module_file}; available={available}"
        )

    except Exception:
        tb = traceback.format_exc()
        header = "WAVsToAAF startup exception"
        _write_log(header, tb)
        # Re-raise so PyInstaller's error handling (if enabled) can also act.
        raise


if __name__ == "__main__":
    main()
