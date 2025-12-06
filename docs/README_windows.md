# WAVsToAAF (Windows) - Readme
**Version 1.0.0**

## Overview

WAVsToAAF generates embedded AAF files from WAV metadata (BEXT, LIST-INFO, embedded XML). It will automatically interpret UCS category & subcategory when files are named with UCS prefixes. And it can infer UCS category/subcategory when no UCS ID prefix is present in the filename.

## Quick Start

1. Run **WAVsToAAF.exe**
2. Choose input WAVs or a folder, and an output directory
3. Click Run; find AAF outputs in your chosen location

## UCS Inference (Best-Guess)

When filenames lack a UCS ID prefix, the app optionally infers category/subcategory by scoring text from:
- Filename words
- BEXT Description
- LIST-INFO fields
- Embedded XML text (when present)

### How Scoring Works

The app scores each UCS entry using three criteria:
- Whole-word overlaps with the UCS Subcategory (highest weight)
- Keyword/synonym overlaps from the UCS list (medium weight)
- Partial string matches on the Subcategory (lower weight, 3+ chars)


## Support

Releases: https://editcandy.com  
Issues: jason@editcandy.com
