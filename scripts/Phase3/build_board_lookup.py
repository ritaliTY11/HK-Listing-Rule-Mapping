"""
Phase 3 - Step 1: Board lookup table

Objective (per Milestones.txt, Phase 3):
    Identify and separate major prospectus sections, classified by board
    (Main Board / GEM). This script builds the board-classification half
    of that: a lookup table keyed by stock code, sourced from the Phase 1
    collection log (which already records board type per filing).

Input:
    Phase 1 log CSV with columns:
    stock_code,company_name,date_filed,board,headline,pdf_url,filename,downloaded,error

Output:
    data/board_lookup.json
    { "09680": {"board": "Main Board", "company_name": "...", "filename": "...", "date_filed": "..."}, ... }

Design notes / assumptions (per prior discussion - update Milestones.txt if these change):
    - Stock codes are normalized to 5-digit zero-padded strings (e.g. "09680"),
      matching the canonical format agreed for joining log <-> raw text later.
    - Only rows with downloaded == "yes" and no error are included, since rows
      that failed to download have no raw text to join against anyway.
    - A stock code can legitimately appear more than once in the log (e.g. a
      GEM company that later transferred to Main Board, or supplemental /
      amended listing documents for the same IPO). Rather than silently
      overwriting, this script keeps the chronologically LATEST row as the
      canonical entry per stock code, and logs every stock code with more
      than one qualifying row so you can manually check whether it's a
      genuine board transfer, a duplicate filing, or a log error.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

# --- Update this path to wherever your Phase 1 log actually lives ---
LOG_PATH = Path("logs/download_log.csv")
OUTPUT_PATH = Path("data/board_lookup.json")


def normalize_code(raw_code: str) -> str:
    """Zero-pad a stock code to the canonical 5-digit format."""
    digits = str(raw_code).strip().lstrip("0")
    if digits == "":
        digits = "0"
    return digits.zfill(5)


def build_lookup(log_path: Path):
    rows_by_code = defaultdict(list)
    skipped = 0

    with log_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            downloaded_ok = row.get("downloaded", "").strip().lower() == "yes"
            has_error = row.get("error", "").strip() != ""

            if not downloaded_ok or has_error:
                skipped += 1
                continue

            code = normalize_code(row["stock_code"])
            rows_by_code[code].append(row)

    lookup = {}
    multi_entry_codes = {}

    for code, rows in rows_by_code.items():
        # Sort chronologically; keep the latest as canonical.
        rows_sorted = sorted(rows, key=lambda r: r.get("date_filed", ""))
        canonical = rows_sorted[-1]

        lookup[code] = {
            "board": canonical["board"].strip(),
            "company_name": canonical["company_name"].strip(),
            "filename": canonical["filename"].strip(),
            "date_filed": canonical.get("date_filed", "").strip(),
        }

        if len(rows_sorted) > 1:
            multi_entry_codes[code] = [
                {
                    "filename": r["filename"].strip(),
                    "date_filed": r.get("date_filed", "").strip(),
                    "board": r["board"].strip(),
                    "headline": r.get("headline", "").strip(),
                }
                for r in rows_sorted
            ]

    return lookup, multi_entry_codes, skipped


def main():
    if not LOG_PATH.exists():
        print(f"Log file not found at {LOG_PATH} -- update LOG_PATH at the top of this script.")
        return

    lookup, multi_entry_codes, skipped = build_lookup(LOG_PATH)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(lookup, f, indent=2, ensure_ascii=False)

    print(f"Built lookup for {len(lookup)} stock codes -> {OUTPUT_PATH}")
    print(f"Skipped {skipped} rows (not downloaded, or flagged with an error).")

    if multi_entry_codes:
        print(f"\nNOTE: {len(multi_entry_codes)} stock code(s) had more than one qualifying log row.")
        print("Kept the chronologically latest as canonical. Review these manually --")
        print("they may be genuine GEM-to-Main-Board transfers, amended filings, or log duplicates:\n")
        for code, entries in multi_entry_codes.items():
            print(f"  {code}:")
            for e in entries:
                print(f"    {e['date_filed']}  {e['board']:<11}  {e['filename']}  ({e['headline']})")


if __name__ == "__main__":
    main()
