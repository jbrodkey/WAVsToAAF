"""Unified CLI entry point for MXToAAF

Automatically detects whether input is a file or directory and runs
appropriate mode (single-file conversion or batch processing).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .__version__ import __version__
from .batch import process_directory
from .utils import ffmpeg_available
from .metadata import extract_music_metadata
from .aaf import create_music_aaf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mxtoaaf",
        description="Convert music files to AAF with metadata - supports single files or batch directories"
    )
    parser.add_argument("input", nargs="?", help="input music file or directory")
    parser.add_argument("--output", help="output AAF file or directory (required for batch)", required=False)
    parser.add_argument("--embed", action="store_true", help="embed audio essence into AAF (requires ffmpeg + aaf2)")
    parser.add_argument("--tag-map", help="JSON file mapping metadata fields to AAF tag names (optional)")
    parser.add_argument("--fps", type=float, default=24.0, help="frame rate for AAF timeline (default: 24.0)")
    parser.add_argument("--version", action="version", version=f"MXToAAF {__version__}")
    
    # Batch-specific options
    batch_group = parser.add_argument_group("batch processing options")
    batch_group.add_argument("--batch", action="store_true", help="force batch mode (auto-detected if input is directory)")
    batch_group.add_argument("--no-recursive", action="store_true", help="do not recurse into subdirectories (batch only)")
    batch_group.add_argument("--max-files", type=int, help="limit to N files for quick runs (batch only)")
    batch_group.add_argument("--skip-existing", action="store_true", help="skip files if output AAF already exists (batch only)")
    batch_group.add_argument("--log-file", help="write detailed results to JSON log file (batch only)")
    batch_group.add_argument("--export-csv", help="write per-file results to CSV report (batch only)")
    batch_group.add_argument("--export-metadata-csv", help="write per-file parsed metadata fields to CSV report (batch only)")
    
    # Single-file specific
    single_group = parser.add_argument_group("single-file options")
    single_group.add_argument("--dry-run", action="store_true", help="extract metadata without creating AAF (single-file only)")

    args = parser.parse_args(argv)
    
    # Interactive mode if no input provided
    if not args.input:
        print("MXToAAF - Music to AAF Converter")
        print("=" * 50)
        args.input = input("Input file or directory: ").strip()
        if not args.input:
            print("Error: Input is required")
            return 2
    
    # Sanitize drag-and-drop or shell-escaped paths
    def _sanitize_path(p: str) -> str:
        s = p.strip()
        # Remove surrounding quotes from drag-and-drop or copied paths
        if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
            s = s[1:-1]
        # Handle escaped spaces from shell copy ("\ ") → space
        # Only apply on POSIX-like systems to avoid interfering with Windows backslashes
        if os.name == 'posix':
            s = s.replace("\\ ", " ")
        # Expand user (~) and resolve relative segments
        s = os.path.expanduser(s)
        return s

    args.input = _sanitize_path(args.input)
    input_path = Path(args.input)
    
    # Validate input exists
    if not input_path.exists():
        print(f"Error: {args.input} does not exist")
        return 2
    
    # Auto-detect mode
    is_directory = input_path.is_dir()
    is_batch = args.batch or is_directory
    
    # Interactive output prompt if not provided
    if not args.output:
        if is_batch:
            default_output = str(input_path.parent / (input_path.name + "_AAFs"))
        else:
            default_output = str(input_path.with_suffix('.aaf'))
        
        output_input = input(f"Output [{default_output}]: ").strip()
        output_input = _sanitize_path(output_input) if output_input else ""
        args.output = output_input if output_input else default_output
    
    # Interactive embed prompt if not set
    if not args.embed and sys.stdin.isatty():
        embed_input = input("Embed audio essence? [Y/n]: ").strip().lower()
        args.embed = embed_input != 'n'
    
    # Interactive CSV export prompt for batch mode
    if is_batch and not args.export_csv and sys.stdin.isatty():
        csv_input = input("Export CSV report? [y/N]: ").strip().lower()
        if csv_input == 'y':
            default_csv = str(Path(args.output) / "results.csv")
            csv_path = input(f"CSV path [{default_csv}]: ").strip()
            args.export_csv = csv_path if csv_path else default_csv
    
    if is_batch:
        # Batch mode
        if not args.output:
            print("Error: --output directory is required for batch processing")
            return 2
        
        if args.embed and not ffmpeg_available():
            print("ffmpeg not available — cannot embed. Install ffmpeg or run without --embed")
            return 2
        
        tag_map = None
        if args.tag_map:
            import json
            with open(args.tag_map, "r", encoding="utf-8") as fh:
                tag_map = json.load(fh)
        
        print(f"Batch mode: Processing {args.input} -> {args.output}")
        print(f"Embed: {args.embed}, Skip existing: {args.skip_existing}")
        
        summary = process_directory(
            args.input,
            args.output,
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
            for item in summary['failed_files'][:10]:
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
    
    else:
        # Single-file mode
        if not input_path.is_file():
            print(f"Error: {args.input} is not a file")
            return 2
        
        out = args.output or str(input_path.with_suffix('.aaf'))
        
        tag_map = None
        if args.tag_map:
            import json
            with open(args.tag_map, "r", encoding="utf-8") as fh:
                tag_map = json.load(fh)
        
        metadata = extract_music_metadata(str(input_path))
        
        if args.dry_run:
            print("Single-file mode (dry-run): Writing manifest")
            created = create_music_aaf(str(input_path), metadata, out, embed=False, tag_map=tag_map, fps=args.fps)
            print("Manifest created:", created)
            return 0
        
        if args.embed:
            if not ffmpeg_available():
                print("ffmpeg required to convert to WAV for AAF embedding — install it or run with --dry-run")
                return 2
            
            from .utils import convert_to_wav
            tmp = str(Path(out).with_suffix('.tmp.wav'))
            convert_to_wav(str(input_path), tmp)
            try:
                created = create_music_aaf(tmp, metadata, out, embed=True, tag_map=tag_map, fps=args.fps)
                print("Single-file mode: AAF created:", created)
            finally:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        else:
            created = create_music_aaf(str(input_path), metadata, out, embed=False, tag_map=tag_map, fps=args.fps)
            print("Single-file mode: AAF created:", created)
        
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
