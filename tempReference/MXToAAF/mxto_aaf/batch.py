"""Batch-processing utilities for MXToAAF

Process directories of music files and produce AAFs (or manifests) for each
file. This is intended for batch generation of dry-run manifests or for full
embedding when ffmpeg + aaf2 are present.
"""
from __future__ import annotations

import argparse
import os
import json
import sys
import time
import csv
from pathlib import Path
from typing import Iterable, Dict, Any, List

from .metadata import extract_music_metadata, MusicMetadata
from .aaf import create_music_aaf
from .utils import ffmpeg_available, convert_to_wav


SUPPORTED = {".mp3", ".m4a", ".wav", ".aif", ".aiff"}


def _iter_audio_files(path: Path, recursive: bool = True) -> Iterable[Path]:
    if recursive:
        for p in path.rglob("*"):
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                yield p
    else:
        for p in path.iterdir():
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                yield p


def _process_single_file(
    p: Path,
    src_root: Path,
    out_dir: Path,
    embed: bool,
    tag_map: dict | None,
    skip_existing: bool,
    fps: float = 24.0,
) -> Dict[str, Any]:
    """Process a single audio file and return result dict"""
    result = {
        "input": str(p),
        "output": None,
        "status": "success",
        "error": None,
        "duration": 0.0,
        "metadata": None,
    }
    
    start_time = time.time()
    
    try:
        # Mirror source directory structure under out_dir
        rel = p.relative_to(src_root)
        dest_dir = out_dir / rel.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / (p.stem + ".aaf")
        
        # Skip if already exists
        if skip_existing and dest.exists():
            result["status"] = "skipped"
            result["output"] = str(dest)
            return result
        
        md = extract_music_metadata(str(p))
        result["metadata"] = {
            "track_name": md.track_name,
            "track": md.track,
            "total_tracks": md.total_tracks,
            "genre": md.genre,
            "artist": md.artist,
            "album_artist": md.album_artist,
            "talent": md.talent,
            "composer": md.composer,
            "source": md.source,
            "album": md.album,
            "catalog_number": md.catalog_number,
            "description": md.description,
            "duration": md.duration,
        }

        # If we are embedding but the file is not a WAV, convert first.
        if embed and p.suffix.lower() != ".wav":
            tmp = str(dest_dir / (p.stem + ".tmp.wav"))
            convert_to_wav(str(p), tmp)
            created = create_music_aaf(tmp, md, str(dest), embed=True, tag_map=tag_map, fps=fps)
            try:
                os.remove(tmp)
            except Exception:
                pass
        else:
            created = create_music_aaf(str(p), md, str(dest), embed=embed, tag_map=tag_map, fps=fps)

        result["output"] = created
        result["duration"] = time.time() - start_time
        
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        result["duration"] = time.time() - start_time
    
    return result


def process_directory(
    src: str | Path,
    out_dir: str | Path,
    recursive: bool = True,
    embed: bool = False,
    tag_map: dict | None = None,
    max_files: int | None = None,
    skip_existing: bool = False,
    log_file: str | None = None,
    export_csv: str | None = None,
    export_metadata_csv: str | None = None,
    fps: float = 24.0,
) -> Dict[str, Any]:
    """Process directory with parallel support and detailed reporting
    
    Returns:
        Dict with keys: results, success_count, failed_count, skipped_count, 
        total_duration, failed_files
    """
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect all files first
    all_files = list(_iter_audio_files(src, recursive=recursive))
    if max_files is not None:
        all_files = all_files[:max_files]
    
    total_files = len(all_files)
    if total_files == 0:
        return {
            "results": [],
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "total_duration": 0.0,
            "failed_files": [],
        }
    
    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0
    failed_files = []
    
    start_time = time.time()
    
    # Progress display helper
    def _print_progress(completed, total, status_msg=""):
        pct = (completed / total * 100) if total > 0 else 0
        bar_width = 40
        filled = int(bar_width * completed / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        elapsed = time.time() - start_time
        rate = completed / elapsed if elapsed > 0 else 0
        eta = (total - completed) / rate if rate > 0 else 0
        
        sys.stdout.write(f"\r[{bar}] {completed}/{total} ({pct:.1f}%) | "
                        f"ETA: {eta:.0f}s | {status_msg}")
        sys.stdout.flush()
    
    # Sequential processing only (parallel removed due to I/O-bound workload)
    for idx, p in enumerate(all_files, 1):
        result = _process_single_file(p, src, out_dir, embed, tag_map, skip_existing, fps)
        results.append(result)
        
        if result["status"] == "success":
            success_count += 1
        elif result["status"] == "skipped":
            skipped_count += 1
        else:
            failed_count += 1
            failed_files.append({"file": str(p), "error": result["error"]})
        
        _print_progress(idx, total_files, f"Success: {success_count}, Failed: {failed_count}, Skipped: {skipped_count}")
    
    print()  # newline after progress
    
    total_duration = time.time() - start_time
    
    summary = {
        "results": results,
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "total_duration": total_duration,
        "failed_files": failed_files,
    }
    
    # Write log file if requested
    if log_file:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    # Write human-friendly CSV if requested
    if export_csv:
        try:
            with open(export_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["input", "output", "status", "error", "duration_s"])
                for r in results:
                    writer.writerow([
                        r.get("input"),
                        r.get("output"),
                        r.get("status"),
                        r.get("error"),
                        f"{float(r.get('duration', 0.0)):.3f}",
                    ])
        except Exception as e:
            print(f"Warning: unable to write CSV report {export_csv}: {e}")

    # Write detailed metadata CSV if requested
    if export_metadata_csv:
        try:
            with open(export_metadata_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "input","output","status","error","duration_s",
                    "Track Name","Track","Total Tracks","Genre","Artist","Album Artist","Talent","Composer","Source","Album","Catalog #","Description","Duration"
                ])
                for r in results:
                    md = r.get("metadata") or {}
                    writer.writerow([
                        r.get("input"),
                        r.get("output"),
                        r.get("status"),
                        r.get("error"),
                        f"{float(r.get('duration', 0.0)):.3f}",
                        md.get("track_name"),
                        md.get("track"),
                        md.get("total_tracks"),
                        md.get("genre"),
                        md.get("artist"),
                        md.get("album_artist"),
                        md.get("talent"),
                        md.get("composer"),
                        md.get("source"),
                        md.get("album"),
                        md.get("catalog_number"),
                        md.get("description"),
                        md.get("duration"),
                    ])
        except Exception as e:
            print(f"Warning: unable to write metadata CSV {export_metadata_csv}: {e}")
    
    return summary


# Note: The enhanced process_directory above is the canonical implementation.


def main(argv: list[str] | None = None) -> int:
    from .__version__ import __version__
    
    parser = argparse.ArgumentParser(prog="mxto_batch", description="Batch process a directory of music files into AAFs/manifests")
    parser.add_argument("src", help="source directory with audio files")
    parser.add_argument("-o", "--out", help="output directory", required=True)
    parser.add_argument("--embed", action="store_true", help="attempt essence embedding (requires ffmpeg + aaf2)")
    parser.add_argument("--no-recursive", action="store_true", help="do not recurse into subdirectories")
    parser.add_argument("--max-files", type=int, help="limit to N files for quick runs")
    parser.add_argument("--tag-map", help="path to JSON tag mapping file (optional)")
    parser.add_argument("--skip-existing", action="store_true", help="skip files if output AAF already exists")
    parser.add_argument("--log-file", help="write detailed results to JSON log file")
    parser.add_argument("--export-csv", help="write per-file results to a CSV report")
    parser.add_argument("--export-metadata-csv", help="write per-file parsed metadata fields to a CSV report")
    parser.add_argument("--fps", type=float, default=24.0, help="frame rate for AAF timeline (default: 24.0)")
    parser.add_argument("--version", action="version", version=f"MXToAAF {__version__}")

    args = parser.parse_args(argv)

    if args.embed and not ffmpeg_available():
        print("ffmpeg not available — cannot embed. Install ffmpeg or run without --embed")
        return 2

    tag_map = None
    if args.tag_map:
        with open(args.tag_map, "r", encoding="utf-8") as fh:
            tag_map = json.load(fh)

    print(f"Processing {args.src} -> {args.out}")
    print(f"Embed: {args.embed}, Skip existing: {args.skip_existing}")
    
    # Use enhanced process_directory (sequential only) with logging
    summary = process_directory(
        args.src,
        args.out,
        recursive=not args.no_recursive,
        embed=args.embed,
        tag_map=tag_map,
        max_files=args.max_files,
        skip_existing=args.skip_existing,
        log_file=args.log_file,
        export_csv=args.export_csv,
        export_metadata_csv=args.export_metadata_csv,
        fps=args.fps,
    )
    
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total files:    {summary['success_count'] + summary['failed_count'] + summary['skipped_count']}")
    print(f"✓ Success:      {summary['success_count']}")
    print(f"⊘ Skipped:      {summary['skipped_count']}")
    print(f"✗ Failed:       {summary['failed_count']}")
    print(f"Duration:       {summary['total_duration']:.1f}s")
    
    if summary['failed_files']:
        print(f"\nFailed files:")
        for item in summary['failed_files'][:10]:  # show first 10
            print(f"  • {item['file']}")
            print(f"    Error: {item['error']}")
        if len(summary['failed_files']) > 10:
            print(f"  ... and {len(summary['failed_files']) - 10} more (see log file)")
    
    if args.log_file:
        print(f"\nDetailed log written to: {args.log_file}")
    if args.export_csv:
        print(f"CSV report written to: {args.export_csv}")
    if args.export_metadata_csv:
        print(f"Metadata CSV written to: {args.export_metadata_csv}")
    
    return 0 if summary['failed_count'] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
