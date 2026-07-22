# """
# Phase 3 - Step 4/5: Prospectus structuring (heading detection + sectioning)

# Core idea: the table of contents lists each heading with its PRINTED page
# number (e.g. "Risk Factors . . . 33"), and the scraped text already contains
# that same printed page number as a standalone footer line on every page
# (e.g. "- 33 -"). So instead of guessing where a heading starts, we:

#   1. Index every printed-page-number footer in the raw text -> exact text
#      position of the start of that printed page.
#   2. Parse the ToC into (heading, printed_page_label) pairs.
#   3. For each ToC entry, jump straight to its printed page (via the index
#      from step 1) and locate the heading as a standalone line there.
#   4. Section content = everything between one heading's PHYSICAL position
#      in the text and the next heading's physical position (headings are
#      re-sorted by where they actually occur, after being located via
#      their ToC page label -- not left in ToC listing order). Within a
#      single prospectus, ToC order and physical body order always match, so
#      this is just "read top to bottom." The fact that DIFFERENT documents
#      in the corpus may order or word their headings differently is a
#      separate concern, handled by the canonical-vocabulary matching in
#      Step 8 below, not by anything in this slicing step.

# This sidesteps needing to know whether a page label is roman, arabic, or
# appendix-style (I-1, II-1, ...) -- it's always compared as a literal string
# match between ToC and footer, never converted.

# Front matter is only the truly un-numbered, non-ToC-listed prefix (cover
# page, "IMPORTANT" notices before the timetable). Anything the ToC actually
# lists -- including "Expected Timetable" and "Contents" itself, which ARE
# page-numbered (roman numerals) and appear as their own ToC entries -- is
# located and sectioned like any other heading, not lumped into front matter.

# Headings that recur across the corpus but are NOT present in every single
# document (e.g. "Waivers from Strict Compliance with the Listing Rules",
# only present when a waiver was actually granted) are captured verbatim
# under their own raw heading text, but deliberately kept OUT of the
# canonical vocabulary -- see KEYWORDS_EXCLUDED_FROM_CANONICAL. Otherwise
# every document without one would show a false "missing section".

# Canonical heading vocabulary is built dynamically across the corpus:
#   - The FIRST document processed seeds the canonical list directly from
#     its own ToC.
#   - Every later document's ToC headings are fuzzy-matched against the
#     canonical list. A genuine miss is logged as a "candidate" and only
#     promoted to canonical once seen in >= 2 separate documents, so a
#     one-off OCR artifact or a single company's oddly-worded heading
#     doesn't pollute the schema.

# KNOWN SIMPLIFICATIONS in this first version (call out for review):
#   - Two-line broken headings are merged via a simple "does line i + line
#     i+1 match better than line i alone" check -- may need tuning on real
#     scraped noise.
#   - Fuzzy match threshold (0.85) is a starting point, not validated
#     against your actual 30-doc manual sample yet.
#   - Duplicate ToC entries (e.g. a sub-item repeated) aren't de-duplicated
#     beyond keeping the first occurrence.
# """

# import bisect
# import difflib
# import json
# import re
# from pathlib import Path

# # --- Update these for your environment ---
# INPUT_DIR = Path("data/extracted_text_sample")
# FILE_GLOB = "*.txt"
# BOARD_LOOKUP_PATH = Path("data/board_lookup.json")
# OUTPUT_DIR = Path("data/structured_prospectuses")
# CANONICAL_HEADINGS_PATH = Path("data/headings/canonical_headings.json")
# CANDIDATE_HEADINGS_PATH = Path("data//headings/candidate_headings.json")

# FUZZY_THRESHOLD = 0.85
# CANDIDATE_PROMOTION_COUNT = 2  # a candidate heading needs this many sightings to become canonical

# # Headings matching any of these keywords (substring match on the normalized,
# # uppercased heading) are captured verbatim but NEVER added to the canonical
# # vocabulary or candidate-promotion tracking. These are real, recurring
# # headings, but they don't appear in every prospectus (e.g. "Waivers from
# # Strict Compliance with the Listing Rules" only shows up when a waiver was
# # actually granted) -- treating them as canonical would falsely flag every
# # document WITHOUT one as missing a section it was never supposed to have.
# KEYWORDS_EXCLUDED_FROM_CANONICAL = ["WAIVER", "INVESTORS", "GEM"]

# PAGE_MARKER_RE = re.compile(r"^=== PAGE (\d+) ===\s*$")
# FOOTER_PAGE_LABEL_RE = re.compile(r"^\s*[\u2013\u2014-]\s*([A-Za-z]{0,3}-?\d+|[ivxlcdmIVXLCDM]+)\s*[\u2013\u2014-]\s*$")
# TOC_LINE_RE = re.compile(r"^(.+?)\s*(?:\.\s*){3,}\s*([ivxlcdmIVXLCDM]+|\d+|[A-Za-z]{1,3}-\d+)\s*$")
# CONTENTS_HEADING_RE = re.compile(r"^\s*CONTENTS\s*$", re.IGNORECASE)

# CHAPTER_18C_KEYWORDS = [
#     "specialist technology company", "chapter 18c",
#     "sophisticated independent investor", "pre-commercial company",
# ]
# CHAPTER_18A_KEYWORDS = [
#     "biotech company", "chapter 18a", "core product",
# ]


# def normalize(text: str) -> str:
#     text = re.sub(r"^\s*(?:[IVXLCDM]+\.|\d+\.|[-*])\s*", "", text.strip())
#     text = re.sub(r"\s+", " ", text)
#     text = text.strip(" .:").upper()
#     return text


# def fuzzy_ratio(a: str, b: str) -> float:
#     return difflib.SequenceMatcher(None, a, b).ratio()


# def build_page_index(lines):
#     """
#     Returns:
#       page_label_positions: dict[label] -> list of line indices where that
#           printed page's footer occurs (usually 1, could repeat if the same
#           label is reused, e.g. multiple "I-1"-style appendix restarts).
#       all_footer_positions: sorted list of every footer line index,
#           regardless of label. Used to bound heading search to the ACTUAL
#           physical page rather than an arbitrary line-count window -- see
#           locate_heading.
#       page_marker_positions: list of (raw_page_num, line_index) from the
#           scraper's own '=== PAGE N ===' markers (currently unused, kept
#           for potential future diagnostics).
#     """
#     page_label_positions = {}
#     all_footer_positions = []
#     page_marker_positions = []

#     for i, line in enumerate(lines):
#         marker_match = PAGE_MARKER_RE.match(line)
#         if marker_match:
#             page_marker_positions.append((int(marker_match.group(1)), i))
#             continue
#         footer_match = FOOTER_PAGE_LABEL_RE.match(line)
#         if footer_match:
#             label = footer_match.group(1)
#             page_label_positions.setdefault(label, []).append(i)
#             all_footer_positions.append(i)

#     return page_label_positions, all_footer_positions, page_marker_positions


# def find_contents_start(lines):
#     for i, line in enumerate(lines):
#         if CONTENTS_HEADING_RE.match(line):
#             return i
#     return None


# def parse_toc(lines, contents_start_idx):
#     """
#     Parse ToC entries starting just after the CONTENTS heading. Real
#     documents commonly have a prose paragraph (e.g. an "IMPORTANT NOTICE
#     TO PROSPECTIVE INVESTORS" notice, or a "Page" column header) between
#     the CONTENTS heading and the actual dot-leader listing -- so this
#     first SEEKS freely (no fail limit) for the first line that matches the
#     ToC pattern, then switches to COLLECTING mode, where two consecutive
#     non-matching lines ends the ToC (heuristic: ToC lines end in a
#     page-number token, body prose essentially never does).
#     """
#     entries = []
#     consecutive_fails = 0
#     collecting = False
#     i = contents_start_idx + 1

#     while i < len(lines):
#         line = lines[i]

#         if PAGE_MARKER_RE.match(line) or not line.strip():
#             i += 1
#             continue

#         match = TOC_LINE_RE.match(line)
#         if match:
#             heading_raw = match.group(1).strip()
#             page_label = match.group(2)
#             if heading_raw:
#                 entries.append((heading_raw, page_label))
#             collecting = True
#             consecutive_fails = 0
#         elif collecting:
#             consecutive_fails += 1
#             if consecutive_fails >= 2:
#                 break
#         # else: still seeking for the first match, keep scanning freely

#         i += 1

#     return entries


# def locate_heading(lines, page_label, heading_raw, page_label_positions, all_footer_positions):
#     """
#     Search the physical page corresponding to page_label for a standalone
#     line matching heading_raw (allowing for a two-line break). Returns
#     (start_line_idx, lines_spanned) or None if not found. lines_spanned is
#     1 for a normal single-line heading, 2 if it was a broken/merged heading.

#     The search window is bounded to the ACTUAL physical page: from just
#     after the PRECEDING footer (anywhere in the document) up to this page's
#     own footer, with a small forward buffer in case the heading sits right
#     at the very top of the next page. This intentionally does NOT use an
#     arbitrary line-count window -- an earlier version did, and a wide
#     enough window could reach back into the ToC's own dot-leader line for
#     this exact heading, which fuzzy-matches closely enough to falsely win
#     over the real (much further away) occurrence.
#     """
#     target_norm = normalize(heading_raw)
#     candidate_footer_indices = page_label_positions.get(page_label, [])

#     for footer_idx in candidate_footer_indices:
#         pos_in_all = bisect.bisect_left(all_footer_positions, footer_idx)
#         prev_footer_idx = all_footer_positions[pos_in_all - 1] if pos_in_all > 0 else -1

#         search_start = prev_footer_idx + 1
#         search_end = min(len(lines), footer_idx + 5)  # small forward buffer only

#         for j in range(search_start, search_end):
#             line = lines[j].strip()
#             if not line or PAGE_MARKER_RE.match(line) or FOOTER_PAGE_LABEL_RE.match(line):
#                 continue

#             single_norm = normalize(line)
#             if single_norm == target_norm or fuzzy_ratio(single_norm, target_norm) >= FUZZY_THRESHOLD:
#                 return j, 1

#             if j + 1 < len(lines):
#                 next_line = lines[j + 1].strip()
#                 if next_line and not PAGE_MARKER_RE.match(next_line) and not FOOTER_PAGE_LABEL_RE.match(next_line):
#                     merged_norm = normalize(line + " " + next_line)
#                     if merged_norm == target_norm or fuzzy_ratio(merged_norm, target_norm) >= FUZZY_THRESHOLD:
#                         return j, 2

#     return None


# def extract_section_text(lines, start_idx, end_idx, heading_norm):
#     """
#     Concatenate lines between start_idx (exclusive of the heading line
#     itself) and end_idx, stripping page markers, footer page-number lines,
#     and any standalone line that repeats the section's own heading
#     (running header).
#     """
#     out = []
#     for line in lines[start_idx:end_idx]:
#         stripped = line.strip()
#         if not stripped:
#             continue
#         if PAGE_MARKER_RE.match(stripped) or FOOTER_PAGE_LABEL_RE.match(stripped):
#             continue
#         if normalize(stripped) == heading_norm:
#             continue
#         out.append(stripped)
#     return "\n".join(out).strip()


# def match_canonical(heading_norm, canonical_headings, aliases):
#     for canonical, alias_list in aliases.items():
#         if heading_norm in alias_list:
#             return canonical
#     best_canonical, best_score = None, 0.0
#     for canonical in canonical_headings:
#         score = fuzzy_ratio(heading_norm, canonical)
#         if score > best_score:
#             best_canonical, best_score = canonical, score
#     if best_score >= FUZZY_THRESHOLD:
#         return best_canonical
#     return None


# def detect_regime_flags(full_text_lower):
#     chapter_18c = any(kw in full_text_lower for kw in CHAPTER_18C_KEYWORDS)
#     chapter_18a = any(kw in full_text_lower for kw in CHAPTER_18A_KEYWORDS)
#     return chapter_18c, chapter_18a


# def structure_document(path: Path, canonical_headings: list, aliases: dict, candidates: dict):
#     text = path.read_text(encoding="utf-8", errors="ignore")
#     lines = text.split("\n")

#     page_label_positions, all_footer_positions, page_marker_positions = build_page_index(lines)
#     contents_idx = find_contents_start(lines)

#     result = {
#         "front_matter": "",
#         "sections": {},
#         "missing_sections": [],
#         "unmatched_headings": [],
#         "candidate_new_headings": [],
#     }

#     if contents_idx is None:
#         # No parseable ToC at all -- store everything as front matter and bail.
#         result["front_matter"] = text.strip()
#         result["unmatched_headings"].append("NO_CONTENTS_HEADING_FOUND")
#         return result

#     toc_entries = parse_toc(lines, contents_idx)

#     # Locate each heading's start position
#     located = []  # list of (raw_name, heading_norm, line_idx, lines_spanned)
#     for heading_raw, page_label in toc_entries:
#         heading_norm = normalize(heading_raw)
#         location = locate_heading(lines, page_label, heading_raw, page_label_positions, all_footer_positions)
#         if location is None:
#             result["unmatched_headings"].append(heading_raw)
#             continue
#         line_idx, lines_spanned = location
#         located.append((heading_raw, heading_norm, line_idx, lines_spanned))

#     located.sort(key=lambda t: t[2])

#     # Front matter cutoff is the earliest LOCATED heading's position -- this
#     # correctly includes "Expected Timetable" and "Contents" itself as real,
#     # page-numbered, ToC-listed sections (per the sample document), NOT as
#     # front matter. Only the truly un-numbered cover/notice pages before
#     # that (which have no ToC entry and no footer) end up as front matter.
#     if located:
#         front_matter_cutoff = located[0][2]
#     else:
#         front_matter_cutoff = contents_idx

#     result["front_matter"] = "\n".join(
#         l.strip() for l in lines[:front_matter_cutoff]
#         if l.strip() and not PAGE_MARKER_RE.match(l.strip())
#     )

#     # If canonical_headings is still empty when we START this document, this
#     # is the seed document: its ENTIRE ToC becomes canonical directly, not
#     # just whichever heading happens to be processed first.
#     is_seed_document = not canonical_headings

#     for idx, (heading_raw, heading_norm, line_idx, lines_spanned) in enumerate(located):
#         section_start = line_idx + lines_spanned
#         section_end = located[idx + 1][2] if idx + 1 < len(located) else len(lines)
#         content = extract_section_text(lines, section_start, section_end, heading_norm)

#         if any(kw in heading_norm for kw in KEYWORDS_EXCLUDED_FROM_CANONICAL):
#             # Capture as-is; deliberately bypasses seed/canonical/candidate
#             # tracking entirely -- see KEYWORDS_EXCLUDED_FROM_CANONICAL.
#             result["sections"][heading_raw] = content
#             continue

#         if is_seed_document:
#             canonical_headings.append(heading_norm)
#             aliases[heading_norm] = [heading_norm]
#             result["sections"][heading_norm] = content
#             continue

#         canonical = match_canonical(heading_norm, canonical_headings, aliases)

#         if canonical is None:
#             candidates[heading_norm] = candidates.get(heading_norm, 0) + 1
#             result["candidate_new_headings"].append(heading_raw)
#             if candidates[heading_norm] >= CANDIDATE_PROMOTION_COUNT:
#                 canonical_headings.append(heading_norm)
#                 aliases[heading_norm] = [heading_norm]
#                 canonical = heading_norm
#             else:
#                 # Store under raw heading for now; will be re-classified
#                 # automatically once/if promoted in a later run.
#                 result["sections"][heading_raw] = content
#                 continue
#         else:
#             aliases.setdefault(canonical, [])
#             if heading_norm not in aliases[canonical]:
#                 aliases[canonical].append(heading_norm)

#         result["sections"][canonical] = content

#     for canonical in canonical_headings:
#         if canonical not in result["sections"]:
#             result["missing_sections"].append(canonical)

#     return result


# def load_board_lookup():
#     if not BOARD_LOOKUP_PATH.exists():
#         return {}
#     with BOARD_LOOKUP_PATH.open(encoding="utf-8") as f:
#         return json.load(f).get("by_filename", {})


# def main():
#     if not INPUT_DIR.exists():
#         print(f"Input directory not found at {INPUT_DIR} -- update INPUT_DIR at the top of this script.")
#         return

#     board_lookup = load_board_lookup()
#     canonical_headings = []
#     aliases = {}
#     candidates = {}

#     OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
#     files = sorted(INPUT_DIR.glob(FILE_GLOB))

#     failures = []

#     for path in files:
#         stem = path.stem
#         meta = board_lookup.get(stem, {})

#         doc_result = structure_document(path, canonical_headings, aliases, candidates)

#         text_lower = path.read_text(encoding="utf-8", errors="ignore").lower()
#         chapter_18c, chapter_18a = detect_regime_flags(text_lower)

#         output = {
#             "stock_code": meta.get("stock_code", ""),
#             "board": meta.get("board", ""),
#             "chapter_18c": chapter_18c,
#             "chapter_18a": chapter_18a,
#             "front_matter": doc_result["front_matter"],
#             "sections": doc_result["sections"],
#             "missing_sections": doc_result["missing_sections"],
#             "unmatched_headings": doc_result["unmatched_headings"],
#             "candidate_new_headings": doc_result["candidate_new_headings"],
#         }

#         with (OUTPUT_DIR / f"{stem}.json").open("w", encoding="utf-8") as f:
#             json.dump(output, f, indent=2, ensure_ascii=False)

#         if len(doc_result["sections"]) < 4:
#             failures.append(stem)

#     with CANONICAL_HEADINGS_PATH.open("w", encoding="utf-8") as f:
#         json.dump({"canonical_headings": canonical_headings, "aliases": aliases}, f, indent=2, ensure_ascii=False)
#     with CANDIDATE_HEADINGS_PATH.open("w", encoding="utf-8") as f:
#         json.dump(candidates, f, indent=2, ensure_ascii=False)

#     print(f"Structured {len(files)} documents -> {OUTPUT_DIR}")
#     print(f"Canonical heading vocabulary: {len(canonical_headings)} headings -> {CANONICAL_HEADINGS_PATH}")
#     print(f"Candidate (not-yet-promoted) headings: {len(candidates)} -> {CANDIDATE_HEADINGS_PATH}")
#     if failures:
#         print(f"\n{len(failures)} document(s) matched fewer than 4 sections -- review these first:")
#         for f in failures[:20]:
#             print(f"  {f}")


# if __name__ == "__main__":
#     main()

"""
Phase 3 - Step 4/5: Prospectus structuring (heading detection + sectioning)

Core idea: the table of contents lists each heading with its PRINTED page
number (e.g. "Risk Factors . . . 33"), and the scraped text already contains
that same printed page number as a standalone footer line on every page
(e.g. "- 33 -"). So instead of guessing where a heading starts, we:

  1. Index every printed-page-number footer in the raw text -> exact text
     position of the start of that printed page.
  2. Parse the ToC into (heading, printed_page_label) pairs.
  3. For each ToC entry, jump straight to its printed page (via the index
     from step 1) and locate the heading as a standalone line there.
  4. Section content = everything between one heading's PHYSICAL position
     in the text and the next heading's physical position (headings are
     re-sorted by where they actually occur, after being located via
     their ToC page label -- not left in ToC listing order). Within a
     single prospectus, ToC order and physical body order always match, so
     this is just "read top to bottom." The fact that DIFFERENT documents
     in the corpus may order or word their headings differently is a
     separate concern, handled by the canonical-vocabulary matching in
     Step 8 below, not by anything in this slicing step.

This sidesteps needing to know whether a page label is roman, arabic, or
appendix-style (I-1, II-1, ...) -- it's always compared as a literal string
match between ToC and footer, never converted.

Front matter is only the truly un-numbered, non-ToC-listed prefix (cover
page, "IMPORTANT" notices before the timetable). Anything the ToC actually
lists -- including "Expected Timetable" and "Contents" itself, which ARE
page-numbered (roman numerals) and appear as their own ToC entries -- is
located and sectioned like any other heading, not lumped into front matter.

Headings that recur across the corpus but are NOT present in every single
document (e.g. "Waivers from Strict Compliance with the Listing Rules",
only present when a waiver was actually granted) are captured verbatim
under their own raw heading text, but deliberately kept OUT of the
canonical vocabulary -- see KEYWORDS_EXCLUDED_FROM_CANONICAL. Otherwise
every document without one would show a false "missing section".

Canonical heading vocabulary is built dynamically across the corpus:
  - The FIRST document processed seeds the canonical list directly from
    its own ToC.
  - Every later document's ToC headings are fuzzy-matched against the
    canonical list. A genuine miss is logged as a "candidate" and only
    promoted to canonical once seen in >= 2 separate documents, so a
    one-off OCR artifact or a single company's oddly-worded heading
    doesn't pollute the schema.

KNOWN SIMPLIFICATIONS in this first version (call out for review):
  - Two-line broken headings are merged via a simple "does line i + line
    i+1 match better than line i alone" check -- may need tuning on real
    scraped noise.
  - Fuzzy match threshold (0.85) is a starting point, not validated
    against your actual 30-doc manual sample yet.
  - Duplicate ToC entries (e.g. a sub-item repeated) aren't de-duplicated
    beyond keeping the first occurrence.
"""

import bisect
import difflib
import json
import re
from pathlib import Path

# --- Update these for your environment ---
INPUT_DIR = Path("data/extracted_text_sample")
FILE_GLOB = "*.txt"
BOARD_LOOKUP_PATH = Path("data/board_lookup.json")
OUTPUT_DIR = Path("data/structured_prospectuses")
CANONICAL_HEADINGS_PATH = Path("data/headings/canonical_headings.json")
CANDIDATE_HEADINGS_PATH = Path("data/headings/candidate_headings.json")

FUZZY_THRESHOLD = 0.85
CANDIDATE_PROMOTION_COUNT = 2  # a candidate heading needs this many sightings to become canonical

# Headings matching any of these keywords (substring match on the normalized,
# uppercased heading) are captured verbatim but NEVER added to the canonical
# vocabulary or candidate-promotion tracking. These are real, recurring
# headings, but they don't appear in every prospectus (e.g. "Waivers from
# Strict Compliance with the Listing Rules" only shows up when a waiver was
# actually granted) -- treating them as canonical would falsely flag every
# document WITHOUT one as missing a section it was never supposed to have.
KEYWORDS_EXCLUDED_FROM_CANONICAL = ["WAIVER", "INVESTORS", "GEM"]

PAGE_MARKER_RE = re.compile(r"^=== PAGE (\d+) ===\s*$")
FOOTER_PAGE_LABEL_RE = re.compile(r"^\s*[\u2013\u2014-]\s*([A-Za-z]{0,3}-?\d+|[ivxlcdmIVXLCDM]+)\s*[\u2013\u2014-]\s*$")
TOC_LINE_RE = re.compile(r"^(.+?)\s*(?:\.\s*){3,}\s*([ivxlcdmIVXLCDM]+|\d+|[A-Za-z]{1,3}-\d+)\s*$")
CONTENTS_HEADING_RE = re.compile(r"^\s*CONTENTS\s*$", re.IGNORECASE)

CHAPTER_18C_KEYWORDS = [
    "specialist technology company", "chapter 18c",
    "sophisticated independent investor", "pre-commercial company",
]
CHAPTER_18A_KEYWORDS = [
    "biotech company", "chapter 18a", "core product",
]


def normalize(text: str) -> str:
    text = re.sub(r"^\s*(?:[IVXLCDM]+\.|\d+\.|[-*])\s*", "", text.strip())
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .:").upper()
    return text


def fuzzy_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def build_page_index(lines):
    """
    Returns:
      page_label_positions: dict[label] -> list of line indices where that
          printed page's footer occurs (usually 1, could repeat if the same
          label is reused, e.g. multiple "I-1"-style appendix restarts).
      all_footer_positions: sorted list of every footer line index,
          regardless of label. Used to bound heading search to the ACTUAL
          physical page rather than an arbitrary line-count window -- see
          locate_heading.
      page_marker_positions: list of (raw_page_num, line_index) from the
          scraper's own '=== PAGE N ===' markers (currently unused, kept
          for potential future diagnostics).
    """
    page_label_positions = {}
    all_footer_positions = []
    page_marker_positions = []

    for i, line in enumerate(lines):
        marker_match = PAGE_MARKER_RE.match(line)
        if marker_match:
            page_marker_positions.append((int(marker_match.group(1)), i))
            continue
        footer_match = FOOTER_PAGE_LABEL_RE.match(line)
        if footer_match:
            label = footer_match.group(1)
            page_label_positions.setdefault(label, []).append(i)
            all_footer_positions.append(i)

    return page_label_positions, all_footer_positions, page_marker_positions


def find_contents_start(lines):
    for i, line in enumerate(lines):
        if CONTENTS_HEADING_RE.match(line):
            return i
    return None


def parse_toc(lines, contents_start_idx):
    """
    Parse ToC entries starting just after the CONTENTS heading. Real
    documents commonly have a prose paragraph (e.g. an "IMPORTANT NOTICE
    TO PROSPECTIVE INVESTORS" notice, or a "Page" column header) between
    the CONTENTS heading and the actual dot-leader listing -- so this
    first SEEKS freely (no fail limit) for the first line that matches the
    ToC pattern, then switches to COLLECTING mode, where two consecutive
    non-matching lines ends the ToC (heuristic: ToC lines end in a
    page-number token, body prose essentially never does).
    """
    entries = []
    consecutive_fails = 0
    collecting = False
    i = contents_start_idx + 1

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip noise that can legitimately appear BETWEEN ToC entries when
        # the ToC spans multiple pages: the scraper's own page markers,
        # blank lines, the printed page-number footer at the bottom of a
        # ToC page, and a repeated "CONTENTS" running header at the top of
        # the next ToC page. None of these should count as a parse
        # failure -- an earlier version didn't skip the footer/repeated
        # header, so two of them in a row (footer at end of page N, then
        # repeated heading at top of page N+1) hit the fail-cutoff and
        # silently dropped the rest of the ToC.
        if (
            PAGE_MARKER_RE.match(line)
            or not stripped
            or FOOTER_PAGE_LABEL_RE.match(line)
            or CONTENTS_HEADING_RE.match(line)
        ):
            i += 1
            continue

        match = TOC_LINE_RE.match(line)
        if match:
            heading_raw = match.group(1).strip()
            page_label = match.group(2)
            if heading_raw:
                entries.append((heading_raw, page_label))
            collecting = True
            consecutive_fails = 0
        elif collecting:
            consecutive_fails += 1
            if consecutive_fails >= 2:
                break
        # else: still seeking for the first match, keep scanning freely

        i += 1

    return entries


def locate_heading(lines, page_label, heading_raw, page_label_positions, all_footer_positions):
    """
    Search the physical page corresponding to page_label for a standalone
    line matching heading_raw (allowing for a two-line break). Returns
    (start_line_idx, lines_spanned) or None if not found. lines_spanned is
    1 for a normal single-line heading, 2 if it was a broken/merged heading.

    The search window is bounded to the ACTUAL physical page: from just
    after the PRECEDING footer (anywhere in the document) up to this page's
    own footer, with a small forward buffer in case the heading sits right
    at the very top of the next page. This intentionally does NOT use an
    arbitrary line-count window -- an earlier version did, and a wide
    enough window could reach back into the ToC's own dot-leader line for
    this exact heading, which fuzzy-matches closely enough to falsely win
    over the real (much further away) occurrence.
    """
    target_norm = normalize(heading_raw)
    candidate_footer_indices = page_label_positions.get(page_label, [])

    for footer_idx in candidate_footer_indices:
        pos_in_all = bisect.bisect_left(all_footer_positions, footer_idx)
        prev_footer_idx = all_footer_positions[pos_in_all - 1] if pos_in_all > 0 else -1

        search_start = prev_footer_idx + 1
        search_end = min(len(lines), footer_idx + 5)  # small forward buffer only

        for j in range(search_start, search_end):
            line = lines[j].strip()
            if not line or PAGE_MARKER_RE.match(line) or FOOTER_PAGE_LABEL_RE.match(line):
                continue

            single_norm = normalize(line)
            if single_norm == target_norm or fuzzy_ratio(single_norm, target_norm) >= FUZZY_THRESHOLD:
                return j, 1

            if j + 1 < len(lines):
                next_line = lines[j + 1].strip()
                if next_line and not PAGE_MARKER_RE.match(next_line) and not FOOTER_PAGE_LABEL_RE.match(next_line):
                    merged_norm = normalize(line + " " + next_line)
                    if merged_norm == target_norm or fuzzy_ratio(merged_norm, target_norm) >= FUZZY_THRESHOLD:
                        return j, 2

    return None


def extract_section_text(lines, start_idx, end_idx, heading_norm):
    """
    Concatenate lines between start_idx (exclusive of the heading line
    itself) and end_idx, stripping page markers, footer page-number lines,
    and any standalone line that repeats the section's own heading
    (running header).
    """
    out = []
    for line in lines[start_idx:end_idx]:
        stripped = line.strip()
        if not stripped:
            continue
        if PAGE_MARKER_RE.match(stripped) or FOOTER_PAGE_LABEL_RE.match(stripped):
            continue
        if normalize(stripped) == heading_norm:
            continue
        out.append(stripped)
    return "\n".join(out).strip()


def match_canonical(heading_norm, canonical_headings, aliases):
    for canonical, alias_list in aliases.items():
        if heading_norm in alias_list:
            return canonical
    best_canonical, best_score = None, 0.0
    for canonical in canonical_headings:
        score = fuzzy_ratio(heading_norm, canonical)
        if score > best_score:
            best_canonical, best_score = canonical, score
    if best_score >= FUZZY_THRESHOLD:
        return best_canonical
    return None


def detect_regime_flags(full_text_lower):
    chapter_18c = any(kw in full_text_lower for kw in CHAPTER_18C_KEYWORDS)
    chapter_18a = any(kw in full_text_lower for kw in CHAPTER_18A_KEYWORDS)
    return chapter_18c, chapter_18a


def structure_document(path: Path, canonical_headings: list, aliases: dict, candidates: dict):
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.split("\n")

    page_label_positions, all_footer_positions, page_marker_positions = build_page_index(lines)
    contents_idx = find_contents_start(lines)

    result = {
        "front_matter": "",
        "sections": {},
        "missing_sections": [],
        "unmatched_headings": [],
        "candidate_new_headings": [],
    }

    if contents_idx is None:
        # No parseable ToC at all -- store everything as front matter and bail.
        result["front_matter"] = text.strip()
        result["unmatched_headings"].append("NO_CONTENTS_HEADING_FOUND")
        return result

    toc_entries = parse_toc(lines, contents_idx)

    # Locate each heading's start position
    located = []  # list of (raw_name, heading_norm, line_idx, lines_spanned)
    for heading_raw, page_label in toc_entries:
        heading_norm = normalize(heading_raw)
        location = locate_heading(lines, page_label, heading_raw, page_label_positions, all_footer_positions)
        if location is None:
            result["unmatched_headings"].append(heading_raw)
            continue
        line_idx, lines_spanned = location
        located.append((heading_raw, heading_norm, line_idx, lines_spanned))

    located.sort(key=lambda t: t[2])

    # Front matter cutoff is the earliest LOCATED heading's position -- this
    # correctly includes "Expected Timetable" and "Contents" itself as real,
    # page-numbered, ToC-listed sections (per the sample document), NOT as
    # front matter. Only the truly un-numbered cover/notice pages before
    # that (which have no ToC entry and no footer) end up as front matter.
    if located:
        front_matter_cutoff = located[0][2]
    else:
        front_matter_cutoff = contents_idx

    result["front_matter"] = "\n".join(
        l.strip() for l in lines[:front_matter_cutoff]
        if l.strip() and not PAGE_MARKER_RE.match(l.strip())
    )

    # If canonical_headings is still empty when we START this document, this
    # is the seed document: its ENTIRE ToC becomes canonical directly, not
    # just whichever heading happens to be processed first.
    is_seed_document = not canonical_headings

    for idx, (heading_raw, heading_norm, line_idx, lines_spanned) in enumerate(located):
        section_start = line_idx + lines_spanned
        section_end = located[idx + 1][2] if idx + 1 < len(located) else len(lines)
        content = extract_section_text(lines, section_start, section_end, heading_norm)

        if any(kw in heading_norm for kw in KEYWORDS_EXCLUDED_FROM_CANONICAL):
            # Capture as-is; deliberately bypasses seed/canonical/candidate
            # tracking entirely -- see KEYWORDS_EXCLUDED_FROM_CANONICAL.
            result["sections"][heading_raw] = content
            continue

        if is_seed_document:
            canonical_headings.append(heading_norm)
            aliases[heading_norm] = [heading_norm]
            result["sections"][heading_norm] = content
            continue

        canonical = match_canonical(heading_norm, canonical_headings, aliases)

        if canonical is None:
            candidates[heading_norm] = candidates.get(heading_norm, 0) + 1
            result["candidate_new_headings"].append(heading_raw)
            if candidates[heading_norm] >= CANDIDATE_PROMOTION_COUNT:
                canonical_headings.append(heading_norm)
                aliases[heading_norm] = [heading_norm]
                canonical = heading_norm
            else:
                # Store under raw heading for now; will be re-classified
                # automatically once/if promoted in a later run.
                result["sections"][heading_raw] = content
                continue
        else:
            aliases.setdefault(canonical, [])
            if heading_norm not in aliases[canonical]:
                aliases[canonical].append(heading_norm)

        result["sections"][canonical] = content

    for canonical in canonical_headings:
        if canonical not in result["sections"]:
            result["missing_sections"].append(canonical)

    return result


def load_board_lookup():
    if not BOARD_LOOKUP_PATH.exists():
        return {}
    with BOARD_LOOKUP_PATH.open(encoding="utf-8") as f:
        return json.load(f).get("by_filename", {})


def main():
    if not INPUT_DIR.exists():
        print(f"Input directory not found at {INPUT_DIR} -- update INPUT_DIR at the top of this script.")
        return

    board_lookup = load_board_lookup()
    canonical_headings = []
    aliases = {}
    candidates = {}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(INPUT_DIR.glob(FILE_GLOB))

    failures = []

    for path in files:
        stem = path.stem
        meta = board_lookup.get(stem, {})

        doc_result = structure_document(path, canonical_headings, aliases, candidates)

        text_lower = path.read_text(encoding="utf-8", errors="ignore").lower()
        chapter_18c, chapter_18a = detect_regime_flags(text_lower)

        output = {
            "stock_code": meta.get("stock_code", ""),
            "board": meta.get("board", ""),
            "chapter_18c": chapter_18c,
            "chapter_18a": chapter_18a,
            "front_matter": doc_result["front_matter"],
            "sections": doc_result["sections"],
            "missing_sections": doc_result["missing_sections"],
            "unmatched_headings": doc_result["unmatched_headings"],
            "candidate_new_headings": doc_result["candidate_new_headings"],
        }

        with (OUTPUT_DIR / f"{stem}.json").open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        if len(doc_result["sections"]) < 4:
            failures.append(stem)

    with CANONICAL_HEADINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump({"canonical_headings": canonical_headings, "aliases": aliases}, f, indent=2, ensure_ascii=False)
    with CANDIDATE_HEADINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)

    print(f"Structured {len(files)} documents -> {OUTPUT_DIR}")
    print(f"Canonical heading vocabulary: {len(canonical_headings)} headings -> {CANONICAL_HEADINGS_PATH}")
    print(f"Candidate (not-yet-promoted) headings: {len(candidates)} -> {CANDIDATE_HEADINGS_PATH}")
    if failures:
        print(f"\n{len(failures)} document(s) matched fewer than 4 sections -- review these first:")
        for f in failures[:20]:
            print(f"  {f}")


if __name__ == "__main__":
    main()
