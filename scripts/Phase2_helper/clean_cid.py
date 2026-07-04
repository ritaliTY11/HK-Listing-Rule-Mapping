"""
CID Token Cleaner
HKEX Prospectus Knowledge Base — Phase 2 helper

Removes all (cid:X) tokens from extracted .txt files in place.
Run this once after extract_text.py completes.

Usage:
    python clean_cid.py
"""

import os
import re

TEXT_DIR = "data/extracted_text"

cid_pattern = re.compile(r'(\(cid:\d+\))+')

files = [f for f in os.listdir(TEXT_DIR) if f.endswith(".txt")]
files.sort()

print(f"Found {len(files)} text files. Cleaning...\n")

total_replacements = 0

for filename in files:
    path = os.path.join(TEXT_DIR, filename)

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    cleaned, count = cid_pattern.subn(" ", original)

    # Collapse any runs of multiple spaces left behind
    cleaned = re.sub(r' {2,}', ' ', cleaned)

    if count > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"  {filename}: {count} replacement(s)")
        total_replacements += count
    else:
        print(f"  {filename}: clean")

print(f"\nDone. Total replacements across all files: {total_replacements}")