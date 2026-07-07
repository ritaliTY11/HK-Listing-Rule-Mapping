"""
Phase 1 — Collection Verification
HKEX Prospectus–Listing Rules Knowledge Base

Independently queries HKEX for all prospectuses across the full date range,
then compares against what you have locally in data/raw_prospectuses/.

Does NOT download anything. Outputs a gap report only.

Usage:
    python phase1_verify.py

Output:
    logs/verification_report.csv   ← full list of HKEX filings with local status
    logs/missing_files.csv         ← only the gaps (on HKEX but not local)
"""

import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from collections import defaultdict

# ─────────────────────────────────────────────
# CONFIGURATION — mirrors phase1_collect.py
# ─────────────────────────────────────────────

BASE_URL     = "https://www1.hkexnews.hk/search/titlesearch.xhtml"
PDF_BASE_URL = "https://www1.hkexnews.hk"

YEAR_RANGES = [
    ("20200101", "20201231"),
    ("20210101", "20211231"),
    ("20220101", "20221231"),
    ("20230101", "20231231"),
    ("20240101", "20241231"),
    ("20250101", "20251231"),
    ("20260101", "20261231"),
]

PAYLOAD_TEMPLATE = {
    "lang":         "EN",
    "category":     "0",
    "market":       "SEHK",
    "searchType":   "1",
    "documentType": "-1",
    "t1code":       "30000",
    "t2Gcode":      "-2",
    "t2code":       "30700",
    "stockId":      "-1",
    "MB-Daterange": "0",
    "title":        "",
}

VALID_LINK_TITLES = [
    "GLOBAL OFFERING",
    "LISTING DOCUMENT",
    "OFFER FOR SALE",
]

EXCLUDE_LINK_KEYWORDS = [
    "APPLICATION FORM",
    "BLUE FORM",
    "E-IPO",
    "EIPO",
    "SUBSCRIPTION FORM",
    "WHITE FORM",
    "YELLOW FORM",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml",
}

OUTPUT_DIR   = "data/raw_prospectuses"
LOG_DIR      = "logs"
REPORT_PATH  = "logs/verification_report.csv"
MISSING_PATH = "logs/missing_files.csv"

DELAY = 2  # seconds between requests


# ─────────────────────────────────────────────
# STEP 1: BUILD LOCAL FILE INDEX
# ─────────────────────────────────────────────

def build_local_index():
    """
    Read all PDFs in raw_prospectuses/ and index them by (stock_code, date).
    Returns a set of (stock_code, date_compact) tuples.
    e.g. {("00068", "20260409"), ("08123", "20241115"), ...}
    """
    index = set()
    pattern = re.compile(r'^(\d+)_(\d{8})\.pdf$')
    for filename in os.listdir(OUTPUT_DIR):
        match = pattern.match(filename)
        if match:
            stock_code   = match.group(1)
            date_compact = match.group(2)
            index.add((stock_code, date_compact))
    return index


# ─────────────────────────────────────────────
# STEP 2: QUERY HKEX
# ─────────────────────────────────────────────

def query_year(from_date, to_date, session):
    payload = {**PAYLOAD_TEMPLATE, "from": from_date, "to": to_date}
    try:
        response = session.post(
            BASE_URL,
            data=payload,
            headers=HEADERS,
            params={"lang": "en"},
            timeout=30,
        )
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [ERROR] Query failed for {from_date}–{to_date}: {e}")
        return None


def parse_date_to_compact(date_filed):
    """Convert DD/MM/YYYY or YYYYMMDD to YYYYMMDD string."""
    date_part = date_filed.strip().split(" ")[0]
    if "/" in date_part:
        d, m, y = date_part.split("/")
        return f"{y}{m}{d}"
    elif len(date_part) == 8 and date_part.isdigit():
        return date_part
    return "".join(filter(str.isdigit, date_part))[:8]


def parse_results(soup):
    """
    Extract prospectus records from HKEX results page.
    Keeps only the most recent valid prospectus per stock code.
    Returns list of dicts: stock_code, company_name, date_compact, pdf_url.
    """
    raw_rows = []
    table = soup.find("table", {"class": "table"})
    if not table:
        print("  [WARN] No results table found.")
        return []

    rows = table.find("tbody").find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        for cell in cells:
            heading = cell.find("span", {"class": "mobile-list-heading"})
            if heading:
                heading.decompose()

        date_filed   = cells[0].get_text(strip=True)
        stock_code   = cells[1].get_text(strip=True).strip()
        company_name = cells[2].get_text(strip=True)

        link_tag = cells[3].find("a", href=True)
        if not link_tag:
            continue
        href = link_tag["href"]
        if not href.endswith(".pdf"):
            continue

        link_text = link_tag.get_text(strip=True).upper()

        if not any(title in link_text for title in VALID_LINK_TITLES):
            continue
        if any(kw in link_text for kw in EXCLUDE_LINK_KEYWORDS):
            continue

        raw_rows.append({
            "stock_code":   stock_code,
            "company_name": company_name,
            "date_compact": parse_date_to_compact(date_filed),
            "pdf_url":      PDF_BASE_URL + href,
        })

    # Keep most recent per stock code
    grouped = defaultdict(list)
    for row in raw_rows:
        grouped[row["stock_code"]].append(row)

    records = []
    for candidates in grouped.values():
        candidates.sort(key=lambda r: r["date_compact"], reverse=True)
        records.append(candidates[0])

    return records


# ─────────────────────────────────────────────
# STEP 3: COMPARE AND REPORT
# ─────────────────────────────────────────────

def main():
    os.makedirs(LOG_DIR, exist_ok=True)

    # Build local index
    print("Reading local files...")
    local_index = build_local_index()
    print(f"  Found {len(local_index)} valid dated PDFs locally.\n")

    # Query HKEX for all years
    session  = requests.Session()
    all_hkex = []  # full list of what HKEX has

    for from_date, to_date in YEAR_RANGES:
        print(f"Querying HKEX: {from_date} to {to_date} ...")
        soup = query_year(from_date, to_date, session)
        if soup is None:
            continue
        records = parse_results(soup)
        print(f"  Found {len(records)} prospectus(es).")
        all_hkex.extend(records)
        time.sleep(DELAY)

    print(f"\nTotal on HKEX: {len(all_hkex)}")

    # Compare
    report_rows = []
    missing_rows = []

    for record in all_hkex:
        key = (record["stock_code"], record["date_compact"])
        have_it = key in local_index
        expected_filename = f"{record['stock_code']}_{record['date_compact']}.pdf"

        row = {
            "stock_code":        record["stock_code"],
            "company_name":      record["company_name"],
            "date_filed":        record["date_compact"],
            "expected_filename": expected_filename,
            "local_status":      "ok" if have_it else "MISSING",
            "pdf_url":           record["pdf_url"],
        }
        report_rows.append(row)
        if not have_it:
            missing_rows.append(row)

    # Write full report
    fields = ["stock_code", "company_name", "date_filed",
              "expected_filename", "local_status", "pdf_url"]

    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report_rows)

    # Write missing-only report
    with open(MISSING_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(missing_rows)

    # Summary
    ok      = len(report_rows) - len(missing_rows)
    missing = len(missing_rows)

    print(f"\n── Verification complete ─────────────────────────")
    print(f"  HKEX total:  {len(all_hkex)}")
    print(f"  Local OK:    {ok}")
    print(f"  Missing:     {missing}")
    print(f"\nFull report:   {REPORT_PATH}")
    print(f"Missing only:  {MISSING_PATH}")


if __name__ == "__main__":
    main()
