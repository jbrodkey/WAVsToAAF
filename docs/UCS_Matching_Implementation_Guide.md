# UCS Category Matching Implementation Guide

## Overview

This document describes the algorithm used in WAVsToAAF for matching audio filenames and descriptions to Universal Category System (UCS) categories. The goal is to enable other tools to implement the same fuzzy matching logic for consistent categorization across workflows.

---

## Data Source

**UCS CSV Format:**
- **Location:** `data/UCS_v8.2.1_Full_List.csv`
- **Required Columns:**
  - `Category` – Primary category (e.g., "AIR", "ANIMAL")
  - `SubCategory` – Subcategory (e.g., "BLOW", "BIRD")
  - `CatID` or `ID` or `CatShort` – Short ID (e.g., "AIRBlow", "ANMLBird")
  - `Explanations` or `Description` – Explanation text
  - `Synonyms - Comma Separated` or `Keywords` – Comma-separated keyword list

**Load all rows** into a dictionary indexed by UCS ID for fast lookup.

---

## Two-Tier Matching Strategy

### 1. **Exact ID Prefix Match** (Priority 1 – Score: 100.0)

Check if the **filename** (without extension) **starts with** a known UCS ID.

**Example:**
- Filename: `AMBMisc_Hotel_Elevator_Ride.wav`
- UCS ID: `AMBMisc`
- Match: **YES** → Return `AMBMisc` with score 100.0

**Why:** Many professional libraries prefix files with UCS IDs. This is the most reliable match.

**Implementation:**
```python
filename_no_ext = filename.replace('.wav', '').replace('.wave', '')
for ucs_id in ucs_database.keys():
    if filename_no_ext.startswith(ucs_id):
        return {
            'id': ucs_id,
            'score': 100.0,
            'category': ucs_database[ucs_id]['category'],
            'subcategory': ucs_database[ucs_id]['subcategory'],
            'full_name': ucs_database[ucs_id]['full_name']
        }
```

---

### 2. **Fuzzy Text Analysis** (Priority 2 – Score: 0.0 to ~50.0+)

If no exact ID prefix is found, analyze the **combined text** (filename + description) and **score** each UCS entry based on keyword matches.

**Text Preprocessing:**
1. Convert to lowercase
2. Remove file extensions (`.wav`, `.wave`)
3. Replace separators (`_`, `-`, `.`) with spaces
4. Split into words

**Example:**
- Input: `door_close_wood_heavy.wav`
- Processed: `door close wood heavy`

---

## Scoring Algorithm

For each UCS entry, calculate a **cumulative match score** based on these criteria:

| Match Type | Condition | Points |
|------------|-----------|--------|
| **Full Name Match** | UCS `full_name` appears in text | +10.0 |
| **Category Match** | UCS `category` appears in text | +5.0 |
| **Subcategory Match** | UCS `subcategory` appears in text | +7.0 |
| **Keyword Match** | Any UCS `keyword` appears in text | +3.0 per keyword |
| **Exact Word Match (Full Name)** | Any text word matches a word in `full_name` | +2.0 per word |
| **Exact Word Match (Category)** | Any text word matches a word in `category` | +1.5 per word |
| **Exact Word Match (Subcategory)** | Any text word matches a word in `subcategory` | +1.5 per word |
| **Partial Word Match** | Text word partially matches a name word (both >3 chars) | +0.5 per match |

**Notes:**
- Only words longer than **2 characters** count for exact matches.
- Only words longer than **3 characters** count for partial matches.
- Scores are **cumulative** (multiple matches add up).

---

## Example Scoring

**File:** `door_close_heavy.wav`  
**Description:** `Wooden door slam`

**UCS Entry:** `DOORClos` (Category: "DOOR", SubCategory: "CLOSE")

| Check | Match | Points |
|-------|-------|--------|
| Full Name "door close" in text? | YES | +10.0 |
| Category "door" in text? | YES | +5.0 |
| Subcategory "close" in text? | YES | +7.0 |
| Keywords (e.g., "slam", "shut")? | YES ("slam") | +3.0 |
| Word "door" matches? | YES (category word) | +1.5 |
| Word "close" matches? | YES (subcategory word) | +1.5 |
| **Total Score** | | **28.0** |

**UCS Entry:** `WOODImpc` (Category: "WOOD", SubCategory: "IMPACT")

| Check | Match | Points |
|-------|-------|--------|
| Full Name "wood impact" in text? | NO | 0.0 |
| Category "wood" in text? | NO | 0.0 |
| Subcategory "impact" in text? | NO | 0.0 |
| Word "wooden" partial match "wood"? | YES | +0.5 |
| **Total Score** | | **0.5** |

**Winner:** `DOORClos` with score 28.0

---

## Result Selection

1. **Sort** all UCS entries by score (descending).
2. **Primary Match:** Return the entry with the **highest score**.
3. **Alternative Matches:** Return up to 5 additional entries with scores ≥ 70% of the best score.

**Example:**
- Best: `DOORClos` (28.0)
- Alternative threshold: 28.0 × 0.7 = 19.6
- Alternatives: Any entries scoring ≥ 19.6

---

## Confidence Thresholds

**Interpretation:**
- **Score 100.0** – Exact UCS ID prefix (highest confidence)
- **Score 25.0+** – Strong fuzzy match (high confidence)
- **Score 10.0 – 24.9** – Moderate match (medium confidence)
- **Score < 10.0** – Weak match (low confidence)

**Low-Confidence Reporting:**
- By default, matches with score **< 25.0** are flagged as "low confidence."
- These should be written to a separate report (e.g., `ucs_low_confidence.csv`) for manual review.

---

## Implementation Pseudocode

```python
def categorize_sound(filename, description, allow_guess=True):
    # Step 1: Exact ID prefix check
    filename_no_ext = remove_extension(filename)
    for ucs_id in ucs_database:
        if filename_no_ext.startswith(ucs_id):
            return create_result(ucs_id, score=100.0)
    
    # Step 2: If no exact match and guessing disabled, return empty
    if not allow_guess:
        return {}
    
    # Step 3: Fuzzy text analysis
    text = preprocess_text(f"{filename} {description}")
    
    best_matches = []
    for ucs_id, ucs_info in ucs_database.items():
        score = calculate_score(text, ucs_info)
        if score > 0:
            best_matches.append((score, ucs_id, ucs_info))
    
    # Step 4: Sort and return
    best_matches.sort(reverse=True)
    
    if not best_matches:
        return {}
    
    best_score, best_id, best_info = best_matches[0]
    
    alternatives = [
        (s, id, info) for s, id, info in best_matches[1:6]
        if s >= best_score * 0.7
    ]
    
    return {
        'primary_category': create_result(best_id, score=best_score),
        'alternative_categories': [create_result(id, s) for s, id, _ in alternatives]
    }


def calculate_score(text, ucs_info):
    score = 0.0
    
    # Full name match
    if ucs_info['full_name'].lower() in text:
        score += 10.0
    
    # Category/subcategory match
    if ucs_info['category'].lower() in text:
        score += 5.0
    if ucs_info['subcategory'].lower() in text:
        score += 7.0
    
    # Keyword match
    for keyword in ucs_info['keywords']:
        if keyword.lower() in text:
            score += 3.0
    
    # Word-level matches
    text_words = set(text.split())
    name_words = set(ucs_info['full_name'].lower().split())
    category_words = set(ucs_info['category'].lower().split())
    subcategory_words = set(ucs_info['subcategory'].lower().split())
    
    for word in text_words:
        if len(word) > 2:
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


def preprocess_text(text):
    text = text.lower()
    text = text.replace('.wav', '').replace('.wave', '')
    text = text.replace('_', ' ').replace('-', ' ').replace('.', ' ')
    return text
```

---

## Output Format

**Primary Match:**
```json
{
  "primary_category": {
    "id": "DOORClos",
    "full_name": "Door Close",
    "category": "DOOR",
    "subcategory": "CLOSE",
    "score": 28.0
  }
}
```

**With Alternatives:**
```json
{
  "primary_category": {
    "id": "DOORClos",
    "full_name": "Door Close",
    "category": "DOOR",
    "subcategory": "CLOSE",
    "score": 28.0
  },
  "alternative_categories": [
    {
      "id": "DOORSlam",
      "full_name": "Door Slam",
      "category": "DOOR",
      "subcategory": "SLAM",
      "score": 20.5
    }
  ]
}
```

---

## Configuration Options

- **`allow_guess`** (boolean): Enable fuzzy matching. If `False`, only exact ID prefix matches are returned.
- **`min_confidence_threshold`** (float): Minimum score to consider a match valid (default: 0.0). Raise to 10.0 or 25.0 for stricter matching.
- **`low_confidence_threshold`** (float): Score below which matches are flagged as "low confidence" (default: 25.0).

---

## Edge Cases

1. **No Matches Found:** Return empty result `{}`.
2. **Multiple Exact ID Prefixes:** Return the **longest matching prefix** (e.g., `AMBMiscInt` beats `AMBMisc`).
3. **Ties in Fuzzy Scoring:** If multiple entries have the same top score, return **all tied entries** as alternatives.
4. **Very Short Filenames:** Fuzzy matching may produce low scores. Consider a minimum filename length threshold (e.g., 5 characters).

---

## Testing Recommendations

**Test Cases:**

| Filename | Expected Match | Expected Score |
|----------|----------------|----------------|
| `AMBMisc_Background.wav` | `AMBMisc` | 100.0 |
| `door_close_heavy.wav` | `DOORClos` | 25.0+ |
| `footsteps_concrete.wav` | `FOOTConc` | 20.0+ |
| `x.wav` (very short) | (no match) | 0.0 |
| `random_noise_123.wav` | (varies) | < 10.0 |

---

## Integration Notes

- **AAF/ALE Tools:** Write UCS fields into metadata columns: `Category`, `SubCategory`, `UCS_ID`, `UCS_Match_Score`.
- **Low-Confidence CSV:** Export matches with score < 25.0 to `ucs_low_confidence.csv` for review.
- **Batch Processing:** Process all files in a directory, collect low-confidence items, and write a single report at the end.

---

## Version History

- **v1.0 (2025-12-02):** Initial implementation guide based on WAVsToAAF v1.0.0 algorithm.

---

## References

- **UCS Specification:** Universal Category System v8.2.1 (https://universalcategorysystem.com/)
- **WAVsToAAF Source:** `wav_to_aaf.py` (class `UCSProcessor`)

---

**Questions or improvements?** Update this guide as the algorithm evolves.
