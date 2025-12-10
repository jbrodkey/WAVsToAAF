#!/usr/bin/env python3
"""
WAVsToAAF - Convert WAV files to Advanced Authoring Format (AAF) files

Copyright (c) 2025 Jason Brodkey. All rights reserved.

This script scans directories for WAV files, extracts comprehensive audio metadata 
including BEXT, LIST-INFO chunks, embedded XML data, and UCS categorization, then 
generates Advanced Authoring Format (AAF) files with embedded metadata suitable 
for professional media workflows.

Supports both interactive prompting mode and command-line arguments.

Supported metadata:
- Standard WAV properties (sample rate, channels, duration, etc.)
- BEXT chunk (broadcast audio metadata)
- LIST-INFO chunks (IART, ICMT, ICOP, INAM, etc.)
- XML chunks (EBU Core, BWF MetaEdit, Pro Tools, etc.)
- UCS categorization (Universal Category System)

Usage:
    python wav_to_aaf.py                           # Interactive mode
    python wav_to_aaf.py [input_directory] [output_directory]
    
Examples:
    python wav_to_aaf.py                           # Prompts for input/output paths
    python wav_to_aaf.py ./audio_files ./aaf_output
    python wav_to_aaf.py /path/to/wavs  # outputs to ./aaf_output
    python wav_to_aaf.py -f input.wav output.aaf   # Process single file

Author: Jason Brodkey
Version: 2.0.0
Date: 2025-11-03
"""

import os
import sys
import wave
import struct
import argparse
import csv
import re
import io
import hashlib
import threading
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
import aaf2
import aaf2.auid
import aaf2.rational
import aaf2.misc

# Import version from _version.py
from _version import __version__, __author__

# AAF Pan Control AUIDs
AAF_PARAMETERDEF_PAN = aaf2.auid.AUID("e4962322-2267-11d3-8a4c-0050040ef7d2")
AAF_OPERATIONDEF_MONOAUDIOPAN = aaf2.auid.AUID("9d2ea893-0968-11d3-8a38-0050040ef7d2")


def _apply_pan_to_slot(f, mslot, mclip, pan_value: float, length_val: int):
    """
    Add pan control to a master timeline slot using OperationGroup with VaryingValue.
    
    Args:
        f: AAF file handle
        mslot: Master timeline slot
        mclip: Source clip to wrap
        pan_value: Pan position (-1.0 = left, 0.0 = center, 1.0 = right)
        length_val: Length in samples/frames
    """
    try:
        # Register ParameterDef for Pan
        typedef = f.dictionary.lookup_typedef("Rational")
        param_def = f.create.ParameterDef(AAF_PARAMETERDEF_PAN, "Pan", "Pan", typedef)
        try:
            f.dictionary.register_def(param_def)
        except Exception:
            # Already registered
            param_def = f.dictionary.lookup_def(AAF_PARAMETERDEF_PAN)
        
        # Register InterpolationDef
        try:
            interp_def = f.create.InterpolationDef(
                aaf2.misc.LinearInterp, "LinearInterp", "LinearInterp"
            )
            f.dictionary.register_def(interp_def)
        except Exception:
            interp_def = f.dictionary.lookup_def(aaf2.misc.LinearInterp)
        
        # Register OperationDef for MonoAudioPan
        try:
            opdef = f.create.OperationDef(AAF_OPERATIONDEF_MONOAUDIOPAN, "Audio Pan")
            opdef.media_kind = "sound"
            opdef["NumberInputs"].value = 1
            f.dictionary.register_def(opdef)
        except Exception:
            opdef = f.dictionary.lookup_def(AAF_OPERATIONDEF_MONOAUDIOPAN)
        
        # Create OperationGroup
        opgroup = f.create.OperationGroup(opdef)
        opgroup.media_kind = "sound"
        opgroup.length = int(length_val)
        
        # Create pan control points - MUST use Rational, not float!
        if pan_value == 0.0:
            pan_rational = aaf2.rational.AAFRational("0/1")
        elif pan_value < 0:
            pan_rational = aaf2.rational.AAFRational("-1/1")
        else:
            pan_rational = aaf2.rational.AAFRational("1/1")
        
        c1 = f.create.ControlPoint()
        c1["ControlPointSource"].value = 2
        c1["Time"].value = aaf2.rational.AAFRational(f"0/{int(length_val)}")
        c1["Value"].value = pan_rational
        
        c2 = f.create.ControlPoint()
        c2["ControlPointSource"].value = 2
        c2["Time"].value = aaf2.rational.AAFRational(f"{int(length_val) - 1}/{int(length_val)}")
        c2["Value"].value = pan_rational
        
        varying_value = f.create.VaryingValue()
        varying_value.parameterdef = param_def
        varying_value["Interpolation"].value = interp_def
        varying_value["PointList"].extend([c1, c2])
        
        opgroup.parameters.append(varying_value)
        opgroup.segments.append(mclip)
        mslot.segment = opgroup
        
    except Exception:
        # Fallback: use clip without pan control
        mslot.segment = mclip


def create_deterministic_umid(wav_path: Path, mob_type: str = "master", tape_mode: bool = False) -> aaf2.mobid.MobID:
    """
    Create a deterministic UMID based on file path, size, and modification time.
    
    Args:
        wav_path: Path to the WAV file
        mob_type: Type of mob ("master", "import", "wave", "tape") for differentiation
        tape_mode: If True, use Avid-style UMID prefix (01010f10) like ALE-exported AAFs
    
    Returns:
        Deterministic MobID that will be the same across runs for the same file
    """
    try:
        # Create a stable seed from file properties
        abs_path = str(wav_path.resolve())
        file_size = wav_path.stat().st_size if wav_path.exists() else 0
        mod_time = int(wav_path.stat().st_mtime) if wav_path.exists() else 0
        
        # Create base hash from file properties
        base_data = f"{abs_path}|{file_size}|{mod_time}".encode('utf-8')
        base_hash = hashlib.sha256(base_data).hexdigest()
        
        # Add mob type differentiation
        mob_data = f"{base_hash}|{mob_type}".encode('utf-8')
        mob_hash = hashlib.sha256(mob_data).digest()
        
        # Create SMPTE UMID URN string from hash
        # Choose UMID prefix based on mode
        if tape_mode:
            # Avid-style prefix from ALE-exported AAFs: 01010f10
            prefix = "060a2b34.01010105.01010f10.13000000"
        else:
            # Standard prefix: 01010f20  
            prefix = "060a2b34.01010105.01010f20.13000000"
        
        # Use first 16 bytes of hash to create the instance part (4 groups of 8 hex chars)
        instance_bytes = mob_hash[:16]
        instance_parts = []
        for i in range(0, 16, 4):
            hex_part = instance_bytes[i:i+4].hex()
            instance_parts.append(hex_part)
        
        instance_str = ".".join(instance_parts)
        urn = f"urn:smpte:umid:{prefix}.{instance_str}"
        
        # Create MobID from URN string
        return aaf2.mobid.MobID(urn)
        
    except Exception as e:
        print(f"Warning: Could not create deterministic UMID for {wav_path}: {e}")
        # Fall back to random UMID if deterministic generation fails
        return aaf2.mobid.MobID()


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
    
    def extract_all_metadata_chunks(self, wav_path: str) -> Dict:
        """Extract all metadata chunks from WAV file (BEXT, LIST-INFO, XML)"""
        all_metadata = {}
        
        try:
            # Read entire file into memory for efficient chunk parsing
            with open(wav_path, 'rb') as f:
                data = f.read()
            
            # Parse different chunk types
            all_metadata.update(self._parse_bext_chunk_from_data(data))
            all_metadata.update(self._parse_info_chunks(data))
            all_metadata.update(self._parse_xml_chunks(data))
            
        except Exception as e:
            print(f"Error reading metadata chunks from {wav_path}: {e}")
        
        return all_metadata
    
    def _parse_bext_chunk_from_data(self, data: bytes) -> Dict:
        """Parse BEXT chunk from raw file data"""
        bext_metadata = {}
        
        try:
            bext_start = data.find(b'bext')
            if bext_start != -1:
                # Skip the 'bext' identifier and chunk size (8 bytes total)
                bext_start += 8
                bext_raw = data[bext_start:bext_start + 602]  # Standard BEXT size
                bext_metadata = self._parse_bext_chunk(bext_raw)
        except Exception as e:
            print(f"Error parsing BEXT from data: {e}")
        
        return bext_metadata
    
    def _parse_info_chunks(self, data: bytes) -> Dict:
        """Parse LIST-INFO chunks from WAV file data"""
        info_metadata = {}
        
        try:
            offset = 0
            while True:
                # Find next LIST chunk
                list_start = data.find(b'LIST', offset)
                if list_start == -1:
                    break
                
                # Check if we have enough data for the LIST header
                if list_start + 12 > len(data):
                    break
                
                # Read LIST chunk size (4 bytes little-endian)
                list_size = struct.unpack('<I', data[list_start + 4:list_start + 8])[0]
                list_type = data[list_start + 8:list_start + 12]
                
                # We only care about INFO lists
                if list_type == b'INFO':
                    # Start of INFO subchunks
                    sub_offset = list_start + 12
                    end_of_list = list_start + 8 + list_size
                    
                    while sub_offset + 8 <= end_of_list and sub_offset + 8 <= len(data):
                        # Read subchunk header
                        chunk_id = data[sub_offset:sub_offset + 4]
                        chunk_size = struct.unpack('<I', data[sub_offset + 4:sub_offset + 8])[0]
                        
                        # Read chunk data
                        data_start = sub_offset + 8
                        data_end = data_start + chunk_size
                        
                        if data_end > len(data) or data_end > end_of_list:
                            break
                        
                        # Extract and clean the string data
                        chunk_data = data[data_start:data_end].split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
                        
                        if chunk_data:  # Only add non-empty data
                            try:
                                chunk_name = chunk_id.decode('ascii')
                                info_metadata[chunk_name] = self._sanitize_string(chunk_data)
                            except Exception:
                                info_metadata[str(chunk_id)] = self._sanitize_string(chunk_data)
                        
                        # Move to next subchunk (chunks are word-aligned)
                        pad = 1 if (chunk_size % 2) == 1 else 0
                        sub_offset = data_end + pad
                
                # Move forward to look for another LIST chunk
                offset = list_start + 4
                
        except Exception as e:
            print(f"Error parsing INFO chunks: {e}")
        
        return info_metadata
    
    def _parse_xml_chunks(self, data: bytes) -> Dict:
        """Parse XML chunks from WAV file data"""
        xml_metadata = {}
        
        try:
            # Look for common XML patterns in broadcast files
            xml_patterns = [
                b'<ebucore:ebuCoreMain',  # EBU Core XML
                b'<BWFMetaEdit>',         # BWF MetaEdit XML
                b'<ProTools',             # Pro Tools XML
                b'<axml',                 # BWF AXML chunk
                b'<?xml'                  # Generic XML
            ]
            
            for pattern in xml_patterns:
                xml_start = data.find(pattern)
                if xml_start != -1:
                    # Try to find the end of the XML
                    xml_end = self._find_xml_end(data, xml_start, pattern)
                    if xml_end > xml_start:
                        xml_data = data[xml_start:xml_end].decode('utf-8', errors='ignore')
                        
                        # Parse the XML and extract metadata
                        parsed_xml = self._parse_xml_content(xml_data)
                        if parsed_xml:
                            # Prefix keys to avoid conflicts with other metadata
                            xml_prefix = self._get_xml_prefix(pattern)
                            for key, value in parsed_xml.items():
                                xml_metadata[f"{xml_prefix}_{key}"] = value
                        
                        # Only process the first XML chunk found
                        break
                        
        except Exception as e:
            print(f"Error parsing XML chunks: {e}")
        
        return xml_metadata
    
    def _find_xml_end(self, data: bytes, start_pos: int, pattern: bytes) -> int:
        """Find the end of an XML block"""
        try:
            # Common XML ending patterns
            if pattern == b'<ebucore:ebuCoreMain':
                end_pattern = b'</ebucore:ebuCoreMain>'
            elif pattern == b'<BWFMetaEdit>':
                end_pattern = b'</BWFMetaEdit>'
            elif pattern == b'<ProTools':
                end_pattern = b'</ProTools>'
            elif pattern == b'<axml':
                end_pattern = b'</axml>'
            else:
                # Generic approach - look for end of root element
                # Find the root element name
                root_start = data.find(b'<', start_pos)
                if root_start == -1:
                    return -1
                root_end = data.find(b'>', root_start)
                if root_end == -1:
                    return -1
                
                # Extract root element name (handle attributes)
                root_element = data[root_start + 1:root_end].split(b' ')[0].split(b'\t')[0]
                end_pattern = b'</' + root_element + b'>'
            
            end_pos = data.find(end_pattern, start_pos)
            if end_pos != -1:
                return end_pos + len(end_pattern)
            
            # Fallback: look for next major chunk or end of file
            # Look for common WAV chunks that would indicate end of XML
            chunk_patterns = [b'data', b'fmt ', b'LIST', b'bext', b'PEAK']
            next_chunk = len(data)
            for chunk_pattern in chunk_patterns:
                chunk_pos = data.find(chunk_pattern, start_pos + 100)  # Skip immediate area
                if chunk_pos != -1 and chunk_pos < next_chunk:
                    next_chunk = chunk_pos
            
            return min(next_chunk, start_pos + 65536)  # Limit XML size to 64KB
            
        except Exception:
            return start_pos + 1024  # Fallback to small chunk
    
    def _get_xml_prefix(self, pattern: bytes) -> str:
        """Get prefix for XML metadata keys based on XML type"""
        if pattern == b'<ebucore:ebuCoreMain':
            return 'ebucore'
        elif pattern == b'<BWFMetaEdit>':
            return 'bwfmetaedit'
        elif pattern == b'<ProTools':
            return 'protools'
        elif pattern == b'<axml':
            return 'axml'
        else:
            return 'xml'
    
    def _parse_xml_content(self, xml_data: str) -> Dict:
        """Parse XML content and extract metadata"""
        metadata = {}
        
        try:
            # Clean up the XML data
            xml_data = xml_data.strip()
            
            # Handle XML declaration and encoding issues
            if not xml_data.startswith('<?xml'):
                xml_data = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_data
            
            # Parse with iterparse to handle large XML efficiently
            xml_io = io.StringIO(xml_data)
            
            try:
                # Try to parse as proper XML
                for event, elem in ET.iterparse(xml_io, events=("start", "end")):
                    if event == "end" and elem.text and elem.text.strip():
                        # Remove namespace prefix from tag name
                        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                        tag = tag.split(':')[-1]  # Remove namespace prefix
                        
                        # Clean and store the text content
                        text_content = self._sanitize_string(elem.text.strip())
                        if text_content and len(text_content) > 0:
                            metadata[tag] = text_content
                        
                        # Also extract attributes if they contain useful data
                        for attr_name, attr_value in elem.attrib.items():
                            if attr_value and attr_value.strip():
                                attr_key = f"{tag}_{attr_name}"
                                metadata[attr_key] = self._sanitize_string(attr_value.strip())
                
            except ET.ParseError:
                # If XML parsing fails, try to extract key-value pairs manually
                metadata = self._extract_xml_manually(xml_data)
                
        except Exception as e:
            print(f"Error parsing XML content: {e}")
        
        return metadata
    
    def _extract_xml_manually(self, xml_data: str) -> Dict:
        """Manually extract metadata from XML when parsing fails"""
        metadata = {}
        
        try:
            # Use regex to find tag-value pairs
            import re
            
            # Find simple tag patterns like <tag>value</tag>
            tag_pattern = r'<([^/>]+)>([^<]+)</[^>]+>'
            matches = re.findall(tag_pattern, xml_data)
            
            for tag_match, value_match in matches:
                # Clean tag name (remove namespaces and attributes)
                tag = re.sub(r'[^a-zA-Z0-9_].*', '', tag_match.split(':')[-1])
                value = self._sanitize_string(value_match.strip())
                
                if tag and value and len(value) > 0:
                    metadata[tag] = value
            
            # Also look for attribute patterns like attribute="value"
            attr_pattern = r'(\w+)="([^"]+)"'
            attr_matches = re.findall(attr_pattern, xml_data)
            
            for attr_name, attr_value in attr_matches:
                if attr_name and attr_value:
                    metadata[f"attr_{attr_name}"] = self._sanitize_string(attr_value)
                    
        except Exception as e:
            print(f"Error in manual XML extraction: {e}")
        
        return metadata
    
    def _sanitize_string(self, value: str) -> str:
        """Clean string data for metadata"""
        if value:
            # Replace tabs, newlines, and carriage returns with spaces
            cleaned = value.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
            # Remove non-printable characters
            cleaned = ''.join(char for char in cleaned if char.isprintable())
            # Collapse multiple spaces into single space and strip
            cleaned = ' '.join(cleaned.split())
            return cleaned
        return ""
    
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

class UCSProcessor:
    """Process Universal Category System (UCS) data for sound categorization"""
    
    def __init__(self):
        self.ucs_data = {}
        self.ucs_loaded = False
        self.load_ucs_data()
    
    def load_ucs_data(self):
        """Load UCS data from CSV file"""
        script_dir = Path(__file__).parent
        ucs_files = [
            script_dir / "data" / "UCS_v8.2.1_Full_List.csv",
            script_dir / "data" / "UCS_v8.2.0_Full_List.csv",
            script_dir / "data" / "UCS_Full_List.csv",
            script_dir / "UCS_v8.2.1_Full_List.csv",
            script_dir / "UCS_v8.2.0_Full_List.csv",
            script_dir / "UCS_Full_List.csv"
        ]
        
        for ucs_file in ucs_files:
            if ucs_file.exists():
                try:
                    with open(ucs_file, 'r', encoding='utf-8') as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            # Handle both old and new CSV formats
                            ucs_id = row.get('ID') or row.get('CatID') or row.get('CatShort', '')
                            full_name = row.get('FullName') or f"{row.get('Category', '')} {row.get('SubCategory', '')}".strip()
                            category = row.get('Category', '')
                            subcategory = row.get('SubCategory', '')
                            description = row.get('Description') or row.get('Explanations', '')
                            keywords_str = row.get('Keywords') or row.get('Synonyms - Comma Separated', '')
                            
                            if ucs_id and category:
                                self.ucs_data[ucs_id] = {
                                    'id': ucs_id,
                                    'full_name': full_name,
                                    'category': category,
                                    'subcategory': subcategory,
                                    'description': description,
                                    'keywords': [k.strip() for k in keywords_str.split(',') if k.strip()] if keywords_str else []
                                }
                    self.ucs_loaded = True
                    print(f"Loaded {len(self.ucs_data)} UCS categories from {ucs_file.name}")
                    break
                except Exception as e:
                    print(f"Warning: Could not load UCS file {ucs_file}: {e}")
        
        if not self.ucs_loaded:
            print("Warning: No UCS file found. UCS categorization will be disabled.")
    
    def categorize_sound(self, filename: str, description: str = "", allow_guess: bool = True) -> Dict:
        """Categorize sound based on filename and description"""
        if not self.ucs_loaded:
            return {}
        
        # First, check if filename starts with an exact UCS ID (common naming convention)
        # e.g., "AMBMisc_Hotel_Elevator_Ride.wav" starts with "AMBMisc"
        filename_no_ext = re.sub(r'\.(wav|wave)$', '', filename, flags=re.IGNORECASE)
        for ucs_id in self.ucs_data.keys():
            if filename_no_ext.startswith(ucs_id):
                # Exact UCS ID match found at the beginning of filename
                ucs_info = self.ucs_data[ucs_id]
                return {
                    'primary_category': {
                        'id': ucs_id,
                        'full_name': ucs_info['full_name'],
                        'category': ucs_info['category'],
                        'subcategory': ucs_info['subcategory'],
                        'score': 100.0  # Perfect match
                    }
                }
        
        # No exact ID match
        if not allow_guess:
            # If guessing is disabled, return empty result when exact ID isn't present
            return {}

        # proceed with text analysis
        # Combine filename and description for analysis
        text_to_analyze = f"{filename} {description}".lower()
        
        # Remove file extension and common separators
        text_to_analyze = re.sub(r'\.(wav|wave)$', '', text_to_analyze)
        text_to_analyze = re.sub(r'[_\-\.]', ' ', text_to_analyze)
        
        # Score each UCS category
        best_matches = []
        
        for ucs_id, ucs_info in self.ucs_data.items():
            score = self._calculate_match_score(text_to_analyze, ucs_info)
            if score > 0:
                best_matches.append((score, ucs_id, ucs_info))
        
        # Sort by score and return top matches
        best_matches.sort(reverse=True, key=lambda x: x[0])
        
        if best_matches:
            # Return best match and alternatives
            best_score, best_id, best_info = best_matches[0]
            
            result = {
                'primary_category': {
                    'id': best_id,
                    'full_name': best_info['full_name'],
                    'category': best_info['category'],
                    'subcategory': best_info['subcategory'],
                    'score': best_score
                }
            }
            
            # Add alternative matches if they're close in score
            alternatives = []
            for score, ucs_id, ucs_info in best_matches[1:6]:  # Top 5 alternatives
                if score >= best_score * 0.7:  # Within 70% of best score
                    alternatives.append({
                        'id': ucs_id,
                        'full_name': ucs_info['full_name'],
                        'category': ucs_info['category'],
                        'subcategory': ucs_info['subcategory'],
                        'score': score
                    })
            
            if alternatives:
                result['alternative_categories'] = alternatives
            
            return result
        
        return {}
    
    def _calculate_match_score(self, text: str, ucs_info: Dict) -> float:
        """Calculate match score between text and UCS category"""
        score = 0.0
        
        # Check full name match
        full_name = ucs_info['full_name'].lower()
        if full_name in text:
            score += 10.0
        
        # Check category and subcategory
        category = ucs_info['category'].lower()
        subcategory = ucs_info['subcategory'].lower()
        
        if category in text:
            score += 5.0
        if subcategory in text:
            score += 7.0
        
        # Check keywords
        for keyword in ucs_info['keywords']:
            keyword = keyword.strip().lower()
            if keyword and keyword in text:
                score += 3.0
        
        # Check word-level matches
        text_words = set(text.split())
        name_words = set(full_name.split())
        category_words = set(category.split())
        subcategory_words = set(subcategory.split())
        
        # Exact word matches get higher scores
        for word in text_words:
            if len(word) > 2:  # Skip very short words
                if word in name_words:
                    score += 2.0
                elif word in category_words:
                    score += 1.5
                elif word in subcategory_words:
                    score += 1.5
        
        # Partial word matches
        for text_word in text_words:
            if len(text_word) > 3:
                for name_word in name_words:
                    if len(name_word) > 3 and (text_word in name_word or name_word in text_word):
                        score += 0.5
        
        return score

class AAFGenerator:
    """Generate AAF files from WAV metadata using pyaaf2"""
    
    def __init__(self):
        self.app_name = f"WAVsToAAF v{__version__}"
    
    def create_aaf_file(self, wav_metadata: Dict, bext_metadata: Dict, info_metadata: Dict = None, 
                       xml_metadata: Dict = None, ucs_metadata: Dict = None, output_path: str = None,
                       fps: float = 24, embed_audio: bool = False, link_mode: str = 'import', 
                       relative_locators: bool = False) -> str:
        """Create AAF file from WAV, BEXT, INFO, XML, and UCS metadata using Avid-compatible structure"""
        
        try:
            # Get audio parameters - ensure they're integers
            try:
                channels = int(wav_metadata.get('channels', 1))
                sample_rate = int(wav_metadata.get('sample_rate', 48000))
                audio_frames = int(wav_metadata.get('frames', 0))
                sample_width = int(wav_metadata.get('sample_width', 2))
                bit_depth = int(sample_width * 8)
            except (ValueError, TypeError) as e:
                raise Exception(f"Invalid audio parameters: channels={wav_metadata.get('channels')}, "
                              f"sample_rate={wav_metadata.get('sample_rate')}, "
                              f"frames={wav_metadata.get('frames')}, "
                              f"sample_width={wav_metadata.get('sample_width')}: {e}")
            
            # Convert fps to int for AAF library (it does not accept floats)
            fps = int(fps)

            # Calculate video length at specified fps
            duration_seconds = audio_frames / sample_rate if sample_rate else 0
            video_length = int(duration_seconds * fps)
            
            with aaf2.open(output_path, 'w') as f:
                # Set file identification
                f.header['ObjectModelVersion'].value = 1
                f.header['Version'].value = {'major': 1, 'minor': 2}
                
                # Update product identification
                for ident in f.header['IdentificationList'].value:
                    ident['ProductName'].value = "WAVsToAAF"
                    ident['CompanyName'].value = "Jason Brodkey"
                    ident['ProductVersionString'].value = __version__
                    break
                
                # Choose linked structure
                # 'pcm' -> MC-exact file essence via PCMDescriptor (earlier variant that may avoid 1-by-1 prompts)
                # 'import' -> ImportDescriptor 3-tier structure (current default)
                use_mc_exact_linked = (str(link_mode).lower() == 'pcm')

                # Resolve path to WAV
                import_mob = f.create.SourceMob()
                from pathlib import Path
                wav_path = Path(wav_metadata.get('filepath', ''))
                if use_mc_exact_linked and wav_path.exists():
                    # Build one SourceMob per channel, with PCMDescriptor and file locators
                    source_mobs = []
                    abs_path = str(wav_path)
                    
                    # Only create URIs if not using relative locators
                    if not relative_locators:
                        file_uri = wav_path.as_uri()
                        file_url_localhost = f"file://localhost{wav_path.as_posix()}"

                    for ch_idx in range(channels):
                        source_mob = f.create.SourceMob()
                        source_mob.name = None  # MC leaves SourceMob names as None

                        pcm = f.create.PCMDescriptor()
                        pcm['SampleRate'].value = sample_rate
                        pcm['Length'].value = audio_frames
                        pcm['AudioSamplingRate'].value = sample_rate
                        pcm['Channels'].value = 1
                        pcm['QuantizationBits'].value = bit_depth
                        pcm['BlockAlign'].value = sample_width
                        pcm['AverageBPS'].value = sample_rate * sample_width
                        pcm['ContainerFormat'].value = f.dictionary.lookup_containerdef('AAF')
                        try:
                            codec = f.dictionary.lookup_codecdef('PCM')
                            pcm['CodecDefinition'].value = codec
                        except Exception:
                            pass

                        # Add locators - use relative if requested
                        if relative_locators:
                            relative_path = f"./{wav_path.name}"
                            loc = f.create.NetworkLocator(); loc['URLString'].value = relative_path; pcm['Locator'].append(loc)
                        else:
                            loc1 = f.create.NetworkLocator(); loc1['URLString'].value = file_uri; pcm['Locator'].append(loc1)
                            loc2 = f.create.NetworkLocator(); loc2['URLString'].value = file_url_localhost; pcm['Locator'].append(loc2)
                            loc3 = f.create.NetworkLocator(); loc3['URLString'].value = abs_path; pcm['Locator'].append(loc3)
                            loc4 = f.create.NetworkLocator(); loc4['URLString'].value = wav_path.name; pcm['Locator'].append(loc4)

                        source_mob.descriptor = pcm

                        # Create source slot at audio sample rate
                        src_slot = source_mob.create_timeline_slot(sample_rate)
                        src_slot.name = "Audio Slot"
                        src_slot.edit_rate = sample_rate

                        # Segment points directly to file essence: no SourceID/SourceMobSlotID
                        sclip = f.create.SourceClip()
                        sclip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        sclip['Length'].value = audio_frames
                        sclip['StartTime'].value = 0
                        src_slot.segment = sclip

                        source_mobs.append((source_mob, src_slot))

                    # Create MasterMob and wire channels
                    master_mob = f.create.MasterMob(str(wav_path.stem))
                    for ch_idx, (source_mob, src_slot) in enumerate(source_mobs, start=1):
                        mslot = master_mob.create_timeline_slot(sample_rate)
                        mslot.name = wav_metadata.get('filename', 'Unknown')
                        mslot.edit_rate = sample_rate
                        mclip = f.create.SourceClip()
                        mclip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        mclip['Length'].value = audio_frames
                        mclip['StartTime'].value = 0
                        mclip['SourceID'].value = source_mob.mob_id
                        mclip['SourceMobSlotID'].value = src_slot.slot_id
                        
                        # Apply pan based on source mob count
                        if len(source_mobs) == 2:
                            # Stereo: channel 1 = left (-1.0), channel 2 = right (1.0)
                            pan_value = -1.0 if ch_idx == 1 else 1.0
                            _apply_pan_to_slot(f, mslot, mclip, pan_value, audio_frames)
                        elif len(source_mobs) == 1:
                            # Mono: center pan (0.0)
                            _apply_pan_to_slot(f, mslot, mclip, 0.0, audio_frames)
                        else:
                            # Multi-channel (>2): no pan control
                            mslot.segment = mclip

                    # Add mobs to content (MC order: Master first, then sources)
                    f.content.mobs.append(master_mob)
                    for source_mob, _ in source_mobs:
                        f.content.mobs.append(source_mob)

                    # === Add metadata to MasterMob (same as below)
                    # BEXT metadata (prefixed)
                    if bext_metadata:
                        if bext_metadata.get('description'):
                            master_mob.comments['BEXT_Description'] = bext_metadata['description']
                        if bext_metadata.get('originator'):
                            master_mob.comments['BEXT_Originator'] = bext_metadata['originator']
                        if bext_metadata.get('originator_reference'):
                            master_mob.comments['BEXT_Originator_Reference'] = bext_metadata['originator_reference']
                        if bext_metadata.get('origination_date'):
                            master_mob.comments['BEXT_Origination_Date'] = bext_metadata['origination_date']
                        if bext_metadata.get('origination_time'):
                            master_mob.comments['BEXT_Origination_Time'] = bext_metadata['origination_time']
                        if bext_metadata.get('time_reference'):
                            master_mob.comments['BEXT_Time_Reference'] = str(bext_metadata['time_reference'])
                        if bext_metadata.get('umid'):
                            master_mob.comments['BEXT_UMID'] = bext_metadata['umid']

                    # INFO metadata (prefixed)
                    if info_metadata:
                        info_mappings = {
                            'IART': 'INFO_Artist','ICMT': 'INFO_Comment','ICOP': 'INFO_Copyright','ICRD': 'INFO_Creation_Date',
                            'IENG': 'INFO_Engineer','IGNR': 'INFO_Genre','IKEY': 'INFO_Keywords','INAM': 'INFO_Title',
                            'IPRD': 'INFO_Product','ISBJ': 'INFO_Subject','ISFT': 'INFO_Software','ISRC': 'INFO_Source'
                        }
                        for chunk_id, value in info_metadata.items():
                            if value:
                                master_mob.comments[info_mappings.get(chunk_id, f'INFO_{chunk_id}')] = str(value)

                    # UCS (prefixed) + clean names
                    if ucs_metadata and 'primary_category' in ucs_metadata:
                        category = ucs_metadata['primary_category']
                        master_mob.comments['UCS_Category'] = category['category']
                        master_mob.comments['UCS_SubCategory'] = category['subcategory']
                        master_mob.comments['UCS_ID'] = category['id']
                        master_mob.comments['UCS_Full_Name'] = category['full_name']
                        master_mob.comments['UCS_Match_Score'] = str(category['score'])
                        master_mob.comments['Category'] = category.get('category','')
                        master_mob.comments['SubCategory'] = category.get('subcategory','')
                        master_mob.comments['UCS ID'] = category.get('id','')

                    # Clean Avid fields
                    if bext_metadata and bext_metadata.get('description'):
                        master_mob.comments['Description'] = bext_metadata['description']
                    elif info_metadata and 'INAM' in info_metadata:
                        master_mob.comments['Description'] = str(info_metadata.get('INAM'))
                    master_mob.comments['Name'] = str(wav_path.stem)
                    master_mob.comments['Filename'] = str(wav_path.name)
                    master_mob.comments['FilePath'] = str(wav_path)
                    master_mob.comments['SampleRate'] = str(sample_rate)
                    master_mob.comments['BitDepth'] = str(bit_depth)
                    master_mob.comments['Channels'] = str(channels)
                    master_mob.comments['Number of Frames'] = str(audio_frames)
                    master_mob.comments['AudioFormat'] = 'WAV'
                    master_mob.comments['Tracks'] = 'A1' if channels==1 else ('A1A2' if channels==2 else f"A1A{channels}")
                    master_mob.comments['Duration'] = f"{duration_seconds:.3f}"
                    if info_metadata and 'IKEY' in info_metadata:
                        master_mob.comments['Keywords'] = str(info_metadata['IKEY'])
                    if bext_metadata:
                        if bext_metadata.get('originator'):
                            master_mob.comments['Originator'] = bext_metadata['originator']
                        if bext_metadata.get('originator_reference'):
                            master_mob.comments['OriginatorReference'] = bext_metadata['originator_reference']
                        if bext_metadata.get('origination_date'):
                            master_mob.comments['Origination Date'] = bext_metadata['origination_date']
                        if bext_metadata.get('origination_time'):
                            master_mob.comments['Origination Time'] = bext_metadata['origination_time']
                    master_mob.comments['Start'] = "00:00:00:00"
                    master_mob.comments['End'] = "00:00:00:00"
                    # Tape field - set to directory name for batch import consistency
                    tape_name = Path(wav_path).parent.name if wav_path else "Unknown"
                    master_mob.comments['Tape'] = tape_name
                    master_mob.comments['Scene'] = ""
                    master_mob.comments['Take'] = ""

                    return output_path
                else:
                    # === 1. Create ImportDescriptor SourceMob ===
                    import_mob = f.create.SourceMob()
                    import_mob.name = wav_metadata.get('filename', 'Unknown')
                    # Set deterministic UMID for consistent batch import behavior
                    import_mob.mob_id = create_deterministic_umid(wav_path, "import")

                    # Create ImportDescriptor and add multiple locators
                    import_desc = f.create.ImportDescriptor()
                    if wav_path.exists():
                        if relative_locators:
                            # Use relative paths according to AAF Edit Protocol spec
                            # Base URI is determined from the AAF file location
                            relative_path = f"./{wav_path.name}"  # "./filename.wav"
                            locs_to_add = [relative_path]
                            print(f"  Using relative locator: {relative_path}")
                        else:
                            # Provide multiple URL variants that MC can resolve with a single folder choice.
                            # Avoid TextLocator to prevent "Error with media reference" warnings.
                            from urllib.parse import quote
                            abs_posix = wav_path.as_posix()
                            # Avid-style volume-prefixed URL tends to show best in UI
                            avid_locator_url = f"file:///Macintosh%20HD{quote(abs_posix)}"
                            file_url_users = f"file://{quote(abs_posix)}"            # file:///Users/...
                            file_url_localhost = f"file://localhost{quote(abs_posix)}"  # file://localhost/Users/...
                            abs_path = abs_posix                                      # /Users/...
                            filename_only = wav_path.name                              # bare filename

                            # Order: Avid volume URL first to help MC UI prefill; then common variants
                            locs_to_add = [avid_locator_url, file_url_users, file_url_localhost, abs_path, filename_only]

                        for url in locs_to_add:
                            try:
                                nl = f.create.NetworkLocator(); nl['URLString'].value = url; import_desc['Locator'].append(nl)
                            except Exception:
                                pass

                    import_mob.descriptor = import_desc

                    # Add slots to ImportDescriptor - Avid expects: Ch1, Timecode, Ch2, Ch3...
                    if channels == 1:
                        # Mono: just add audio slot and timecode
                        slot = import_mob.create_timeline_slot(fps)
                        clip = f.create.SourceClip()
                        clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        clip['Length'].value = video_length
                        clip['StartTime'].value = 0
                        slot.segment = clip
                        slot.name = wav_metadata.get('filename', 'Unknown')

                        # Timecode slot
                        tc_slot = import_mob.create_timeline_slot(fps)
                        tc = f.create.Timecode(length=video_length)
                        tc['Start'].value = 0
                        tc['FPS'].value = fps
                        tc_slot.segment = tc
                    else:
                        # Stereo/Multi: Ch1, then Timecode, then remaining channels
                        # First channel
                        slot1 = import_mob.create_timeline_slot(fps)
                        clip1 = f.create.SourceClip()
                        clip1['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        clip1['Length'].value = video_length
                        clip1['StartTime'].value = 0
                        slot1.segment = clip1
                        slot1.name = wav_metadata.get('filename', 'Unknown')

                        # Timecode slot (slot 2)
                        tc_slot = import_mob.create_timeline_slot(fps)
                        tc = f.create.Timecode(length=video_length)
                        tc['Start'].value = 0
                        tc['FPS'].value = fps
                        tc_slot.segment = tc

                        # Remaining channels
                        for ch_idx in range(1, channels):
                            slot = import_mob.create_timeline_slot(fps)
                            clip = f.create.SourceClip()
                            clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                            clip['Length'].value = video_length
                            clip['StartTime'].value = 0
                            slot.segment = clip
                            slot.name = wav_metadata.get('filename', 'Unknown')

                    # Defer appending mobs to control content order later

                    # === 2. Recreate Avid export chain: WAVEDescriptor SourceMob -> ImportDescriptor SourceMob ===
                    # Build intermediate WAVEDescriptor SourceMob with one slot per channel
                    wave_mob = f.create.SourceMob()
                    wave_mob.name = wav_metadata.get('filename', 'Unknown')  # Avid uses original filename
                    # Set deterministic UMID for consistent batch import behavior
                    wave_mob.mob_id = create_deterministic_umid(wav_path, "wave")

                    # prepare channel_mobs list (may get filled by per-channel embedding)
                    channel_mobs = []

                    if embed_audio:
                        # If user asked for per-channel embedding (default when multi-channel),
                        # create one SourceMob per channel and import each mono channel separately.
                        # Multi-channel WAVs will be split into per-channel mono files and each channel embedded separately.
                        if channels > 1:
                            # Split channels into temp mono files and import each into its own SourceMob
                            import tempfile, os, wave as _wave
                            tmp_paths = []
                            try:
                                with _wave.open(str(wav_path), 'rb') as r:
                                    nch = r.getnchannels()
                                    sampwidth = r.getsampwidth()
                                    fr = r.getframerate()
                                    nframes = r.getnframes()
                                    raw = r.readframes(nframes)
                                # reveal low-level values for problematic files (only in debug runs)

                                # build per-channel byte streams
                                bytes_per_frame = sampwidth * nch
                                channels_data = [bytearray() for _ in range(nch)]
                                for i in range(nframes):
                                    off = i * bytes_per_frame
                                    for c in range(nch):
                                        start = off + c * sampwidth
                                        channels_data[c].extend(raw[start:start+sampwidth])

                                # write temp mono files and import into per-channel SourceMobs
                                # report per-channel data lengths before writing (for debugging)
                                for idx, chdata in enumerate(channels_data, start=1):
                                    tmp = tempfile.NamedTemporaryFile(prefix=f"{wav_metadata.get('filename','tmp')}_ch{idx}_", suffix='.wav', delete=False)
                                    tmp_paths.append(tmp.name)
                                    tmp.close()
                                    try:
                                        with _wave.open(tmp.name,'wb') as w:
                                            w.setnchannels(1)
                                            w.setsampwidth(sampwidth)
                                            w.setframerate(fr)
                                            w.writeframes(bytes(chdata))
                                    except Exception as write_exc:
                                        # Failed to write temp WAV - surface the error
                                        print(f"  Failed to write temp WAV {tmp.name}: {write_exc}")
                                        # re-raise so the import step will fail and be reported
                                        raise

                                    # create a SourceMob and import the channel essence
                                    phys_mob = f.create.SourceMob(f"{wav_metadata.get('filename','Unknown')}.PHYS.ch{idx}")
                                    # Validate temp wav before passing to import_audio_essence to help diagnose EOF issues
                                    try:
                                        size = os.path.getsize(tmp.name)
                                        # quick wave sanity check
                                        try:
                                            with _wave.open(tmp.name, 'rb') as tcheck:
                                                params = (tcheck.getnchannels(), tcheck.getsampwidth(), tcheck.getframerate(), tcheck.getnframes())
                                        except Exception as e:
                                            # If the wave module can't read it, capture header and raise
                                            with open(tmp.name, 'rb') as fh:
                                                head = fh.read(256)
                                            raise Exception(f"Temp WAV invalid (size={size}): wave.open failed: {e}; header={head[:64]!r}")

                                        # Also try aaf2's WaveReader as an early check
                                        try:
                                            from aaf2 import audio as _audio
                                            _wr = _audio.WaveReader(tmp.name)
                                            _wr.close()
                                        except Exception as e:
                                            raise Exception(f"aaf2 WaveReader failed on temp WAV: {e}")

                                    except Exception as diag_exc:
                                        # Provide extra diagnostic info if import fails later
                                        print(f"  Temp WAV diagnostics failed for {tmp.name}: {diag_exc}")
                                    # Now import into the mob
                                    phys_mob.import_audio_essence(tmp.name, edit_rate=sample_rate)
                                    channel_mobs.append(phys_mob)

                            finally:
                                # cleanup temp files
                                for p in tmp_paths:
                                    try:
                                        os.unlink(p)
                                    except Exception:
                                        pass
                        else:
                            # Use the library helper to import WAV essence directly into the AAF
                            # This will create a PCMDescriptor, EssenceData and write frames into the file.
                            try:
                                # import_audio_essence expects a path and will write essence into the file
                                # The returned source_slot contains descriptor and slot length info
                                source_slot = wave_mob.import_audio_essence(str(wav_path), edit_rate=sample_rate)
                                # descriptor and essence data have been attached to wave_mob by the helper
                                channel_mobs.append(wave_mob)
                            except Exception as e:
                                # If embedding fails for any reason, surface the error so we can fall back or diagnose
                                raise Exception(f"Embedding failed using import_audio_essence: {e}")
                    else:
                        wave_desc = f.create.WAVEDescriptor()
                        wave_desc['SampleRate'].value = sample_rate
                        wave_desc['Length'].value = audio_frames
                        # Match Avid exported ContainerFormat (OMF rather than AAF for linked media)
                        try:
                            wave_desc['ContainerFormat'].value = f.dictionary.lookup_containerdef('OMF')
                        except Exception:
                            wave_desc['ContainerFormat'].value = f.dictionary.lookup_containerdef('AAF')

                    if not embed_audio:
                        # Minimal RIFF summary (same as before)
                        summary = bytearray()
                        summary.extend(b'RIFF'); summary.extend(struct.pack('<I', 0)); summary.extend(b'WAVE')
                        summary.extend(b'fmt '); summary.extend(struct.pack('<I', 16)); summary.extend(struct.pack('<H', 1))
                        summary.extend(struct.pack('<H', channels)); summary.extend(struct.pack('<I', int(sample_rate)))
                        bytes_per_sec = int(sample_rate * sample_width * channels)
                        summary.extend(struct.pack('<I', bytes_per_sec))
                        summary.extend(struct.pack('<H', int(sample_width * channels)))
                        summary.extend(struct.pack('<H', int(bit_depth)))
                        summary.extend(b'data'); summary.extend(struct.pack('<I', int(audio_frames * sample_width * channels)))
                        wave_desc['Summary'].value = bytes(summary)

                        # Also add locators to WAVEDescriptor (some MC versions consult these for batch prefill)
                        try:
                            if wav_path.exists() and 'Locator' in wave_desc.keys():
                                if relative_locators:
                                    # Use relative path for WAVEDescriptor
                                    relative_path = f"./{wav_path.name}"
                                    nl = f.create.NetworkLocator(); nl['URLString'].value = relative_path; wave_desc['Locator'].append(nl)
                                else:
                                    from urllib.parse import quote
                                    abs_posix = wav_path.as_posix()
                                    avid_locator_url = f"file:///Macintosh%20HD{quote(abs_posix)}"
                                    file_url_users = f"file://{quote(abs_posix)}"
                                    file_url_localhost = f"file://localhost{quote(abs_posix)}"
                                    abs_path = abs_posix
                                    filename_only = wav_path.name
                                    for url in [avid_locator_url, file_url_users, file_url_localhost, abs_path, filename_only]:
                                        try:
                                            nl = f.create.NetworkLocator(); nl['URLString'].value = url; wave_desc['Locator'].append(nl)
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                        wave_mob.descriptor = wave_desc

                        # Create slots on WAVEDescriptor referencing ImportDescriptor channel slots
                        # ImportDescriptor slot layout: mono has [1:audio, 2:tc], stereo has [1:ch1, 2:tc, 3:ch2, ...]
                        for ch_idx in range(channels):
                            wslot = wave_mob.create_timeline_slot(fps)
                            wclip = f.create.SourceClip()
                            wclip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                            wclip['Length'].value = video_length
                            wclip['StartTime'].value = 0
                            wclip['SourceID'].value = import_mob.mob_id
                            # Map to ImportDescriptor slot: ch1=slot1, ch2=slot3, ch3=slot4, etc. (skip slot 2 which is timecode)
                            import_slot_id = 1 if ch_idx == 0 else (ch_idx + 2)
                            wclip['SourceMobSlotID'].value = import_slot_id
                            wslot.segment = wclip
                        # linked case: this WAVEDescriptor represents all channels in this single SourceMob
                        channel_mobs = [wave_mob]
                    else:
                        # For embedded audio we used import_audio_essence() which created the descriptor and
                        # essence and also created a timeline slot on the SourceMob. No additional WAVEDescriptor
                        # or channel slot setup is necessary here.
                        pass
                
                # (Embedding handled above via import_audio_essence())
                
                # === 3. Create MasterMob ===
                master_mob = f.create.MasterMob()
                master_mob.name = Path(wav_metadata.get('filename', 'Unknown')).stem
                # Set deterministic UMID for consistent batch import behavior
                master_mob.mob_id = create_deterministic_umid(wav_path, "master")
                
                # MasterMob slots - adjust edit rate and length based on embedded vs linked
                master_edit_rate = sample_rate if embed_audio else fps
                master_length = audio_frames if embed_audio else video_length
                
                # MasterMob slot layout — one master slot per channel (linked or per-channel embedded)
                for ch_idx in range(channels):
                        mslot = master_mob.create_timeline_slot(master_edit_rate)
                        mclip = f.create.SourceClip()
                        mclip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        mclip['Length'].value = master_length
                        mclip['StartTime'].value = 0
                        # pick source mob for this channel (per-channel phys mobs OR single wave_mob)
                        src_mob = channel_mobs[ch_idx] if ch_idx < len(channel_mobs) else channel_mobs[0]
                        mclip['SourceID'].value = src_mob.mob_id
                        # determine slot mapping depending on how channels were stored
                        if embed_audio and channels > 1:
                            # each channel was embedded into its own SourceMob; its slot id will be 1
                            mclip['SourceMobSlotID'].value = 1
                        elif not embed_audio:
                            # linked WAVEDescriptor has one slot per channel (ch1=1, ch2=3, ...)
                            mclip['SourceMobSlotID'].value = ch_idx + 1
                        else:
                            # embedded single-channel or other cases use slot 1
                            mclip['SourceMobSlotID'].value = 1
                        
                        # Apply pan based on source mob count
                        if len(channel_mobs) == 2:
                            # Stereo: channel 1 = left (-1.0), channel 2 = right (1.0)
                            pan_value = -1.0 if ch_idx == 0 else 1.0
                            _apply_pan_to_slot(f, mslot, mclip, pan_value, master_length)
                        elif len(channel_mobs) == 1:
                            # Mono: center pan (0.0)
                            _apply_pan_to_slot(f, mslot, mclip, 0.0, master_length)
                        else:
                            # Multi-channel (>2): no pan control
                            mslot.segment = mclip
                        
                        mslot.name = wav_metadata.get('filename', 'Unknown')
                
                # === 4. Add metadata to MasterMob ===
                # Add BEXT metadata as comments (prefixed for storage)
                if bext_metadata:
                    if bext_metadata.get('description'):
                        master_mob.comments['BEXT_Description'] = bext_metadata['description']
                    if bext_metadata.get('originator'):
                        master_mob.comments['BEXT_Originator'] = bext_metadata['originator']
                    if bext_metadata.get('originator_reference'):
                        master_mob.comments['BEXT_Originator_Reference'] = bext_metadata['originator_reference']
                    if bext_metadata.get('origination_date'):
                        master_mob.comments['BEXT_Origination_Date'] = bext_metadata['origination_date']
                    if bext_metadata.get('origination_time'):
                        master_mob.comments['BEXT_Origination_Time'] = bext_metadata['origination_time']
                    if bext_metadata.get('time_reference'):
                        master_mob.comments['BEXT_Time_Reference'] = str(bext_metadata['time_reference'])
                    if bext_metadata.get('umid'):
                        master_mob.comments['BEXT_UMID'] = bext_metadata['umid']
                
                # Add INFO metadata as comments (prefixed for storage)
                if info_metadata:
                    info_mappings = {
                        'IART': 'INFO_Artist',
                        'ICMT': 'INFO_Comment',
                        'ICOP': 'INFO_Copyright',
                        'ICRD': 'INFO_Creation_Date',
                        'IENG': 'INFO_Engineer',
                        'IGNR': 'INFO_Genre',
                        'IKEY': 'INFO_Keywords',
                        'INAM': 'INFO_Title',
                        'IPRD': 'INFO_Product',
                        'ISBJ': 'INFO_Subject',
                        'ISFT': 'INFO_Software',
                        'ISRC': 'INFO_Source'
                    }
                    
                    for chunk_id, value in info_metadata.items():
                        if value:
                            comment_key = info_mappings.get(chunk_id, f'INFO_{chunk_id}')
                            master_mob.comments[comment_key] = str(value)
                
                # Add UCS category information (prefixed for storage)
                if ucs_metadata and 'primary_category' in ucs_metadata:
                    category = ucs_metadata['primary_category']
                    master_mob.comments['UCS_Category'] = category['category']
                    master_mob.comments['UCS_SubCategory'] = category['subcategory']
                    master_mob.comments['UCS_ID'] = category['id']
                    master_mob.comments['UCS_Full_Name'] = category['full_name']
                    master_mob.comments['UCS_Match_Score'] = str(category['score'])
                
                # Add Avid-compatible fields (clean names that appear in Media Composer)
                # Description field
                if bext_metadata and bext_metadata.get('description'):
                    master_mob.comments['Description'] = bext_metadata['description']
                elif info_metadata and 'INAM' in info_metadata:
                    master_mob.comments['Description'] = str(info_metadata.get('INAM'))
                
                # File info (matching ALE column names)
                master_mob.comments['Name'] = str(wav_path.stem)  # ALE clip name (no extension)
                master_mob.comments['Filename'] = str(wav_path.name)
                master_mob.comments['FilePath'] = str(wav_path)
                master_mob.comments['SampleRate'] = str(sample_rate)
                master_mob.comments['BitDepth'] = str(bit_depth)
                master_mob.comments['Channels'] = str(channels)
                master_mob.comments['Number of Frames'] = str(audio_frames)
                
                # Audio format and track info
                master_mob.comments['AudioFormat'] = 'WAV'
                if channels == 1:
                    master_mob.comments['Tracks'] = 'A1'
                elif channels == 2:
                    master_mob.comments['Tracks'] = 'A1A2'
                else:
                    master_mob.comments['Tracks'] = f"A1A{channels}"
                
                # Duration in seconds
                master_mob.comments['Duration'] = f"{duration_seconds:.3f}"
                
                # Additional INFO fields (clean names)
                if info_metadata:
                    if 'IKEY' in info_metadata:
                        master_mob.comments['Keywords'] = str(info_metadata['IKEY'])
                
                # Additional BEXT fields (clean names)
                if bext_metadata:
                    if bext_metadata.get('originator'):
                        master_mob.comments['Originator'] = bext_metadata['originator']
                    if bext_metadata.get('originator_reference'):
                        master_mob.comments['OriginatorReference'] = bext_metadata['originator_reference']
                    if bext_metadata.get('origination_date'):
                        master_mob.comments['Origination Date'] = bext_metadata['origination_date']
                    if bext_metadata.get('origination_time'):
                        master_mob.comments['Origination Time'] = bext_metadata['origination_time']
                
                # Category and SubCategory (clean names for Avid)
                if ucs_metadata and 'primary_category' in ucs_metadata:
                    category = ucs_metadata['primary_category']
                    master_mob.comments['Category'] = category.get('category', '')
                    master_mob.comments['SubCategory'] = category.get('subcategory', '')
                    master_mob.comments['UCS ID'] = category.get('id', '')
                
                # Timecode fields - get from XML metadata if available
                timecode_str = None
                if xml_metadata and 'timecode' in xml_metadata:
                    timecode_str = xml_metadata['timecode']
                
                if timecode_str:
                    start_tc = timecode_str
                    # Calculate end timecode
                    total_frames = int(audio_frames / sample_rate * fps)
                    tc_parts = timecode_str.split(':')
                    if len(tc_parts) == 4:
                        start_frames = (int(tc_parts[0]) * 3600 * fps + 
                                      int(tc_parts[1]) * 60 * fps + 
                                      int(tc_parts[2]) * fps + 
                                      int(tc_parts[3]))
                        end_frames = start_frames + total_frames
                        end_tc = f"{end_frames//(3600*fps):02d}:{(end_frames%(3600*fps))//(60*fps):02d}:{(end_frames%(60*fps))//fps:02d}:{end_frames%fps:02d}"
                        master_mob.comments['Start'] = start_tc
                        master_mob.comments['StartTC_24fps'] = start_tc
                        master_mob.comments['End'] = end_tc
                    else:
                        master_mob.comments['Start'] = "00:00:00:00"
                        master_mob.comments['End'] = "00:00:00:00"
                else:
                    master_mob.comments['Start'] = "00:00:00:00"
                    master_mob.comments['End'] = "00:00:00:00"
                
                # Tape field - set to directory name for batch import consistency
                tape_name = Path(wav_path).parent.name if wav_path else "Unknown"
                master_mob.comments['Tape'] = tape_name
                
                # Scene and Take (empty by default, can be populated from filename parsing if needed)
                master_mob.comments['Scene'] = ""
                master_mob.comments['Take'] = ""
                
                # Add mobs to content based on embed_audio setting
                if embed_audio:
                    # Embedded: one PCM SourceMob per channel (created earlier) + MasterMob
                    for cm in channel_mobs:
                        # avoid re-appending if already attached
                        if cm not in f.content.mobs:
                            f.content.mobs.append(cm)
                    f.content.mobs.append(master_mob)
                else:
                    # Linked: WAVEDescriptor SourceMob, MasterMob, ImportDescriptor SourceMob
                    f.content.mobs.append(channel_mobs[0])  # WAVE mob
                    f.content.mobs.append(master_mob)
                    f.content.mobs.append(import_mob)
                
                return output_path
                
        except Exception as e:
            # Raise with full traceback to make debugging failing files much easier
            import traceback
            tb = traceback.format_exc()
            msg = f"Error creating AAF file: {e}\nFull traceback:\n{tb}"
            raise Exception(msg)

    def create_multi_aaf(self, wav_entries: List[Dict[str, Dict]], output_path: str,
                         fps: float = 24, embed_audio: bool = False, link_mode: str = 'import') -> str:
        """Create a single AAF that contains multiple master clips (one per WAV entry).
        
        Note: Embedded audio is not supported for multi-clip AAFs due to file size concerns.

        wav_entries: list of dicts with keys: wav_metadata, bext_metadata, info_metadata, xml_metadata, ucs_metadata
        """
        if embed_audio:
            raise ValueError("Multi-clip AAFs with embedded audio are not supported due to file size concerns. Use linked mode instead.")
            
        try:
            fps = int(fps)
            with aaf2.open(output_path, 'w') as f:
                # Set file identification
                f.header['ObjectModelVersion'].value = 1
                f.header['Version'].value = {'major': 1, 'minor': 2}
                for ident in f.header['IdentificationList'].value:
                    ident['ProductName'].value = "WAVsToAAF"
                    ident['CompanyName'].value = "Jason Brodkey"
                    ident['ProductVersionString'].value = __version__
                    break

                for entry in wav_entries:
                    wav_metadata = entry.get('wav_metadata', {})
                    bext_metadata = entry.get('bext_metadata', {})
                    info_metadata = entry.get('info_metadata', {})
                    xml_metadata = entry.get('xml_metadata', {})
                    ucs_metadata = entry.get('ucs_metadata', {})

                    # Audio params
                    channels = int(wav_metadata.get('channels', 1))
                    sample_rate = int(wav_metadata.get('sample_rate', 48000))
                    audio_frames = int(wav_metadata.get('frames', 0))
                    sample_width = int(wav_metadata.get('sample_width', 2))
                    bit_depth = int(sample_width * 8)
                    duration_seconds = audio_frames / sample_rate if sample_rate else 0
                    # Use sample_rate as timeline edit rate for audio AAF (spec-compliant)
                    timeline_edit_rate = sample_rate
                    clip_length = audio_frames

                    # Resolve path
                    from pathlib import Path
                    wav_path = Path(wav_metadata.get('filepath', ''))

                    # Currently support 'import' mode for multi-clip AAF. 'pcm' can be added if needed.
                    # 1) ImportDescriptor SourceMob
                    import_mob = f.create.SourceMob()
                    import_mob.name = wav_metadata.get('filename', 'Unknown')
                    # Set deterministic UMID for consistent batch import behavior
                    import_mob.mob_id = create_deterministic_umid(wav_path, "import")
                    import_desc = f.create.ImportDescriptor()
                    if wav_path.exists():
                        from urllib.parse import quote
                        abs_posix = wav_path.as_posix()
                        file_url_users = f"file://{quote(abs_posix)}"
                        file_url_localhost = f"file://localhost{quote(abs_posix)}"
                        abs_path = abs_posix
                        filename_only = wav_path.name
                        loc1 = f.create.NetworkLocator(); loc1['URLString'].value = file_url_users; import_desc['Locator'].append(loc1)
                        loc2 = f.create.NetworkLocator(); loc2['URLString'].value = file_url_localhost; import_desc['Locator'].append(loc2)
                        loc3 = f.create.NetworkLocator(); loc3['URLString'].value = abs_path; import_desc['Locator'].append(loc3)
                        loc4 = f.create.NetworkLocator(); loc4['URLString'].value = filename_only; import_desc['Locator'].append(loc4)
                    import_mob.descriptor = import_desc

                    # Import slots
                    if channels == 1:
                        slot = import_mob.create_timeline_slot(timeline_edit_rate)
                        clip = f.create.SourceClip()
                        clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        clip['Length'].value = clip_length
                        clip['StartTime'].value = 0
                        slot.segment = clip
                        slot.name = wav_metadata.get('filename', 'Unknown')
                        tc_slot = import_mob.create_timeline_slot(timeline_edit_rate)
                        tc = f.create.Timecode(length=clip_length)
                        tc['Start'].value = 0
                        tc['FPS'].value = timeline_edit_rate  # Use timeline rate for timecode
                        tc_slot.segment = tc
                    else:
                        slot1 = import_mob.create_timeline_slot(timeline_edit_rate)
                        clip1 = f.create.SourceClip()
                        clip1['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        clip1['Length'].value = clip_length
                        clip1['StartTime'].value = 0
                        slot1.segment = clip1
                        slot1.name = wav_metadata.get('filename', 'Unknown')
                        tc_slot = import_mob.create_timeline_slot(timeline_edit_rate)
                        tc = f.create.Timecode(length=clip_length)
                        tc['Start'].value = 0
                        tc['FPS'].value = timeline_edit_rate
                        tc_slot.segment = tc
                        for ch_idx in range(1, channels):
                            slot = import_mob.create_timeline_slot(timeline_edit_rate)
                            clip = f.create.SourceClip()
                            clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                            clip['Length'].value = clip_length
                            clip['StartTime'].value = 0
                            slot.segment = clip
                            slot.name = wav_metadata.get('filename', 'Unknown')

                    # 2) WAVEDescriptor SourceMob
                    wave_mob = f.create.SourceMob()
                    wave_mob.name = wav_metadata.get('filename', 'Unknown')
                    # Set deterministic UMID for consistent batch import behavior
                    wave_mob.mob_id = create_deterministic_umid(wav_path, "wave")
                    wave_desc = f.create.WAVEDescriptor()
                    wave_desc['SampleRate'].value = sample_rate
                    wave_desc['Length'].value = audio_frames
                    try:
                        wave_desc['ContainerFormat'].value = f.dictionary.lookup_containerdef('OMF')
                    except Exception:
                        wave_desc['ContainerFormat'].value = f.dictionary.lookup_containerdef('AAF')
                    summary = bytearray()
                    summary.extend(b'RIFF'); summary.extend(struct.pack('<I', 0)); summary.extend(b'WAVE')
                    summary.extend(b'fmt '); summary.extend(struct.pack('<I', 16)); summary.extend(struct.pack('<H', 1))
                    summary.extend(struct.pack('<H', channels)); summary.extend(struct.pack('<I', int(sample_rate)))
                    bytes_per_sec = int(sample_rate * sample_width * channels)
                    summary.extend(struct.pack('<I', bytes_per_sec))
                    summary.extend(struct.pack('<H', int(sample_width * channels)))
                    summary.extend(struct.pack('<H', int(bit_depth)))
                    summary.extend(b'data'); summary.extend(struct.pack('<I', int(audio_frames * sample_width * channels)))
                    wave_desc['Summary'].value = bytes(summary)
                    wave_mob.descriptor = wave_desc
                    channel_mobs = [wave_mob]
                    for ch_idx in range(channels):
                        wslot = wave_mob.create_timeline_slot(timeline_edit_rate)
                        wclip = f.create.SourceClip()
                        wclip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        wclip['Length'].value = clip_length
                        wclip['StartTime'].value = 0
                        wclip['SourceID'].value = import_mob.mob_id
                        import_slot_id = 1 if ch_idx == 0 else (ch_idx + 2)
                        wclip['SourceMobSlotID'].value = import_slot_id
                        wslot.segment = wclip

                    # 3) MasterMob
                    master_mob = f.create.MasterMob()
                    master_mob.name = Path(wav_metadata.get('filename', 'Unknown')).stem
                    # Set deterministic UMID for consistent batch import behavior
                    master_mob.mob_id = create_deterministic_umid(wav_path, "master")
                    for ch_idx in range(channels):
                        mslot = master_mob.create_timeline_slot(timeline_edit_rate)
                        mclip = f.create.SourceClip()
                        mclip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                        mclip['Length'].value = clip_length
                        mclip['StartTime'].value = 0
                        mclip['SourceID'].value = wave_mob.mob_id
                        mclip['SourceMobSlotID'].value = ch_idx + 1
                        
                        # Apply pan based on channel count (WAVE descriptor mode)
                        if channels == 2:
                            # Stereo: channel 0 = left (-1.0), channel 1 = right (1.0)
                            pan_value = -1.0 if ch_idx == 0 else 1.0
                            _apply_pan_to_slot(f, mslot, mclip, pan_value, clip_length)
                        elif channels == 1:
                            # Mono: center pan (0.0)
                            _apply_pan_to_slot(f, mslot, mclip, 0.0, clip_length)
                        else:
                            # Multi-channel (>2): no pan control
                            mslot.segment = mclip
                        
                        mslot.name = wav_metadata.get('filename', 'Unknown')

                    # 4) Metadata on MasterMob
                    if bext_metadata:
                        if bext_metadata.get('description'):
                            master_mob.comments['BEXT_Description'] = bext_metadata['description']
                        if bext_metadata.get('originator'):
                            master_mob.comments['BEXT_Originator'] = bext_metadata['originator']
                        if bext_metadata.get('originator_reference'):
                            master_mob.comments['BEXT_Originator_Reference'] = bext_metadata['originator_reference']
                        if bext_metadata.get('origination_date'):
                            master_mob.comments['BEXT_Origination_Date'] = bext_metadata['origination_date']
                        if bext_metadata.get('origination_time'):
                            master_mob.comments['BEXT_Origination_Time'] = bext_metadata['origination_time']
                        if bext_metadata.get('time_reference'):
                            master_mob.comments['BEXT_Time_Reference'] = str(bext_metadata['time_reference'])
                        if bext_metadata.get('umid'):
                            master_mob.comments['BEXT_UMID'] = bext_metadata['umid']
                    if info_metadata:
                        info_mappings = {
                            'IART': 'INFO_Artist','ICMT': 'INFO_Comment','ICOP': 'INFO_Copyright','ICRD': 'INFO_Creation_Date',
                            'IENG': 'INFO_Engineer','IGNR': 'INFO_Genre','IKEY': 'INFO_Keywords','INAM': 'INFO_Title',
                            'IPRD': 'INFO_Product','ISBJ': 'INFO_Subject','ISFT': 'INFO_Software','ISRC': 'INFO_Source'
                        }
                        for chunk_id, value in info_metadata.items():
                            if value:
                                master_mob.comments[info_mappings.get(chunk_id, f'INFO_{chunk_id}')] = str(value)
                    if ucs_metadata and 'primary_category' in ucs_metadata:
                        category = ucs_metadata['primary_category']
                        master_mob.comments['UCS_Category'] = category.get('category','')
                        master_mob.comments['UCS_SubCategory'] = category.get('subcategory','')
                        master_mob.comments['UCS_ID'] = category.get('id','')
                        master_mob.comments['UCS_Full_Name'] = category.get('full_name','')
                        master_mob.comments['UCS_Match_Score'] = str(category.get('score',''))
                        master_mob.comments['Category'] = category.get('category','')
                        master_mob.comments['SubCategory'] = category.get('subcategory','')
                        master_mob.comments['UCS ID'] = category.get('id','')
                    if bext_metadata and bext_metadata.get('description'):
                        master_mob.comments['Description'] = bext_metadata['description']
                    elif info_metadata and 'INAM' in info_metadata:
                        master_mob.comments['Description'] = str(info_metadata.get('INAM'))
                    master_mob.comments['Name'] = str(Path(wav_metadata.get('filename','Unknown')).stem)
                    master_mob.comments['Filename'] = str(Path(wav_metadata.get('filename','Unknown')).name)
                    master_mob.comments['FilePath'] = str(wav_path)
                    master_mob.comments['SampleRate'] = str(sample_rate)
                    master_mob.comments['BitDepth'] = str(bit_depth)
                    master_mob.comments['Channels'] = str(channels)
                    master_mob.comments['Number of Frames'] = str(audio_frames)
                    master_mob.comments['AudioFormat'] = 'WAV'
                    master_mob.comments['Tracks'] = 'A1' if channels==1 else ('A1A2' if channels==2 else f"A1A{channels}")
                    master_mob.comments['Duration'] = f"{duration_seconds:.3f}"
                    master_mob.comments['Start'] = "00:00:00:00"
                    master_mob.comments['End'] = "00:00:00:00"
                    # Tape field - set to directory name for batch import consistency
                    tape_name = Path(wav_path).parent.name if wav_path else "Unknown"
                    master_mob.comments['Tape'] = tape_name
                    master_mob.comments['Scene'] = ""
                    master_mob.comments['Take'] = ""

                    # Order: WAVEDesc SourceMob, MasterMob, ImportDesc SourceMob
                    f.content.mobs.append(wave_mob)
                    f.content.mobs.append(master_mob)
                    f.content.mobs.append(import_mob)

                return output_path
        except Exception as e:
            raise Exception(f"Error creating multi-clip AAF: {e}")

    def create_multi_tape_aaf(self, wav_entries: List[Dict[str, Dict]], output_path: str,
                             fps: float = 24) -> str:
        """Create a single AAF with multiple clips using TapeDescriptor structure (like ALE-exported AAFs).

        wav_entries: list of dicts with keys: wav_metadata, bext_metadata, info_metadata, xml_metadata, ucs_metadata
        """
        try:
            fps = int(fps)
            with aaf2.open(output_path, 'w') as f:
                # Set file identification
                f.header['ObjectModelVersion'].value = 1
                f.header['Version'].value = {'major': 1, 'minor': 2}
                for ident in f.header['IdentificationList'].value:
                    ident['ProductName'].value = "WAVsToAAF"
                    ident['CompanyName'].value = "Jason Brodkey"
                    ident['ProductVersionString'].value = __version__
                    break

                for entry in wav_entries:
                    wav_metadata = entry.get('wav_metadata', {})
                    bext_metadata = entry.get('bext_metadata', {})
                    info_metadata = entry.get('info_metadata', {})
                    xml_metadata = entry.get('xml_metadata', {})
                    ucs_metadata = entry.get('ucs_metadata', {})

                    # Audio params
                    channels = int(wav_metadata.get('channels', 1))
                    sample_rate = int(wav_metadata.get('sample_rate', 48000))
                    audio_frames = int(wav_metadata.get('frames', 0))
                    sample_width = int(wav_metadata.get('sample_width', 2))
                    bit_depth = int(sample_width * 8)
                    duration_seconds = audio_frames / sample_rate if sample_rate else 0
                    video_length = int(duration_seconds * fps)

                    # Resolve path
                    from pathlib import Path
                    wav_path = Path(wav_metadata.get('filepath', ''))
                    wav_stem = wav_path.stem

                    # 1) TapeDescriptor SourceMob (mimics ALE-exported structure)
                    tape_mob = f.create.SourceMob()
                    tape_mob.name = f"Tape_{wav_stem}"
                    # Use Avid-style UMID prefix (01010f10) with tape_mode=True
                    tape_mob.mob_id = create_deterministic_umid(wav_path, "tape", tape_mode=True)
                    
                    tape_desc = f.create.from_name('TapeDescriptor')
                    tape_desc['ColorFrame'].value = 0
                    tape_mob.descriptor = tape_desc

                    # Create slots like ALE exports: video slot (1) + audio slot (2)
                    # Video slot
                    video_slot = tape_mob.create_timeline_slot(fps)
                    video_slot.slot_id = 1
                    video_clip = f.create.SourceClip()
                    video_clip['DataDefinition'].value = f.dictionary.lookup_datadef('picture')
                    video_clip['Length'].value = video_length
                    video_clip['StartTime'].value = 0
                    video_clip['SourceID'].value = aaf2.mobid.MobID()  # NULL source
                    video_clip['SourceMobSlotID'].value = 0
                    video_slot.segment = video_clip

                    # Audio slot  
                    audio_slot = tape_mob.create_timeline_slot(fps)
                    audio_slot.slot_id = 2
                    audio_clip = f.create.SourceClip()
                    audio_clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                    audio_clip['Length'].value = video_length
                    audio_clip['StartTime'].value = 0
                    audio_clip['SourceID'].value = aaf2.mobid.MobID()  # NULL source
                    audio_clip['SourceMobSlotID'].value = 0
                    audio_slot.segment = audio_clip

                    # 2) MasterMob (mimics ALE-exported naming: filename.Exported.01)
                    master_mob = f.create.MasterMob()
                    master_mob.name = f"{wav_stem}.Exported.01"
                    # Use Avid-style UMID prefix (01010f10) with tape_mode=True
                    master_mob.mob_id = create_deterministic_umid(wav_path, "master", tape_mode=True)

                    # Single audio slot referencing the tape
                    master_slot = master_mob.create_timeline_slot(fps)
                    master_slot.slot_id = 1
                    master_clip = f.create.SourceClip()
                    master_clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                    master_clip['Length'].value = video_length
                    master_clip['StartTime'].value = 0
                    master_clip['SourceID'].value = tape_mob.mob_id
                    master_clip['SourceMobSlotID'].value = 2  # Reference audio slot on tape
                    master_slot.segment = master_clip

                    # 3) Add metadata comments to MasterMob (same as ImportDescriptor version)
                    if bext_metadata:
                        if bext_metadata.get('description'):
                            master_mob.comments['BEXT_Description'] = bext_metadata['description']
                        if bext_metadata.get('originator'):
                            master_mob.comments['BEXT_Originator'] = bext_metadata['originator']
                        if bext_metadata.get('originator_reference'):
                            master_mob.comments['BEXT_Originator_Reference'] = bext_metadata['originator_reference']
                        if bext_metadata.get('origination_date'):
                            master_mob.comments['BEXT_Origination_Date'] = bext_metadata['origination_date']
                        if bext_metadata.get('origination_time'):
                            master_mob.comments['BEXT_Origination_Time'] = bext_metadata['origination_time']
                        if bext_metadata.get('time_reference'):
                            master_mob.comments['BEXT_Time_Reference'] = str(bext_metadata['time_reference'])
                        if bext_metadata.get('umid'):
                            master_mob.comments['BEXT_UMID'] = bext_metadata['umid']
                    if info_metadata:
                        info_mappings = {
                            'IART': 'INFO_Artist','ICMT': 'INFO_Comment','ICOP': 'INFO_Copyright','ICRD': 'INFO_Creation_Date',
                            'IENG': 'INFO_Engineer','IGNR': 'INFO_Genre','IKEY': 'INFO_Keywords','INAM': 'INFO_Title',
                            'IPRD': 'INFO_Product','ISBJ': 'INFO_Subject','ISFT': 'INFO_Software','ISRC': 'INFO_Source'
                        }
                        for chunk_id, value in info_metadata.items():
                            if value:
                                master_mob.comments[info_mappings.get(chunk_id, f'INFO_{chunk_id}')] = str(value)
                    if ucs_metadata and 'primary_category' in ucs_metadata:
                        category = ucs_metadata['primary_category']
                        master_mob.comments['UCS_Category'] = category.get('category','')
                        master_mob.comments['UCS_SubCategory'] = category.get('subcategory','')
                        master_mob.comments['UCS_ID'] = category.get('id','')
                        master_mob.comments['UCS_Full_Name'] = category.get('full_name','')
                        master_mob.comments['UCS_Match_Score'] = str(category.get('score',''))
                        master_mob.comments['Category'] = category.get('category','')
                        master_mob.comments['SubCategory'] = category.get('subcategory','')
                        master_mob.comments['UCS ID'] = category.get('id','')
                    if bext_metadata and bext_metadata.get('description'):
                        master_mob.comments['Description'] = bext_metadata['description']
                    elif info_metadata and 'INAM' in info_metadata:
                        master_mob.comments['Description'] = str(info_metadata.get('INAM'))
                    master_mob.comments['Name'] = str(Path(wav_metadata.get('filename','Unknown')).stem)
                    master_mob.comments['Filename'] = str(Path(wav_metadata.get('filename','Unknown')).name)
                    master_mob.comments['FilePath'] = str(wav_path)
                    master_mob.comments['SampleRate'] = str(sample_rate)
                    master_mob.comments['BitDepth'] = str(bit_depth)
                    master_mob.comments['Channels'] = str(channels)
                    master_mob.comments['Number of Frames'] = str(audio_frames)
                    master_mob.comments['AudioFormat'] = 'WAV'
                    master_mob.comments['Tracks'] = 'A1' if channels==1 else ('A1A2' if channels==2 else f"A1A{channels}")
                    master_mob.comments['Duration'] = f"{duration_seconds:.3f}"
                    master_mob.comments['Start'] = "00:00:00:00"
                    master_mob.comments['End'] = "00:00:00:00"
                    master_mob.comments['Tape'] = ""
                    master_mob.comments['Scene'] = ""
                    master_mob.comments['Take'] = ""

                    # Add mobs to content (order: TapeDescriptor SourceMob, then MasterMob)
                    f.content.mobs.append(tape_mob)
                    f.content.mobs.append(master_mob)

                return output_path
        except Exception as e:
            raise Exception(f"Error creating multi-clip tape AAF: {e}")
    
    def _get_wave_fmt(self, wav_path: str) -> bytes:
        """Extract WAV format chunk for Summary property"""
        if not wav_path or not os.path.exists(wav_path):
            return None
            
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
                    
                    if chunk_id == 'fmt ':
                        return f.read(chunk_size)
                    else:
                        f.seek(chunk_size, 1)
                        if chunk_size % 2:  # Align to word boundary
                            f.seek(1, 1)
        except:
            pass
        return None
    
    def _generate_mob_id(self, filename: str) -> str:
        """Generate a simple Mob ID based on filename (kept for compatibility)"""
        import hashlib
        hash_obj = hashlib.md5(filename.encode())
        hash_hex = hash_obj.hexdigest()
        return f"urn:uuid:{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"

    def create_tape_aaf_file(self, wav_metadata: Dict, bext_metadata: Dict, info_metadata: Dict, 
                            xml_metadata: Dict, ucs_metadata: Dict, output_path: str, 
                            fps: float = 24, embed_audio: bool = True) -> str:
        """
        Create AAF file using TapeDescriptor structure (like ALE-exported AAFs)
        
        This replicates the successful structure found in ALE-exported AAFs:
        - Uses TapeDescriptor instead of ImportDescriptor
        - Uses Avid-style UMID prefix (01010f10)
        - Simpler 2-mob structure: MasterMob + TapeDescriptor SourceMob
        """
        try:
            from pathlib import Path
            wav_path = Path(wav_metadata.get('filepath', ''))
            
            # Extract audio parameters
            try:
                channels = int(wav_metadata.get('channels', 1))
                sample_rate = int(wav_metadata.get('sample_rate', 48000))
                audio_frames = int(wav_metadata.get('frames', 0))
                sample_width = int(wav_metadata.get('sample_width', 2))
                bit_depth = int(sample_width * 8)
            except (ValueError, TypeError) as e:
                raise Exception(f"Invalid audio parameters: {e}")
            
            fps = int(fps)
            duration_seconds = audio_frames / sample_rate if sample_rate else 0
            video_length = int(duration_seconds * fps)
            
            with aaf2.open(output_path, 'w') as f:
                # Set file identification (same as working ALE exports)
                f.header['ObjectModelVersion'].value = 1
                f.header['Version'].value = {'major': 1, 'minor': 2}
                
                # Create TapeDescriptor SourceMob (like "wavTest_1" in ALE exports)
                tape_mob = f.create.SourceMob()
                tape_mob.name = f"Tape_{wav_path.stem}"  # Simplified name
                tape_mob.mob_id = create_deterministic_umid(wav_path, "tape", tape_mode=True)
                
                # Create TapeDescriptor
                tape_desc = f.create.from_name('TapeDescriptor')
                tape_desc['ColorFrame'].value = 0  # Match ALE exports
                tape_mob.descriptor = tape_desc
                
                # Create multiple slots like ALE exports (simplified version)
                # Slot 1: Video (Picture data definition)
                vid_slot = tape_mob.create_timeline_slot(fps)
                vid_clip = f.create.SourceClip()
                vid_clip['DataDefinition'].value = f.dictionary.lookup_datadef('picture')
                vid_clip['Length'].value = video_length
                vid_clip['StartTime'].value = 0
                vid_clip['SourceID'].value = aaf2.mobid.MobID()  # Null source
                vid_clip['SourceMobSlotID'].value = 0
                vid_slot.segment = vid_clip
                
                # Slot 2: Audio (Sound data definition)  
                aud_slot = tape_mob.create_timeline_slot(fps)
                aud_clip = f.create.SourceClip()
                aud_clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                aud_clip['Length'].value = video_length
                aud_clip['StartTime'].value = 0
                aud_clip['SourceID'].value = aaf2.mobid.MobID()  # Null source
                aud_clip['SourceMobSlotID'].value = 0
                aud_slot.segment = aud_clip
                
                # Create MasterMob
                master_mob = f.create.MasterMob()
                master_mob.name = f"{wav_path.stem}.Exported.01"  # Match ALE export naming
                master_mob.mob_id = create_deterministic_umid(wav_path, "master", tape_mode=True)
                
                # MasterMob slot referencing TapeDescriptor
                master_slot = master_mob.create_timeline_slot(fps)
                master_clip = f.create.SourceClip()
                master_clip['DataDefinition'].value = f.dictionary.lookup_datadef('sound')
                master_clip['Length'].value = video_length
                master_clip['StartTime'].value = 0
                master_clip['SourceID'].value = tape_mob.mob_id
                master_clip['SourceMobSlotID'].value = 2  # Reference audio slot
                master_slot.segment = master_clip
                
                # Add metadata to MasterMob
                if bext_metadata.get('description'):
                    master_mob.comments['Description'] = bext_metadata['description']
                if ucs_metadata and 'primary_category' in ucs_metadata:
                    category = ucs_metadata['primary_category']
                    master_mob.comments['Category'] = category['category']
                    master_mob.comments['SubCategory'] = category['subcategory']
                
                # Set standard comments
                master_mob.comments['Start'] = "00:00:00:00"
                master_mob.comments['End'] = "00:00:00:00"
                master_mob.comments['Tape'] = ""
                master_mob.comments['Scene'] = ""
                master_mob.comments['Take'] = ""
                
                # Add mobs to content
                f.content.mobs.append(master_mob)
                f.content.mobs.append(tape_mob)
                
                return output_path
                
        except Exception as e:
            print(f"Error creating tape-mode AAF: {e}")
            raise

class WAVsToAAFProcessor:
    """Main processor class for converting WAV files to AAF format"""
    
    def __init__(self):
        self.extractor = WAVMetadataExtractor()
        self.generator = AAFGenerator()
        self.ucs_processor = UCSProcessor()
    
    def process_directory(self, input_dir: str, output_dir: str, fps: float = 24, embed_audio: bool = False,
                          link_mode: str = 'import', emit_ale: bool = False, one_aaf: bool = False,
                          near_sources: bool = False, tape_mode: bool = False, relative_locators: bool = False,
                          skip_log_path: Optional[str] = None, auto_skip_log: bool = False,
                          allow_ucs_guess: bool = True) -> int:
        """Process all WAV files in a directory"""
        input_path = Path(input_dir)
        
        # Determine the base output directory
        if not near_sources and output_dir:
            # When output_dir is provided but not near_sources, use it as-is
            output_path = Path(output_dir)
        elif not near_sources and not output_dir:
            # When no output_dir and not near_sources, create AAFs directory one level above input
            output_path = input_path.parent / 'AAFs'
        else:
            # When near_sources is True, we'll save next to each WAV
            output_path = Path(output_dir) if output_dir else input_path.parent / 'AAFs'

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

        # Prepare ALE rows (optional)
        ale_rows: List[Dict[str, str]] = []

        def add_ale_row_from_wavmeta(wav_path: Path, wav_meta: Dict):
            try:
                ch = int(wav_meta.get('channels', 1))
                sr = int(wav_meta.get('sample_rate', 48000))
                frames = int(wav_meta.get('frames', 0))
                dur = (frames / sr) if sr else 0.0
                name = wav_path.stem
                audio_rate = '48kHz' if sr == 48000 else (f"{sr/1000:g}kHz")
                ale_rows.append({
                    'Name': name,
                    'Tracks': ('A1' if ch==1 else ('A1A2' if ch==2 else f"A1A{ch}")),
                    'Start': '',
                    'End': '',
                    'Tape': '',
                    'Source File': wav_path.name,
                    'AudioRate': audio_rate,
                    'SampleRate': f"{sr}Hz",
                    'Channels': str(ch),
                    'Duration': f"{dur:.3f}",
                })
            except Exception:
                pass

        processed = 0
        low_confidence_items = []  # collect low-confidence UCS matches for reporting
        if one_aaf:
            # Check if embedded mode is requested for multi-clip AAF
            if embed_audio:
                print("Warning: Multi-clip AAFs with embedded audio would be extremely large.")
                print("Falling back to individual AAFs per clip.")
                print("Use --linked flag if you want multi-clip AAFs with external file references.")
                one_aaf = False  # Force individual AAF mode
        
        if one_aaf:
            # Build multi-clip AAF in one file (linked mode only)
            wav_entries = []
            for wav_file in wav_files:
                try:
                    wav_meta = self.extractor.extract_basic_info(str(wav_file))
                    if not wav_meta:
                        print(f"  Skipping {wav_file.name}: Could not read metadata")
                        continue
                    all_chunks = self.extractor.extract_all_metadata_chunks(str(wav_file))
                    bext_metadata = {k: v for k, v in all_chunks.items() if k in [
                        'description', 'originator', 'originator_reference', 'origination_date',
                        'origination_time', 'time_reference', 'version', 'umid', 'loudness_value',
                        'loudness_range', 'max_true_peak', 'max_momentary_loudness', 'max_short_term_loudness'
                    ]}
                    xml_prefixes = ['ebucore_', 'bwfmetaedit_', 'protools_', 'axml_', 'xml_']
                    xml_metadata = {k: v for k, v in all_chunks.items() if any(k.startswith(prefix) for prefix in xml_prefixes)}
                    used_keys = set(bext_metadata.keys()) | set(xml_metadata.keys())
                    info_metadata = {k: v for k, v in all_chunks.items() if k not in used_keys}

                    # Resolve UCS metadata taking INFO / iXML fields into account
                    ucs_metadata = self._resolve_ucs_metadata(
                        wav_file.name,
                        bext_metadata.get('description', ''),
                        info_metadata, xml_metadata,
                        allow_guess=allow_ucs_guess
                    )
                    # Collect low-confidence fuzzy matches for reporting (multi-clip path)
                    try:
                        if allow_ucs_guess and ucs_metadata and 'primary_category' in ucs_metadata:
                            score = float(ucs_metadata['primary_category'].get('score', 0.0))
                            if 0 < score < getattr(self, '_ucs_min_score', 25.0):
                                low_confidence_items.append({
                                    'file': str(wav_file.name),
                                    'description': bext_metadata.get('description',''),
                                    'ucs_id': ucs_metadata['primary_category'].get('id',''),
                                    'category': ucs_metadata['primary_category'].get('category',''),
                                    'subcategory': ucs_metadata['primary_category'].get('subcategory',''),
                                    'score': score,
                                })
                    except Exception:
                        pass

                    wav_entries.append({
                        'wav_metadata': wav_meta,
                        'bext_metadata': bext_metadata,
                        'info_metadata': info_metadata,
                        'xml_metadata': xml_metadata,
                        'ucs_metadata': ucs_metadata,
                    })
                    add_ale_row_from_wavmeta(wav_file, wav_meta)
                except Exception as e:
                    print(f"  Error preparing {wav_file.name}: {e}")

            out_file = output_path / 'batch.aaf'
            try:
                if tape_mode:
                    self.generator.create_multi_tape_aaf(wav_entries, str(out_file), fps=fps)
                    print(f"  Created (tape-mode): {out_file.name}")
                else:
                    self.generator.create_multi_aaf(wav_entries, str(out_file), fps=fps, embed_audio=embed_audio, link_mode=link_mode)
                    print(f"  Created: {out_file.name}")
                processed = len(wav_entries)
            except Exception as e:
                print(f"  Error creating multi-clip AAF: {e}")
        else:
            # One AAF per clip
            for wav_file in wav_files:
                try:
                    print(f"Processing: {wav_file.name}")
                    wav_metadata = self.extractor.extract_basic_info(str(wav_file))
                    if not wav_metadata:
                        print(f"  Skipping {wav_file.name}: Could not read metadata")
                        continue
                    # Extract all metadata chunks
                    all_chunks = self.extractor.extract_all_metadata_chunks(str(wav_file))
                    bext_metadata = {k: v for k, v in all_chunks.items() if k in [
                        'description', 'originator', 'originator_reference', 'origination_date',
                        'origination_time', 'time_reference', 'version', 'umid', 'loudness_value',
                        'loudness_range', 'max_true_peak', 'max_momentary_loudness', 'max_short_term_loudness'
                    ]}
                    xml_prefixes = ['ebucore_', 'bwfmetaedit_', 'protools_', 'axml_', 'xml_']
                    xml_metadata = {k: v for k, v in all_chunks.items() if any(k.startswith(prefix) for prefix in xml_prefixes)}
                    used_keys = set(bext_metadata.keys()) | set(xml_metadata.keys())
                    info_metadata = {k: v for k, v in all_chunks.items() if k not in used_keys}

                    ucs_metadata = self._resolve_ucs_metadata(
                        wav_file.name,
                        bext_metadata.get('description', ''),
                        info_metadata, xml_metadata,
                        allow_guess=allow_ucs_guess
                    )

                    try:
                        if allow_ucs_guess and ucs_metadata and 'primary_category' in ucs_metadata:
                            score = float(ucs_metadata['primary_category'].get('score', 0.0))
                            if 0 < score < getattr(self, '_ucs_min_score', 25.0):
                                low_confidence_items.append({
                                    'file': str(wav_file.name),
                                    'description': bext_metadata.get('description',''),
                                    'ucs_id': ucs_metadata['primary_category'].get('id',''),
                                    'category': ucs_metadata['primary_category'].get('category',''),
                                    'subcategory': ucs_metadata['primary_category'].get('subcategory',''),
                                    'score': score,
                                })
                    except Exception:
                        pass
                    output_filename = wav_file.stem + '.aaf'
                    
                    # Choose output location based on near_sources flag
                    if near_sources:
                        # Save AAF next to the source WAV file
                        out_file = wav_file.parent / output_filename
                        print(f"  Saving near source: {out_file}")
                    else:
                        # Mirror the subdirectory structure within the output directory
                        # Calculate relative path from input_path to wav_file
                        try:
                            rel_dir = wav_file.parent.relative_to(input_path)
                            out_dir = output_path / rel_dir
                        except ValueError:
                            # Fallback if relative path calculation fails
                            out_dir = output_path
                        
                        out_dir.mkdir(parents=True, exist_ok=True)
                        out_file = out_dir / output_filename
                    
                    # Choose AAF generation method based on tape_mode flag
                    if tape_mode:
                        self.generator.create_tape_aaf_file(
                            wav_metadata, bext_metadata, info_metadata, xml_metadata, ucs_metadata, str(out_file),
                            fps=fps, embed_audio=embed_audio
                        )
                        print(f"  Created (tape-mode): {output_filename}")
                    else:
                        self.generator.create_aaf_file(
                            wav_metadata, bext_metadata, info_metadata, xml_metadata, ucs_metadata, str(out_file),
                            fps=fps, embed_audio=embed_audio, link_mode=link_mode, relative_locators=relative_locators
                        )
                        print(f"  Created: {output_filename}")
                    processed += 1
                    add_ale_row_from_wavmeta(wav_file, wav_metadata)
                except Exception as e:
                    print(f"  Error processing {wav_file.name}: {e}")

        # Optionally write ALE
        if emit_ale and ale_rows:
            ale_path = output_path / 'batch.ale'
            try:
                with open(ale_path, 'w', encoding='utf-8') as f:
                    f.write('Heading\n')
                    f.write('FIELD_DELIM\tTABS\n')
                    f.write('VIDEO_FORMAT\t1080\n')
                    f.write('AUDIO_FORMAT\t48kHz\n')
                    f.write(f'FPS\t{int(fps)}\n')
                    f.write('\nColumn\n')
                    cols = ['Name','Tracks','Start','End','Tape','Source File','AudioRate','SampleRate','Channels','Duration']
                    f.write('\t'.join(cols)+'\n')
                    f.write('Data\n')
                    for r in ale_rows:
                        f.write('\t'.join(r.get(c,'') for c in cols)+'\n')
                print(f"  Wrote ALE: {ale_path}")
            except Exception as e:
                print(f"  Failed to write ALE: {e}")

        # Write batch low-confidence report if present
        if low_confidence_items:
            try:
                import csv
                report_path = output_path / 'ucs_low_confidence.csv'
                with open(report_path, 'w', newline='', encoding='utf-8') as rf:
                    writer = csv.DictWriter(rf, fieldnames=['file','description','ucs_id','category','subcategory','score'])
                    writer.writeheader()
                    for row in low_confidence_items:
                        writer.writerow(row)
                print(f"  Wrote UCS low-confidence report: {report_path}")
            except Exception as e:
                print(f"  Failed to write UCS low-confidence report: {e}")

        print(f"\nCompleted! Processed {processed} file(s)")
        print(f"Output files saved to: {output_path}")
        return 0
    
    def process_single_file(self, wav_file: str, output_file: str, fps: float = 24, embed_audio: bool = False,
                            link_mode: str = 'import', relative_locators: bool = False,
                            skip_log_path: Optional[str] = None, auto_skip_log: bool = False,
                            allow_ucs_guess: bool = True) -> int:
        """Process a single WAV file"""
        try:
            # Ensure output directory exists
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"Processing: {wav_file}")
            
            # Enforce WAV-only policy: check extension early and provide helpful error
            ext = Path(wav_file).suffix.lower()
            if ext not in self.extractor.supported_formats:
                print(f"Error: Unsupported input format '{ext}'. This tool only supports WAV files (.wav, .wave).")
                return 1

            # Extract metadata
            wav_metadata = self.extractor.extract_basic_info(wav_file)
            
            if not wav_metadata:
                print(f"Error: Could not read metadata from {wav_file}")
                return 1
            
            # Extract all metadata chunks
            all_chunks = self.extractor.extract_all_metadata_chunks(wav_file)
            
            # Separate chunk types
            bext_metadata = {k: v for k, v in all_chunks.items() if k in [
                'description', 'originator', 'originator_reference', 'origination_date', 
                'origination_time', 'time_reference', 'version', 'umid', 'loudness_value',
                'loudness_range', 'max_true_peak', 'max_momentary_loudness', 'max_short_term_loudness'
            ]}
            
            # Extract XML metadata (keys with XML prefixes)
            xml_prefixes = ['ebucore_', 'bwfmetaedit_', 'protools_', 'axml_', 'xml_']
            xml_metadata = {k: v for k, v in all_chunks.items() if any(k.startswith(prefix) for prefix in xml_prefixes)}
            
            # INFO metadata is everything else (not BEXT or XML)
            used_keys = set(bext_metadata.keys()) | set(xml_metadata.keys())
            info_metadata = {k: v for k, v in all_chunks.items() if k not in used_keys}
            
            # Show metadata found
            if info_metadata:
                print(f"INFO metadata found: {list(info_metadata.keys())}")
            
            if xml_metadata:
                xml_types = set(k.split('_')[0] for k in xml_metadata.keys() if '_' in k)
                print(f"XML metadata found: {list(xml_types)}")
            
            # UCS categorization
            ucs_metadata = self._resolve_ucs_metadata(
                Path(wav_file).name,
                bext_metadata.get('description', ''),
                info_metadata, xml_metadata,
                allow_guess=allow_ucs_guess
            )
            
            if ucs_metadata and 'primary_category' in ucs_metadata:
                category = ucs_metadata['primary_category']
                print(f"UCS Category: {category['category']} > {category['subcategory']} ({category['score']:.1f})")
            
            # Generate AAF file
            output_file_path = self.generator.create_aaf_file(
                wav_metadata, bext_metadata, info_metadata, xml_metadata, ucs_metadata, output_file,
                fps=fps, embed_audio=embed_audio, link_mode=link_mode, relative_locators=relative_locators
            )
            
            print(f"Created: {output_file}")
            # If single-file and fuzzy match was low-confidence, write a tiny report near the output
            try:
                if allow_ucs_guess and ucs_metadata and 'primary_category' in ucs_metadata:
                    score = float(ucs_metadata['primary_category'].get('score', 0.0))
                    if 0 < score < getattr(self, '_ucs_min_score', 25.0):
                        try:
                            import csv
                            report_path = output_path.parent / 'ucs_low_confidence.csv'
                            with open(report_path, 'w', newline='', encoding='utf-8') as rf:
                                writer = csv.DictWriter(rf, fieldnames=['file','description','ucs_id','category','subcategory','score'])
                                writer.writeheader()
                                writer.writerow({
                                    'file': Path(wav_file).name,
                                    'description': bext_metadata.get('description',''),
                                    'ucs_id': ucs_metadata['primary_category'].get('id',''),
                                    'category': ucs_metadata['primary_category'].get('category',''),
                                    'subcategory': ucs_metadata['primary_category'].get('subcategory',''),
                                    'score': score,
                                })
                            print(f"  Wrote UCS low-confidence report: {report_path}")
                        except Exception as e:
                            print(f"  Failed to write UCS low-confidence report: {e}")
            except Exception:
                pass

            return 0

        except Exception as e:
            print(f"Error processing {wav_file}: {e}")
            return 1

    def _resolve_ucs_metadata(self, filename: str, description: str, info_metadata: Dict, xml_metadata: Dict, allow_guess: bool = True) -> Dict:
        """Resolve UCS metadata for a file, preferring filename-ID exact matches, then INFO/iXML fields, then fuzzy UCS guessing.

        Returns a ucs_metadata dict in the same shape as UCSProcessor.categorize_sound.
        """
        # 1) Exact filename-ID match handled by categorize_sound (it returns score 100)
        res = self.ucs_processor.categorize_sound(filename, description, allow_guess=True)
        if res and 'primary_category' in res and float(res['primary_category'].get('score', 0)) >= 100.0:
            return res

        # 2) Check INFO metadata (case-insensitive keys) for explicit Category/SubCategory/UCS ID
        # Normalize keys to lower-case for lookup
        info_norm = {k.strip().lower(): v for k, v in (info_metadata or {}).items()}
        xml_norm = {k.strip().lower(): v for k, v in (xml_metadata or {}).items()}

        # Helper to pick candidate values
        def find_key(dct, possible_keys):
            for pk in possible_keys:
                if pk in dct and dct[pk]:
                    return dct[pk]
            return None

        category = find_key(info_norm, ['category']) or find_key(xml_norm, [k for k in xml_norm.keys() if 'category' in k])
        subcategory = find_key(info_norm, ['subcategory', 'sub category', 'sub_cat', 'sub_catagory']) or find_key(xml_norm, [k for k in xml_norm.keys() if 'subcategory' in k or 'sub category' in k])
        ucsid = find_key(info_norm, ['ucs_id','ucs id','ucsid']) or find_key(xml_norm, ['ucs_id','ucs id','ucsid'])

        if category or subcategory or ucsid:
            # Use explicit metadata; mark score 100 to indicate authoritative source
            full_name = f"{category or ''} {subcategory or ''}".strip()
            return {
                'primary_category': {
                    'id': ucsid or '',
                    'full_name': full_name or (ucsid or ''),
                    'category': category or '',
                    'subcategory': subcategory or '',
                    'score': 100.0
                }
            }

        # 3) Fallback to UCS guessing if allowed
        if allow_guess:
            return self.ucs_processor.categorize_sound(filename, description)

        # No match
        return {}
            
        

    def process_files_to_one_aaf(self, wav_files: List[str], output_file: str, fps: float = 24,
                                 embed_audio: bool = False, link_mode: str = 'import', tape_mode: bool = False,
                                 allow_ucs_guess: bool = True) -> int:
        """Process multiple WAV files into a single multi-clip AAF file."""
        try:
            # Ensure output directory exists
            out_path = Path(output_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            wav_entries = []
            for wav_file in wav_files:
                # Extract metadata
                wav_metadata = self.extractor.extract_basic_info(wav_file)
                if not wav_metadata:
                    print(f"Skipping {wav_file}: cannot read metadata")
                    continue

                all_chunks = self.extractor.extract_all_metadata_chunks(wav_file)
                bext_metadata = {k: v for k, v in all_chunks.items() if k in [
                    'description', 'originator', 'originator_reference', 'origination_date', 
                    'origination_time', 'time_reference', 'version', 'umid', 'loudness_value',
                    'loudness_range', 'max_true_peak', 'max_momentary_loudness', 'max_short_term_loudness'
                ]}
                xml_prefixes = ['ebucore_', 'bwfmetaedit_', 'protools_', 'axml_', 'xml_']
                xml_metadata = {k: v for k, v in all_chunks.items() if any(k.startswith(prefix) for prefix in xml_prefixes)}
                used_keys = set(bext_metadata.keys()) | set(xml_metadata.keys())
                info_metadata = {k: v for k, v in all_chunks.items() if k not in used_keys}

                ucs_metadata = self.ucs_processor.categorize_sound(
                        Path(wav_file).name,
                        bext_metadata.get('description', ''),
                        allow_guess=allow_ucs_guess
                    )

                wav_entries.append({
                    'wav_metadata': wav_metadata,
                    'bext_metadata': bext_metadata,
                    'info_metadata': info_metadata,
                    'xml_metadata': xml_metadata,
                    'ucs_metadata': ucs_metadata,
                })

            if not wav_entries:
                print("No valid WAV entries to process")
                return 1

            if tape_mode:
                self.generator.create_multi_tape_aaf(wav_entries, output_file, fps=fps)
                print(f"Created multi-clip tape AAF: {output_file}")
            else:
                self.generator.create_multi_aaf(wav_entries, output_file, fps=fps, embed_audio=embed_audio, link_mode=link_mode)
                print(f"Created multi-clip AAF: {output_file}")
            return 0
        except Exception as e:
            print(f"Error creating multi-clip AAF: {e}")
            return 1

def launch_gui():
    """Launch a Tkinter GUI for selecting inputs and running AAF conversion."""
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        from tkinter.scrolledtext import ScrolledText
    except ImportError:
        print("Error: tkinter is required for GUI mode.")
        print("Install tkinter or run in CLI mode instead.")
        sys.exit(1)
    
    root = tk.Tk()
    root.title("WAVsToAAF")
    root.geometry("680x520")
    
    # Set window icon for taskbar and title bar
    try:
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            icon_path = os.path.join(sys._MEIPASS, 'icons', 'WAVsToAAF.ico')
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
    except Exception:
        pass

    # Helper function to get bundled file path
    def get_resource_path(filename):
        """Get path to bundled file (works in both dev and PyInstaller modes)."""
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            return os.path.join(sys._MEIPASS, filename)
        else:
            # Running from source
            return os.path.join(os.path.dirname(__file__), filename)

    # Variables
    wav_var = tk.StringVar()
    out_var = tk.StringVar()
    fps_var = tk.StringVar(value="24")
    embed_var = tk.BooleanVar(value=True)
    infer_ucs_var = tk.BooleanVar(value=True)
    progress_var = tk.StringVar(value="")
    last_outputs = {'paths': []}
    cancel_event = threading.Event()
    processor = WAVsToAAFProcessor()

    # Help menu functions
    def show_about():
        """Show About dialog."""
        messagebox.showinfo(
            "About WAVsToAAF",
            f"WAVsToAAF v{__version__}\n\n"
            "Convert WAV files to Advanced Authoring Format (AAF)\n"
            "with rich metadata for fast organizing, relinking,\n"
            "and batch import in Avid Media Composer.\n\n"
            "© Jason Brodkey\n"
            "www.editcandy.com"
        )

    def show_license():
        """Display the LICENSES.txt file in a new window."""
        try:
            license_path = get_resource_path('LICENSES.txt')
            if os.path.exists(license_path):
                with open(license_path, 'r') as f:
                    license_text = f.read()
                
                # Create a new window for license display
                license_win = tk.Toplevel(root)
                license_win.title("Licenses")
                license_win.geometry("600x400")
                
                text_widget = ScrolledText(license_win, state='normal', wrap='word')
                text_widget.pack(fill='both', expand=True, padx=8, pady=8)
                text_widget.insert('1.0', license_text)
                text_widget.configure(state='disabled')
            else:
                messagebox.showinfo("Licenses", "License file not found")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open licenses: {e}")

    def show_help():
        """Display help/readme documentation."""
        try:
            # Try platform-specific readme first, then generic README
            if sys.platform == 'darwin':
                readme_path = get_resource_path('docs/README_mac.md')
            elif sys.platform == 'win32':
                readme_path = get_resource_path('docs/README_windows.md')
            else:
                readme_path = get_resource_path('README.md')
            
            if not os.path.exists(readme_path):
                readme_path = get_resource_path('README.md')
            
            if os.path.exists(readme_path):
                with open(readme_path, 'r') as f:
                    readme_text = f.read()
                
                # Create a new window for help display
                help_win = tk.Toplevel(root)
                help_win.title("Help")
                help_win.geometry("700x500")
                
                text_widget = ScrolledText(help_win, state='normal', wrap='word')
                text_widget.pack(fill='both', expand=True, padx=8, pady=8)
                text_widget.insert('1.0', readme_text)
                text_widget.configure(state='disabled')
            else:
                messagebox.showinfo("Help", "Help documentation not found")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open help: {e}")

    def log(msg):
        log_text.configure(state='normal')
        log_text.insert('end', str(msg) + "\n")
        log_text.see('end')
        log_text.configure(state='disabled')
        # Parse progress "X/Y" from batch processing output
        try:
            s = str(msg)
            if "/" in s and "%" in s:
                # Extract X/Y from progress bar line like "1/18 (5.6%)"
                parts = s.split()
                for part in parts:
                    if "/" in part and part[0].isdigit():
                        progress_var.set(f"Processing {part}")
                        break
        except Exception:
            pass
        # Capture generated AAF paths from log lines to enable Reveal button
        try:
            s = str(msg)
            markers = ["Created:", "Output files saved to:"]
            for m in markers:
                if m in s:
                    # Extract path after marker
                    path = s.split(m, 1)[1].strip() if m in s else ""
                    if path:
                        # Store directory path
                        if os.path.isdir(path):
                            if path not in last_outputs['paths']:
                                last_outputs['paths'].append(path)
                        elif path.lower().endswith('.aaf'):
                            if path not in last_outputs['paths']:
                                last_outputs['paths'].append(path)
                        try:
                            if not open_btn.winfo_ismapped():
                                open_btn.pack(side='left', padx=(8, 0))
                            open_btn.configure(state='normal')
                        except Exception:
                            pass
                    break
        except Exception:
            pass

    def browse_wav_file():
        path = filedialog.askopenfilename(
            title="Select WAV file",
            filetypes=[("WAV Files", "*.wav *.wave"), ("All Files", "*.*")]
        )
        if path:
            wav_var.set(path)
    def browse_wav_dir():
        path = filedialog.askdirectory(title="Select WAV directory")
        if path:
            wav_var.set(path)

    def browse_out():
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            out_var.set(path)

    def run_clicked():
        # Parse FPS
        try:
            fps = float(fps_var.get().strip() or "24")
            if fps <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Invalid FPS", "FPS must be a positive number (e.g. 24 or 23.976). Using 24.")
            fps = 24.0
        
        # Get options
        embed_audio = embed_var.get()
        allow_ucs_guess = infer_ucs_var.get()
        write_skip_log = True  # Always on by default

        wavp = wav_var.get().strip() or None
        outp = out_var.get().strip() or None

        if not wavp:
            messagebox.showerror("Missing input", "Please select a WAV file or directory.")
            return
        
        # Verify source still exists (catch cases where user deleted/moved file before clicking Run)
        if not os.path.exists(wavp):
            messagebox.showerror("Source not found", "The selected source is not available")
            return

        # Normalize output path to always include AAFs directory structure
        is_single_file = os.path.isfile(wavp)
        if is_single_file:
            # For single file processing
            if not outp:
                # Default: AAFs folder next to the file
                out_folder = os.path.join(os.path.dirname(wavp), "AAFs")
            else:
                # User specified output - force it to end with AAFs
                if not outp.rstrip('/\\').endswith("AAFs"):
                    out_folder = os.path.join(outp, "AAFs")
                else:
                    out_folder = outp.rstrip('/\\')
            # Create output folder if it doesn't exist
            try:
                os.makedirs(out_folder, exist_ok=True)
            except Exception:
                pass
            outp = os.path.join(out_folder, os.path.splitext(os.path.basename(wavp))[0] + ".aaf")
            log(f"Output will be: {outp}")
        else:
            # Directory mode - always use AAFs structure
            if not outp:
                # Default: AAFs folder as sibling with directory structure preserved
                dir_path = wavp.rstrip('/\\')
                dir_name = os.path.basename(dir_path)
                parent = os.path.dirname(dir_path)
                parent_name = os.path.basename(parent) if parent else ""
                # Include parent directory name if it exists (preserve one level of structure)
                if parent_name:
                    outp = os.path.join(os.path.dirname(parent), "AAFs", parent_name, dir_name)
                else:
                    outp = os.path.join(parent, "AAFs", dir_name)
            else:
                # User specified output - force it to end with AAFs
                if not outp.rstrip('/\\').endswith("AAFs"):
                    outp = os.path.join(outp, "AAFs")
                else:
                    outp = outp.rstrip('/\\')

        # Run in a thread to keep UI responsive
        cancel_event.clear()
        try:
            run_btn.configure(state='disabled')
            cancel_btn.configure(state='normal')
        except Exception:
            pass

        def worker():
            log("Starting conversion…")
            log(f"Frame rate: {fps} fps")
            log(f"Audio: {'Embedded' if embed_audio else 'Linked'}")
            progress_var.set("")  # Reset progress display
            last_outputs['paths'].clear()
            ok = False
            try:
                if os.path.isfile(wavp):
                    # Single file mode - outp is already the full AAF file path
                    result = processor.process_single_file(
                        wavp, outp, fps=fps, embed_audio=embed_audio,
                        auto_skip_log=write_skip_log, allow_ucs_guess=allow_ucs_guess
                    )
                    ok = (result == 0)
                    # Explicitly track the output file path after successful processing
                    if ok and outp:
                        last_outputs['paths'].append(outp)
                else:
                    # Directory mode - outp is now computed AAFs path
                    result = processor.process_directory(
                        wavp, outp, fps=fps, embed_audio=embed_audio,
                        auto_skip_log=write_skip_log, allow_ucs_guess=allow_ucs_guess
                    )
                    ok = (result == 0)
            except Exception as e:
                error_str = str(e)
                # Check for common ffmpeg/source not found errors
                if "returned non-zero exit status" in error_str or "No such file" in error_str or not os.path.exists(wavp):
                    log(f"Source not found: The source file or directory is no longer available or cannot be accessed")
                    messagebox.showerror("Source not found", f"The source file or directory is no longer available or cannot be accessed:\n{wavp}")
                elif error_str.strip():
                    log(f"Error: {e}")
                    messagebox.showerror("Error", f"AAF creation failed: {e}")
                ok = False

            # Update UI from main thread
            def finish_ui():
                try:
                    run_btn.configure(state='normal')
                    cancel_btn.configure(state='disabled')
                except Exception:
                    pass
                if ok:
                    messagebox.showinfo("Done", "AAF creation completed.")
                else:
                    if cancel_event.is_set():
                        messagebox.showinfo("Cancelled", "AAF creation canceled. Some AAFs may have already been created.")
                    else:
                        messagebox.showerror("Error", "AAF creation failed. Check the log for details.")

            try:
                root.after(0, finish_ui)
            except Exception:
                finish_ui()

        threading.Thread(target=worker, daemon=True).start()

    def cancel_clicked():
        cancel_event.set()
        log("Cancellation requested…")

    def clear_log():
        log_text.configure(state='normal')
        log_text.delete('1.0', 'end')
        log_text.configure(state='disabled')
        progress_var.set("")  # Reset progress display
        # Also hide the Open AAF Location button
        try:
            open_btn.pack_forget()
        except Exception:
            pass

    def open_output_location():
        # Prefer opening the folder containing the last created AAF file if tracked
        paths = last_outputs.get('paths') or []
        if paths:
            target = paths[-1]  # last created AAF
            try:
                # Open the folder containing the AAF, not the AAF itself
                if sys.platform == 'win32':
                    folder = os.path.normpath(os.path.dirname(target))
                else:
                    folder = os.path.dirname(target)
                if sys.platform == 'darwin':
                    subprocess.run(['open', folder], check=False)
                elif sys.platform == 'win32':
                    os.startfile(folder)
                else:
                    subprocess.run(['xdg-open', folder], check=False)
                return
            except Exception:
                pass
        
        # Fallback: check if the user set an Output Folder
        outp = (out_var.get().strip() or '')
        wavp = (wav_var.get().strip() or '')
        if outp:
            try:
                folder = outp if os.path.isdir(outp) else os.path.dirname(outp)
                if sys.platform == 'darwin':
                    subprocess.run(['open', folder], check=False)
                elif sys.platform == 'win32':
                    os.startfile(folder)
                else:
                    subprocess.run(['xdg-open', folder], check=False)
                return
            except Exception:
                pass
        
        # Last resort fallback: open expected folder based on inputs
        try:
            if os.path.isfile(wavp):
                # Single file case: default output is AAFs subdirectory
                folder = os.path.join(os.path.dirname(wavp), 'AAFs')
            else:
                # Directory case: use the parent directory's AAFs
                folder = os.path.join(os.path.dirname(wavp), 'AAFs')
            
            if os.path.isdir(folder):
                if sys.platform == 'darwin':
                    subprocess.run(['open', folder], check=False)
                elif sys.platform == 'win32':
                    os.startfile(folder)
                else:
                    subprocess.run(['xdg-open', folder], check=False)
            else:
                messagebox.showwarning("Open Location", f"AAF folder not found: {folder}")
        except Exception as e:
            messagebox.showwarning("Open Location", f"Could not open the AAF location: {e}")

    # Create menu bar
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    # Map macOS About menu to custom dialog
    try:
        root.createcommand('tkAboutDialog', show_about)
    except Exception:
        pass
    
    # App menu (WAVsToAAF)
    app_menu = tk.Menu(menubar, tearoff=0, name='apple')
    menubar.add_cascade(label="WAVsToAAF", menu=app_menu)
    app_menu.add_command(label="About WAVsToAAF", command=show_about)
    app_menu.add_separator()
    
    # Help menu
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="Help Documentation", command=show_help)
    help_menu.add_separator()
    help_menu.add_command(label="Licenses", command=show_license)

    # Layout - use ttk.Frame like ALE
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill='both', expand=True)

    # WAV
    ttk.Label(frm, text="WAV file or directory").grid(row=0, column=0, sticky='w')
    wav_entry = ttk.Entry(frm, textvariable=wav_var, width=60)
    wav_entry.grid(row=1, column=0, columnspan=2, sticky='we', pady=(1, 0))
    # Place the buttons in a frame in the same row as the entry
    wav_btns = ttk.Frame(frm)
    wav_btns.grid(row=1, column=2, sticky='w', pady=0)
    ttk.Button(wav_btns, text="File…", command=browse_wav_file).grid(row=0, column=0, padx=(0, 4), pady=0)
    ttk.Button(wav_btns, text="Folder…", command=browse_wav_dir).grid(row=0, column=1, pady=0)

    # Output
    ttk.Label(frm, text="Output Folder for AAFs").grid(row=2, column=0, sticky='w', pady=(6, 0))
    out_entry = ttk.Entry(frm, textvariable=out_var, width=60)
    out_entry.grid(row=3, column=0, columnspan=2, sticky='we', pady=(1, 0))
    ttk.Button(frm, text="Browse…", command=browse_out).grid(row=3, column=2, sticky='w', pady=0)

    # FPS
    fps_row = ttk.Frame(frm)
    fps_row.grid(row=4, column=0, columnspan=3, sticky='w', pady=(6, 8))
    ttk.Label(fps_row, text="FPS:").pack(side='left')
    ttk.Entry(fps_row, textvariable=fps_var, width=8).pack(side='left', padx=(4, 0))
    ttk.Label(fps_row, text="(default 24)").pack(side='left', padx=(6, 0))
    
    # Embed audio checkbox (embedded is default)
    ttk.Checkbutton(frm, text="Embed audio in AAF (default)", variable=embed_var).grid(row=5, column=0, columnspan=3, sticky='w', pady=(0, 2))
    
    # UCS inference checkbox
    ttk.Checkbutton(frm, text="Infer UCS category/subcategory if filename lacks a UCS ID", variable=infer_ucs_var).grid(row=5, column=0, columnspan=3, sticky='w', pady=(2, 8))

    # Action buttons
    buttons_row = ttk.Frame(frm)
    buttons_row.grid(row=6, column=0, columnspan=3, sticky='w', pady=(0, 8))
    run_btn = ttk.Button(buttons_row, text="Run", command=run_clicked)
    run_btn.pack(side='left')
    cancel_btn = ttk.Button(buttons_row, text="Cancel", command=cancel_clicked, state='disabled')
    cancel_btn.pack(side='left', padx=(8, 0))
    open_btn = ttk.Button(buttons_row, text="Open AAF Location", command=open_output_location, state='disabled')
    # Keep hidden until an AAF is generated
    try:
        open_btn.pack_forget()
    except Exception:
        pass

    # Log area with progress display and clear button
    log_header = ttk.Frame(frm)
    log_header.grid(row=7, column=0, columnspan=3, sticky='ew', pady=(0, 2))
    ttk.Label(log_header, text="Output Log").pack(side='left')
    progress_lbl = ttk.Label(log_header, textvariable=progress_var, foreground="#555555")
    progress_lbl.pack(side='left', padx=(12, 0))
    ttk.Button(log_header, text="Clear", command=clear_log, width=8).pack(side='right')

    log_text = ScrolledText(frm, height=16, state='disabled')
    log_text.grid(row=8, column=0, columnspan=3, sticky='nsew')
    frm.rowconfigure(8, weight=1)

    # Copyright, website, and version labels below log
    copyright_font = (None, 10)
    copyright_lbl = ttk.Label(frm, text="© Jason Brodkey", font=copyright_font, anchor='w', justify='left')
    copyright_lbl.grid(row=9, column=0, sticky='w', pady=(4, 0))

    def open_website(event=None):
        webbrowser.open_new_tab('https://www.editcandy.com')

    website_lbl = ttk.Label(frm, text="www.editcandy.com", font=copyright_font, foreground="#4ea3ff", cursor="hand2")
    website_lbl.grid(row=9, column=0, columnspan=3, pady=(4, 0))
    website_lbl.bind("<Button-1>", open_website)

    version_lbl = ttk.Label(frm, text=f"v{__version__}", font=copyright_font, anchor='e', justify='right')
    version_lbl.grid(row=9, column=2, sticky='e', pady=(4, 0))

    frm.columnconfigure(0, weight=1)

    # Redirect stdout to log with smart carriage return handling
    class StdoutRedirector:
        def __init__(self):
            self.last_was_carriage_return = False
        
        def write(self, message):
            if not message:
                return
            
            # Handle carriage return (\r) - used by progress bars to update same line
            if '\r' in message:
                # Split by \r and process each part
                parts = message.split('\r')
                for i, part in enumerate(parts):
                    if not part.strip():
                        continue
                    
                    if i > 0 or self.last_was_carriage_return:
                        # Replace last line in log
                        log_text.configure(state='normal')
                        log_text.delete("end-2l", "end-1l")
                        log_text.configure(state='disabled')
                    
                    if part.strip():
                        log(part.rstrip('\n'))
                
                self.last_was_carriage_return = True
            else:
                # Normal output
                if message.strip():
                    log(message.rstrip('\n'))
                self.last_was_carriage_return = False
        
        def flush(self):
            pass

    sys.stdout = StdoutRedirector()

    root.mainloop()

def main():
    """Main entry point"""
    # Handle --version flag
    if len(sys.argv) > 1 and sys.argv[1] in ('--version', '-v'):
        print(f"WAVsToAAF v{__version__}")
        return 0
    
    # Check if we should run in interactive mode (no arguments provided)
    if len(sys.argv) == 1:
        return interactive_mode()
    
    # Use argparse for command-line mode
    parser = argparse.ArgumentParser(
        description="Convert WAV files to Advanced Authoring Format (AAF). Embedded audio is the default; use --linked to reference external WAV files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./audio_files ./aaf_output    # Process directory (embedded AAFs)
  %(prog)s ./audio_files                 # Output to ./aaf_output (embedded)
  %(prog)s                               # Process current dir (embedded)
  %(prog)s -f input.wav output.aaf       # Process single file (embedded)
  %(prog)s ./audio_files --linked        # Create linked AAFs referencing WAVs

NOTE: WAVsToAAF intentionally accepts PCM WAV files only (extensions: .wav, .wave). Other audio formats are not supported.
        """
    )
    
    parser.add_argument('input', nargs='?', default=None,
                        help='Input directory or file (if not provided, interactive mode is used)')
    parser.add_argument('output', nargs='?', default=None,
                        help='Output directory or file (if not provided, interactive mode is used)')
    parser.add_argument('-f', '--file', action='store_true',
                        help='Process single file instead of directory')
    parser.add_argument('--emit-ale', action='store_true',
                        help='Also write an ALE for batch importing in Media Composer (directory mode only)')
    parser.add_argument('--one-aaf', action='store_true',
                        help='In directory mode, write one AAF containing all clips instead of one-per-clip (only applies with --linked)')
    # Embedded AAFs are now the default. Use --linked to create linked AAFs.
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--linked', action='store_true',
                        help='Create linked AAFs (reference external files). Use when you prefer smaller AAFs that reference the original WAVs')
    mode_group.add_argument('--embedded', action='store_true',
                        help='(Default) Create embedded AAFs. Multi-channel WAVs will be split into per-channel mono embeds for best Avid compatibility')
    parser.add_argument('--relative-locators', action='store_true',
                        help='Use relative paths in locators (e.g., "./filename.wav") to eliminate locate prompts')
    parser.add_argument('--link-mode', choices=['import','pcm'], default='import',
                        help="Link style for linked AAFs: 'import' (ImportDescriptor chain) or 'pcm' (PCMDescriptor linked)")
    parser.add_argument('--near-sources', action='store_true',
                        help='Save per-clip AAFs next to their source WAV files')
    parser.add_argument('--tape-mode', action='store_true',
                        help='Use TapeDescriptor structure (like ALE-exported AAFs) instead of ImportDescriptor')
    parser.add_argument('-v', '--version', action='version',
                        version=f'WAVsToAAF {__version__}')

    parser.add_argument('--ucs-exact', action='store_true',
                        help='Only use exact UCS ID filename matches (disable fuzzy UCS guessing).')
    parser.add_argument('--ucs-min-score', type=float, default=25.0,
                        help='Score threshold under which fuzzy UCS matches will be recorded to a low-confidence report (default: 25.0)')
    
    # Note: WAVsToAAF intentionally only supports PCM WAV files (.wav, .wave).
    # Other audio formats (AIFF, MP3, FLAC, etc.) are not supported by design.
    args = parser.parse_args()
    
    # If no input provided, use interactive mode
    if args.input is None:
        return interactive_mode()
    
    # For single file processing, auto-generate output path if not provided
    output_path = args.output
    if args.file and output_path is None:
        # Create AAFs subdirectory in the same directory as the WAV
        input_dir = os.path.dirname(args.input)
        aaf_dir = os.path.join(input_dir, 'AAFs')
        output_path = os.path.join(aaf_dir, os.path.splitext(os.path.basename(args.input))[0] + '.aaf')
    
    # Default to embedded AAFs. If user explicitly provided --linked, use linked.
    embed_audio = True if not args.linked else False

    # UCS matching mode: default allows fuzzy guessing; --ucs-exact restricts to exact-ID filename matches only
    allow_ucs_guess = not getattr(args, 'ucs_exact', False)
    
    processor = WAVsToAAFProcessor()
    # configure processor with UCS low confidence threshold
    processor._ucs_min_score = float(getattr(args, 'ucs_min_score', 25.0))
    
    if args.file:
        return processor.process_single_file(args.input, output_path, embed_audio=embed_audio,
                                           link_mode=args.link_mode, relative_locators=args.relative_locators,
                                           allow_ucs_guess=allow_ucs_guess)
    else:
        return processor.process_directory(args.input, output_path, embed_audio=embed_audio,
                                          link_mode=args.link_mode, emit_ale=args.emit_ale, 
                                          one_aaf=args.one_aaf, near_sources=args.near_sources, 
                                          tape_mode=args.tape_mode, relative_locators=args.relative_locators,
                                          allow_ucs_guess=allow_ucs_guess)

def interactive_mode() -> int:
    """Interactive mode for user-friendly input prompting"""
    print(f"WAVsToAAF v{__version__} - Convert WAV files to AAF format")
    print("Copyright (c) 2025 Jason Brodkey. All rights reserved.")
    print()
    
    # Prompt for input path
    while True:
        raw_input = input("Enter the path to the WAV directory or single WAV file: ").strip()
        if not raw_input:
            print("Please enter a valid path.")
            continue
        
        # Expand user path and handle quotes
        input_path = sanitize_path(raw_input)
        
        if os.path.exists(input_path):
            break
        else:
            print(f"Path does not exist: {input_path}")
            print("Please try again.")
    
    # Determine if it's a file or directory
    is_single_file = os.path.isfile(input_path)
    
    # Prompt for output path
    if is_single_file:
        # Create AAFs subdirectory in the same directory as the WAV
        input_dir = os.path.dirname(input_path)
        aaf_dir = os.path.join(input_dir, 'AAFs')
        default_output = os.path.join(aaf_dir, os.path.splitext(os.path.basename(input_path))[0] + '.aaf')
        raw_output = input(f"Enter the output AAF file path (RETURN for '{default_output}'): ").strip()
        output_path = sanitize_path(raw_output) if raw_output else default_output
    else:
        # For directories, default to None to let process_directory use its built-in logic (AAFs one level above)
        default_output = "None (will create AAFs directory one level above input)"
        raw_output = input(f"Enter the output directory (RETURN for '{default_output}'): ").strip()
        output_path = sanitize_path(raw_output) if raw_output else None
    
    print()
    print(f"Input: {input_path}")
    print(f"Output: {output_path if output_path else 'Will be auto-generated'}")
    print()
    
    # Process the files
    processor = WAVsToAAFProcessor()
    
    if is_single_file:
        return processor.process_single_file(input_path, output_path)
    else:
        return processor.process_directory(input_path, output_path)

def sanitize_path(path_str: str) -> str:
    """Normalize a path string coming from user input"""
    if path_str is None:
        return path_str
    
    s = path_str.strip()
    
    # Remove surrounding matching quotes
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1]
    
    # Expand user path (~) and environment variables
    s = os.path.expanduser(os.path.expandvars(s))
    
    try:
        s = os.path.abspath(s)
    except Exception:
        pass
    
    return s

if __name__ == "__main__":
    # Check for --gui flag to launch GUI mode
    if '--gui' in sys.argv:
        sys.argv.remove('--gui')
        launch_gui()
    else:
        sys.exit(main())