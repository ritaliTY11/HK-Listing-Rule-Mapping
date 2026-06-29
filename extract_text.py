"""
Phase 2 — Text Extraction
HKEX Prospectus Knowledge Base

Extracts text from prospectus PDFs, preserving page numbers.
Outputs one .txt per prospectus and an extraction_log.csv.

Usage:
    python extract_text.py

Expected input folder:  data/raw_prospectuses/
Expected output folder: data/extracted_text/
Log output:             data/extraction_log.csv
"""

import os
import csv
import pdfplumber
import fitz  # PyMuPDF
import logging
logging.getLogger("pdfminer").setLevel(logging.ERROR)

import fitz
fitz.TOOLS.mute_warnings = True

# ── Configuration ────────────────────────────────────────────────────────────

INPUT_DIR  = "data/raw_prospectuses"
OUTPUT_DIR = "data/extracted_text"
LOG_PATH   = "data/extraction_log.csv"

# A page is flagged "low yield" if its extracted text is shorter than this.
# Prospectus pages are dense; anything under ~100 chars likely failed or is a
# blank/image-only page.
LOW_YIELD_CHARS_PER_PAGE = 100

# If the TOTAL character count for the whole document is below this threshold,
# the file is flagged as "low_yield" overall (probably scanned).
LOW_YIELD_TOTAL_THRESHOLD = 5000


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_with_pdfplumber(pdf_path):
    """
    Try extracting text with pdfplumber.
    Returns a list of (page_number, text) tuples — page_number is 1-based.
    Returns None if the file cannot be opened.
    """
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append((i, text))
        return pages
    except Exception:
        return None


def extract_with_pymupdf(pdf_path):
    """
    Fallback extraction with PyMuPDF (fitz).
    Returns a list of (page_number, text) tuples — page_number is 1-based.
    Returns None if the file cannot be opened.
    """
    pages = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc, start=1):
            text = page.get_text() or ""
            pages.append((i, text))
        doc.close()
        return pages
    except Exception:
        return None


def total_chars(pages):
    """Sum of all character counts across pages."""
    return sum(len(text) for _, text in pages)


def write_txt(pages, output_path):
    """
    Write extracted pages to a .txt file.
    Each page is preceded by a separator line: === PAGE N ===
    This preserves page numbers for downstream use (Phase 3+).
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for page_num, text in pages:
            f.write(f"=== PAGE {page_num} ===\n")
            f.write(text.strip())
            f.write("\n\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    pdf_files.sort()

    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}. Exiting.")
        return

    print(f"Found {len(pdf_files)} PDFs. Starting extraction...\n")

    log_rows = []

    for idx, filename in enumerate(pdf_files, start=1):
        pdf_path    = os.path.join(INPUT_DIR, filename)
        stem        = os.path.splitext(filename)[0]   # e.g. "00068_20260409"
        output_path = os.path.join(OUTPUT_DIR, stem + ".txt")

        print(f"[{idx}/{len(pdf_files)}] {filename}", end=" ... ")

        # ── Step 1: Try pdfplumber ────────────────────────────────────────
        pages = extract_with_pdfplumber(pdf_path)

        method = "pdfplumber"

        # ── Step 2: Fallback to PyMuPDF if pdfplumber failed or low yield ─
        if pages is None or total_chars(pages) < LOW_YIELD_TOTAL_THRESHOLD:
            fallback = extract_with_pymupdf(pdf_path)
            if fallback is not None:
                if pages is None or total_chars(fallback) > total_chars(pages):
                    pages  = fallback
                    method = "pymupdf_fallback"

        # ── Step 3: Determine status ──────────────────────────────────────
        if pages is None:
            status     = "failed"
            page_count = 0
            char_count = 0
            print("FAILED")
        else:
            char_count = total_chars(pages)
            page_count = len(pages)

            if char_count < LOW_YIELD_TOTAL_THRESHOLD:
                status = "low_yield"
                print(f"LOW YIELD ({char_count} chars, {page_count} pages) — likely scanned")
            else:
                status = "ok"
                print(f"ok ({char_count:,} chars, {page_count} pages)")

            write_txt(pages, output_path)

        # ── Step 4: Log ───────────────────────────────────────────────────
        log_rows.append({
            "filename":   filename,
            "stock_code": stem.split("_")[0],
            "date":       stem.split("_")[1] if "_" in stem else "",
            "page_count": page_count,
            "char_count": char_count,
            "method":     method if pages is not None else "none",
            "status":     status,
        })

    # ── Write log ─────────────────────────────────────────────────────────────
    fieldnames = ["filename", "stock_code", "date",
                  "page_count", "char_count", "method", "status"]

    with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)

    # ── Summary ───────────────────────────────────────────────────────────────
    ok         = sum(1 for r in log_rows if r["status"] == "ok")
    low_yield  = sum(1 for r in log_rows if r["status"] == "low_yield")
    failed     = sum(1 for r in log_rows if r["status"] == "failed")

    print(f"\n── Extraction complete ──────────────────────────────")
    print(f"  Total :     {len(log_rows)}")
    print(f"  OK :        {ok}")
    print(f"  Low yield : {low_yield}  ← likely scanned; review manually")
    print(f"  Failed :    {failed}     ← could not open at all")
    print(f"\nLog saved to: {LOG_PATH}")
    print(f"Text files in: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()