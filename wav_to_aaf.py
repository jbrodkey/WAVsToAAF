#!/usr/bin/env python3
"""
WAVsToAAF - Convert WAV files to simplified AAF XML format

This script scans directories for WAV files, extracts audio metadata and BEXT data,
and generates simplified AAF XML files suitable for media management workflows.

Usage:
    python wav_to_aaf.py [input_directory] [output_directory]
    
Examples:
    python wav_to_aaf.py ./audio_files ./aaf_output
    python wav_to_aaf.py /path/to/wavs  # outputs to ./aaf_output
    python wav_to_aaf.py               # scans current dir, outputs to ./aaf_output

Author: Jason Brodkey
Version: 1.0.0
Date: 2025-11-03
"""

import os
import sys
import wave
import struct
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom

__version__ = "1.0.0"
__author__ = "Jason Brodkey"

class WAVMetadataExtractor:
    """Extract metadata from WAV files including BEXT chunk data"""
    
    def __init__(self):
        self.supported_formats = ['.wav', '.wave']
    
    def extract_basic_info(self, wav_path: str) -> Dict:
        """Extract basic audio information from WAV file"""
        try:
            with wave.open(wav_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                duration = frames / sample_rate if sample_rate > 0 else 0
                
                return {
                    'filename': Path(wav_path).name,
                    'filepath': wav_path,
                    'frames': frames,
                    'sample_rate': sample_rate,
                    'channels': channels,
                    'sample_width': sample_width,
                    'duration_seconds': duration,
                    'duration_timecode': self._seconds_to_timecode(duration),
                    'file_size': os.path.getsize(wav_path),
                    'creation_time': datetime.fromtimestamp(os.path.getctime(wav_path)).isoformat(),
                    'modification_time': datetime.fromtimestamp(os.path.getmtime(wav_path)).isoformat()
                }
        except Exception as e:
            print(f"Error reading {wav_path}: {e}")
            return {}
    
    def extract_bext_chunk(self, wav_path: str) -> Dict:
        """Extract BEXT chunk data from WAV file"""
        bext_data = {}
        
        try:
            with open(wav_path, 'rb') as f:
                # Skip RIFF header
                f.seek(12)
                
                while True:
                    chunk_header = f.read(8)
                    if len(chunk_header) < 8:
                        break
                    
                    chunk_id = chunk_header[:4].decode('ascii', errors='ignore')
                    chunk_size = struct.unpack('<I', chunk_header[4:8])[0]
                    
                    if chunk_id == 'bext':
                        # Read BEXT chunk data
                        bext_raw = f.read(chunk_size)
                        bext_data = self._parse_bext_chunk(bext_raw)
                        break
                    else:
                        # Skip this chunk
                        f.seek(chunk_size, 1)
                        if chunk_size % 2:  # Align to word boundary
                            f.seek(1, 1)
        
        except Exception as e:
            print(f"Error reading BEXT from {wav_path}: {e}")
        
        return bext_data
    
    def _parse_bext_chunk(self, bext_data: bytes) -> Dict:
        """Parse BEXT chunk binary data"""
        if len(bext_data) < 602:  # Minimum BEXT size
            return {}
        
        try:
            # BEXT structure (EBU R68-2000)
            description = bext_data[0:256].rstrip(b'\x00').decode('ascii', errors='ignore')
            originator = bext_data[256:288].rstrip(b'\x00').decode('ascii', errors='ignore')
            originator_ref = bext_data[288:320].rstrip(b'\x00').decode('ascii', errors='ignore')
            origination_date = bext_data[320:330].rstrip(b'\x00').decode('ascii', errors='ignore')
            origination_time = bext_data[330:338].rstrip(b'\x00').decode('ascii', errors='ignore')
            time_reference = struct.unpack('<Q', bext_data[338:346])[0]
            version = struct.unpack('<H', bext_data[346:348])[0]
            
            # UMID (64 bytes)
            umid = bext_data[348:412].hex().upper() if any(bext_data[348:412]) else ""
            
            # Loudness info (if version >= 1)
            loudness_value = loudness_range = max_true_peak = max_momentary = max_short_term = 0
            if version >= 1 and len(bext_data) >= 602:
                loudness_value = struct.unpack('<h', bext_data[412:414])[0]
                loudness_range = struct.unpack('<h', bext_data[414:416])[0] 
                max_true_peak = struct.unpack('<h', bext_data[416:418])[0]
                max_momentary = struct.unpack('<h', bext_data[418:420])[0]
                max_short_term = struct.unpack('<h', bext_data[420:422])[0]
            
            return {
                'description': description,
                'originator': originator,
                'originator_reference': originator_ref,
                'origination_date': origination_date,
                'origination_time': origination_time,
                'time_reference': time_reference,
                'version': version,
                'umid': umid,
                'loudness_value': loudness_value / 100.0 if loudness_value != 0x8000 else None,
                'loudness_range': loudness_range / 100.0 if loudness_range != 0x8000 else None,
                'max_true_peak': max_true_peak / 100.0 if max_true_peak != 0x8000 else None,
                'max_momentary_loudness': max_momentary / 100.0 if max_momentary != 0x8000 else None,
                'max_short_term_loudness': max_short_term / 100.0 if max_short_term != 0x8000 else None
            }
        
        except Exception as e:
            print(f"Error parsing BEXT data: {e}")
            return {}
    
    def _seconds_to_timecode(self, seconds: float, fps: int = 25) -> str:
        """Convert seconds to timecode format HH:MM:SS:FF"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * fps)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

class AAFGenerator:
    """Generate simplified AAF XML files from WAV metadata"""
    
    def __init__(self):
        self.namespace = "http://www.aafassociation.org/aafxml"
    
    def create_aaf_xml(self, wav_metadata: Dict, bext_metadata: Dict) -> str:
        """Create simplified AAF XML from WAV and BEXT metadata"""
        
        # Create root element
        root = ET.Element("AAF")
        root.set("xmlns", self.namespace)
        root.set("version", "1.1")
        root.set("generator", f"WAVsToAAF v{__version__}")
        root.set("timestamp", datetime.now().isoformat())
        
        # Header
        header = ET.SubElement(root, "Header")
        ET.SubElement(header, "Version").text = "1.1"
        ET.SubElement(header, "Generator").text = f"WAVsToAAF v{__version__}"
        ET.SubElement(header, "CreationTime").text = datetime.now().isoformat()
        
        # Content Storage
        content = ET.SubElement(root, "ContentStorage")
        
        # Master Mob
        master_mob = ET.SubElement(content, "MasterMob")
        mob_id = self._generate_mob_id(wav_metadata.get('filename', 'unknown'))
        master_mob.set("MobID", mob_id)
        
        # Mob properties
        ET.SubElement(master_mob, "Name").text = wav_metadata.get('filename', 'Unknown')
        ET.SubElement(master_mob, "CreationTime").text = wav_metadata.get('creation_time', '')
        ET.SubElement(master_mob, "LastModified").text = wav_metadata.get('modification_time', '')
        
        # Add BEXT metadata if available
        if bext_metadata:
            bext_elem = ET.SubElement(master_mob, "BextMetadata")
            for key, value in bext_metadata.items():
                if value is not None and value != "":
                    elem = ET.SubElement(bext_elem, key.replace('_', '').title())
                    elem.text = str(value)
        
        # Timeline Mob Slot
        timeline_slot = ET.SubElement(master_mob, "TimelineMobSlot")
        timeline_slot.set("SlotID", "1")
        ET.SubElement(timeline_slot, "SlotName").text = "Audio"
        ET.SubElement(timeline_slot, "EditRate").text = str(wav_metadata.get('sample_rate', 48000))
        
        # Source Clip
        source_clip = ET.SubElement(timeline_slot, "SourceClip")
        ET.SubElement(source_clip, "StartTime").text = "0"
        ET.SubElement(source_clip, "Length").text = str(wav_metadata.get('frames', 0))
        
        # Audio properties
        audio_props = ET.SubElement(source_clip, "AudioProperties")
        ET.SubElement(audio_props, "SampleRate").text = str(wav_metadata.get('sample_rate', 0))
        ET.SubElement(audio_props, "Channels").text = str(wav_metadata.get('channels', 0))
        ET.SubElement(audio_props, "SampleWidth").text = str(wav_metadata.get('sample_width', 0))
        ET.SubElement(audio_props, "Duration").text = wav_metadata.get('duration_timecode', '00:00:00:00')
        ET.SubElement(audio_props, "FileSize").text = str(wav_metadata.get('file_size', 0))
        
        # File Reference
        file_ref = ET.SubElement(source_clip, "FileReference")
        ET.SubElement(file_ref, "FileName").text = wav_metadata.get('filename', '')
        ET.SubElement(file_ref, "FilePath").text = wav_metadata.get('filepath', '')
        
        return self._prettify_xml(root)
    
    def _generate_mob_id(self, filename: str) -> str:
        """Generate a simple Mob ID based on filename"""
        # Simple hash-based ID generation
        import hashlib
        hash_obj = hashlib.md5(filename.encode())
        hash_hex = hash_obj.hexdigest()
        return f"urn:uuid:{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"
    
    def _prettify_xml(self, elem: ET.Element) -> str:
        """Return a pretty-printed XML string"""
        rough_string = ET.tostring(elem, 'unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

class WAVsToAAFProcessor:
    """Main processor class for converting WAV files to AAF format"""
    
    def __init__(self):
        self.extractor = WAVMetadataExtractor()
        self.generator = AAFGenerator()
    
    def process_directory(self, input_dir: str, output_dir: str) -> int:
        """Process all WAV files in a directory"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        
        if not input_path.exists():
            print(f"Error: Input directory '{input_dir}' does not exist")
            return 1
        
        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Find WAV files
        wav_files = []
        for ext in self.extractor.supported_formats:
            wav_files.extend(input_path.glob(f"**/*{ext}"))
            wav_files.extend(input_path.glob(f"**/*{ext.upper()}"))
        
        if not wav_files:
            print(f"No WAV files found in '{input_dir}'")
            return 1
        
        print(f"Found {len(wav_files)} WAV file(s) to process...")
        
        processed = 0
        for wav_file in wav_files:
            try:
                print(f"Processing: {wav_file.name}")
                
                # Extract metadata
                wav_metadata = self.extractor.extract_basic_info(str(wav_file))
                bext_metadata = self.extractor.extract_bext_chunk(str(wav_file))
                
                if not wav_metadata:
                    print(f"  Skipping {wav_file.name}: Could not read metadata")
                    continue
                
                # Generate AAF XML
                aaf_xml = self.generator.create_aaf_xml(wav_metadata, bext_metadata)
                
                # Write output file
                output_filename = wav_file.stem + '.aaf.xml'
                output_file = output_path / output_filename
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(aaf_xml)
                
                print(f"  Created: {output_filename}")
                processed += 1
                
            except Exception as e:
                print(f"  Error processing {wav_file.name}: {e}")
        
        print(f"\nCompleted! Processed {processed} file(s)")
        print(f"Output files saved to: {output_dir}")
        return 0
    
    def process_single_file(self, wav_file: str, output_file: str) -> int:
        """Process a single WAV file"""
        try:
            print(f"Processing: {wav_file}")
            
            # Extract metadata
            wav_metadata = self.extractor.extract_basic_info(wav_file)
            bext_metadata = self.extractor.extract_bext_chunk(wav_file)
            
            if not wav_metadata:
                print(f"Error: Could not read metadata from {wav_file}")
                return 1
            
            # Generate AAF XML
            aaf_xml = self.generator.create_aaf_xml(wav_metadata, bext_metadata)
            
            # Write output file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(aaf_xml)
            
            print(f"Created: {output_file}")
            return 0
            
        except Exception as e:
            print(f"Error processing {wav_file}: {e}")
            return 1

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Convert WAV files to simplified AAF XML format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./audio_files ./aaf_output    # Process directory
  %(prog)s ./audio_files                 # Output to ./aaf_output
  %(prog)s                               # Process current dir
  %(prog)s -f input.wav output.aaf.xml   # Process single file
        """
    )
    
    parser.add_argument('input', nargs='?', default='.',
                        help='Input directory or file (default: current directory)')
    parser.add_argument('output', nargs='?', default='./aaf_output',
                        help='Output directory or file (default: ./aaf_output)')
    parser.add_argument('-f', '--file', action='store_true',
                        help='Process single file instead of directory')
    parser.add_argument('-v', '--version', action='version',
                        version=f'WAVsToAAF {__version__}')
    
    args = parser.parse_args()
    
    processor = WAVsToAAFProcessor()
    
    if args.file:
        return processor.process_single_file(args.input, args.output)
    else:
        return processor.process_directory(args.input, args.output)

if __name__ == "__main__":
    sys.exit(main())