#!/usr/bin/env python3
"""
WAVsToAAF - Convert WAV files to simplified AAF XML format

Copyright (c) 2025 Jason Brodkey. All rights reserved.

This script scans directories for WAV files, extracts comprehensive audio metadata 
including BEXT, LIST-INFO chunks, embedded XML data, and UCS categorization, then 
generates simplified AAF XML files suitable for media management workflows.

Supported metadata:
- Standard WAV properties (sample rate, channels, duration, etc.)
- BEXT chunk (broadcast audio metadata)
- LIST-INFO chunks (IART, ICMT, ICOP, INAM, etc.)
- XML chunks (EBU Core, BWF MetaEdit, Pro Tools, etc.)
- UCS categorization (Universal Category System)

Usage:
    python wav_to_aaf.py [input_directory] [output_directory]
    
Examples:
    python wav_to_aaf.py ./audio_files ./aaf_output
    python wav_to_aaf.py /path/to/wavs  # outputs to ./aaf_output
    python wav_to_aaf.py               # scans current dir, outputs to ./aaf_output

Author: Jason Brodkey
Version: 1.2.0
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
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom

__version__ = "1.2.0"
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
    
    def categorize_sound(self, filename: str, description: str = "") -> Dict:
        """Categorize sound based on filename and description"""
        if not self.ucs_loaded:
            return {}
        
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
    """Generate simplified AAF XML files from WAV metadata"""
    
    def __init__(self):
        self.namespace = "http://www.aafassociation.org/aafxml"
    
    def create_aaf_xml(self, wav_metadata: Dict, bext_metadata: Dict, info_metadata: Dict = None, xml_metadata: Dict = None, ucs_metadata: Dict = None) -> str:
        """Create simplified AAF XML from WAV, BEXT, INFO, XML, and UCS metadata"""
        
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
        
        # Add LIST-INFO metadata if available
        if info_metadata:
            info_elem = ET.SubElement(master_mob, "InfoMetadata")
            
            # Standard INFO chunk mappings
            info_mappings = {
                'IART': 'Artist',
                'ICMT': 'Comment', 
                'ICOP': 'Copyright',
                'ICRD': 'CreationDate',
                'IENG': 'Engineer',
                'IGNR': 'Genre',
                'IKEY': 'Keywords',
                'IMED': 'Medium',
                'INAM': 'Title',
                'IPRD': 'Product',
                'ISBJ': 'Subject',
                'ISFT': 'Software',
                'ISRC': 'Source',
                'ISRF': 'SourceForm',
                'ITCH': 'Technician'
            }
            
            for chunk_id, value in info_metadata.items():
                if value:
                    # Use standard mapping if available, otherwise use chunk ID
                    element_name = info_mappings.get(chunk_id, chunk_id)
                    elem = ET.SubElement(info_elem, element_name)
                    elem.text = str(value)
                    # Also store original chunk ID as attribute for reference
                    if chunk_id in info_mappings:
                        elem.set("chunkId", chunk_id)
        
        # Add XML metadata if available
        if xml_metadata:
            xml_elem = ET.SubElement(master_mob, "XmlMetadata")
            
            # Group XML metadata by prefix (ebucore, bwfmetaedit, etc.)
            xml_groups = {}
            for key, value in xml_metadata.items():
                if '_' in key:
                    prefix, field = key.split('_', 1)
                    if prefix not in xml_groups:
                        xml_groups[prefix] = {}
                    xml_groups[prefix][field] = value
                else:
                    # Items without prefix go to generic group
                    if 'generic' not in xml_groups:
                        xml_groups['generic'] = {}
                    xml_groups['generic'][key] = value
            
            # Create sub-elements for each XML type
            for xml_type, fields in xml_groups.items():
                if fields:  # Only create section if it has data
                    type_elem = ET.SubElement(xml_elem, f"{xml_type.capitalize()}Data")
                    
                    for field_name, field_value in fields.items():
                        if field_value and str(field_value).strip():
                            # Clean field name for XML element
                            clean_field = re.sub(r'[^a-zA-Z0-9_]', '', field_name)
                            if clean_field:
                                field_elem = ET.SubElement(type_elem, clean_field.capitalize())
                                field_elem.text = str(field_value)
        
        # Add UCS metadata if available
        if ucs_metadata:
            ucs_elem = ET.SubElement(master_mob, "UCSMetadata")
            
            # Primary category
            if 'primary_category' in ucs_metadata:
                primary = ucs_metadata['primary_category']
                primary_elem = ET.SubElement(ucs_elem, "PrimaryCategory")
                ET.SubElement(primary_elem, "ID").text = primary['id']
                ET.SubElement(primary_elem, "FullName").text = primary['full_name']
                ET.SubElement(primary_elem, "Category").text = primary['category']
                ET.SubElement(primary_elem, "SubCategory").text = primary['subcategory']
                ET.SubElement(primary_elem, "MatchScore").text = str(primary['score'])
            
            # Alternative categories
            if 'alternative_categories' in ucs_metadata and ucs_metadata['alternative_categories']:
                alternatives_elem = ET.SubElement(ucs_elem, "AlternativeCategories")
                for alt in ucs_metadata['alternative_categories']:
                    alt_elem = ET.SubElement(alternatives_elem, "Category")
                    ET.SubElement(alt_elem, "ID").text = alt['id']
                    ET.SubElement(alt_elem, "FullName").text = alt['full_name']
                    ET.SubElement(alt_elem, "Category").text = alt['category']
                    ET.SubElement(alt_elem, "SubCategory").text = alt['subcategory']
                    ET.SubElement(alt_elem, "MatchScore").text = str(alt['score'])
        
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
        self.ucs_processor = UCSProcessor()
    
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
                
                if not wav_metadata:
                    print(f"  Skipping {wav_file.name}: Could not read metadata")
                    continue
                
                # Extract all metadata chunks
                all_chunks = self.extractor.extract_all_metadata_chunks(str(wav_file))
                
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
                    info_items = [f"{k}={v}" for k, v in info_metadata.items() if v]
                    if info_items:
                        print(f"  INFO metadata: {', '.join(info_items[:3])}{'...' if len(info_items) > 3 else ''}")
                
                if xml_metadata:
                    xml_types = set(k.split('_')[0] for k in xml_metadata.keys() if '_' in k)
                    if xml_types:
                        print(f"  XML metadata: {', '.join(xml_types)}")
                
                # UCS categorization
                ucs_metadata = self.ucs_processor.categorize_sound(
                    wav_file.name, 
                    bext_metadata.get('description', '')
                )
                
                if ucs_metadata and 'primary_category' in ucs_metadata:
                    category = ucs_metadata['primary_category']
                    print(f"  UCS Category: {category['category']} > {category['subcategory']} ({category['score']:.1f})")
                
                # Generate AAF XML
                aaf_xml = self.generator.create_aaf_xml(wav_metadata, bext_metadata, info_metadata, xml_metadata, ucs_metadata)
                
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
            ucs_metadata = self.ucs_processor.categorize_sound(
                Path(wav_file).name,
                bext_metadata.get('description', '')
            )
            
            if ucs_metadata and 'primary_category' in ucs_metadata:
                category = ucs_metadata['primary_category']
                print(f"UCS Category: {category['category']} > {category['subcategory']} ({category['score']:.1f})")
            
            # Generate AAF XML
            aaf_xml = self.generator.create_aaf_xml(wav_metadata, bext_metadata, info_metadata, xml_metadata, ucs_metadata)
            
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