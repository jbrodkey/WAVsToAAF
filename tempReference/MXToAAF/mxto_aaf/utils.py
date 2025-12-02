"""Utilities for MXToAAF workspace package"""
from __future__ import annotations

import shutil
import subprocess


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def convert_to_wav(src_path: str, dst_path: str, samplerate: int = 48000, bits: int = 24, channels: int = 2) -> None:
    if not ffmpeg_available():
        raise FileNotFoundError("ffmpeg not available in PATH")

    # prefer explicit codec for 24-bit
    codec = "pcm_s24le" if bits == 24 else "pcm_s16le"
    cmd = [
        shutil.which("ffmpeg"),
        "-y",
        "-v",
        "error",
        "-i",
        src_path,
        "-ar",
        str(samplerate),
        "-ac",
        str(channels),
        "-acodec",
        codec,
        dst_path,
    ]

    subprocess.run(cmd, check=True)


__all__ = ["ffmpeg_available", "convert_to_wav"]
