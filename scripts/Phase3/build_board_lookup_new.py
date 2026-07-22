"""
Phase 3 - Step 1 (filename-only version): Board lookup table, no Phase 1 log dependency

Rationale: the Phase 1 log is currently outdated (not being fixed right now).
Rather than trust it, this loops through the actual filenames already saved
on disk -- no file content is opened, no log is read -- and derives:

    1. Stock code, parsed directly from the filename.
    2. Board, derived from the stock code prefix ("08" = GEM, else Main Board).

Output:
    data/board_lookup.json
    {
      "by_filename": {
        "<filename-without-extension>": {
          "stock_code": "03952",
          "board": "Main Board",
          "date_filed": "20260622",   # parsed straight from the filename
          "is_latest": true           # true only for the most recent filing per code
        },
        ...
      },
      "by_stock_code": {
        "03952": ["<filename_1>", "<filename_2>", ...]   # chronological order
      }
    }

Confirmed filename format: "<5-digit stock code>_<YYYYMMDD>" (e.g. "03952_20260622"),
which conveniently also resolves the earlier open item about not having a reliable
date to determine "latest" version without the Phase 1 log.
"""

import json
import re
from pathlib import Path

# --- Update these ---
INPUT_DIR = Path("data/extracted_text")   # directory to scan
FILE_GLOB = "*.txt"                       # file extension to match
OUTPUT_PATH = Path("data/board_lookup.json")

# Confirmed filename format: "<5-digit stock code>_<YYYYMMDD>", e.g. "03952_20260622"
FILENAME_PATTERN = re.compile(r"^(\d{4,5})_(\d{8})$")


def normalize_code(raw_code: str) -> str:
    digits = str(raw_code).strip().lstrip("0")
    if digits == "":
        digits = "0"
    return digits.zfill(5)


def derive_board(normalized_code: str) -> str:
    return "GEM" if normalized_code.startswith("08") else "Main Board"


def parse_filename(stem: str):
    """Returns (stock_code, date_str) or (None, None) if the filename doesn't match."""
    match = FILENAME_PATTERN.match(stem)
    if not match:
        return None, None
    return normalize_code(match.group(1)), match.group(2)


def build_lookup(input_dir: Path, file_glob: str):
    by_filename = {}
    code_to_entries = {}
    failures = []

    for path in sorted(input_dir.glob(file_glob)):
        code, date_str = parse_filename(path.stem)
        if code is None:
            failures.append(path.name)
            continue

        board = derive_board(code)
        code_to_entries.setdefault(code, []).append((path.stem, date_str, board))

    by_stock_code = {}
    for code, entries in code_to_entries.items():
        # Sort chronologically using the date embedded in the filename.
        entries_sorted = sorted(entries, key=lambda e: e[1])
        filenames_in_order = [e[0] for e in entries_sorted]
        by_stock_code[code] = filenames_in_order

        for i, (fname, date_str, board) in enumerate(entries_sorted):
            by_filename[fname] = {
                "stock_code": code,
                "board": board,
                "date_filed": date_str,
                "is_latest": i == len(entries_sorted) - 1,
            }

    return {"by_filename": by_filename, "by_stock_code": by_stock_code}, failures


def main():
    if not INPUT_DIR.exists():
        print(f"Input directory not found at {INPUT_DIR} -- update INPUT_DIR at the top of this script.")
        return

    lookup, failures = build_lookup(INPUT_DIR, FILE_GLOB)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(lookup, f, indent=2, ensure_ascii=False)

    print(f"Built lookup for {len(lookup['by_filename'])} documents "
          f"across {len(lookup['by_stock_code'])} stock codes -> {OUTPUT_PATH}")

    multi = {c: fs for c, fs in lookup["by_stock_code"].items() if len(fs) > 1}
    if multi:
        print(f"\n{len(multi)} stock code(s) matched more than one file:")
        for code, files in multi.items():
            print(f"  {code}: {files}")

    if failures:
        print(f"\n{len(failures)} filename(s) didn't match the expected pattern:")
        for name in failures[:20]:
            print(f"  {name}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more")


if __name__ == "__main__":
    main()
