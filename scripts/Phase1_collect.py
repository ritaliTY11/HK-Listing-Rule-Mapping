"""
Phase 1 — Prospectus Collection
HKEX Prospectus–Listing Rules Knowledge Base

Objective: Collect IPO listing documents from HKEXnews for Main Board (SEHK),
           2022–2026, under Headline Category t1code=30000 (Listing Documents).

Output:
    data/raw_prospectuses/   ← downloaded PDFs
    logs/download_log.csv    ← index of all discovered documents + download status

Usage:
    python phase1_collect.py
"""

import os
import time
import csv
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

BASE_URL = "https://www1.hkexnews.hk/search/titlesearch.xhtml"
PDF_BASE_URL = "https://www1.hkexnews.hk"

# Year ranges to query — one query per year to stay within the 12-month limit
# that HKEXnews imposes when no stock code is specified.
YEAR_RANGES = [
    ("20220101", "20221231"),
    ("20230101", "20231231"),
    ("20240101", "20241231"),
    ("20250101", "20251231"),
    ("20260101", "20261231"),
]

# POST payload template — values confirmed from DevTools capture
PAYLOAD_TEMPLATE = {
    "lang":         "EN",
    "category":     "0",
    "market":       "SEHK",        # Main Board
    "searchType":   "1",           # 1 = search by headline category
    "documentType": "-1",
    "t1code":       "30000",       # Listing Documents headline category
    "t2Gcode":      "-2",          # All sub-groups
    "t2code":       "30700",       # Offer for subscription
    "stockId":      "-1",          # All companies
    "MB-Daterange": "0",
    "title":        "",
}

# Headline keywords that identify a prospectus (Listing Document — Offer for Subscription
# or Offer for Sale). Filters out PHIPs, application proofs, offering circulars etc.
# Extend this list if you find prospectuses being missed during review.
PROSPECTUS_KEYWORDS = [
    "listing documents",
    "offer for subscription",
    "offer for sale",
    "global offering",
    "prospectus",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml",
}

OUTPUT_DIR = "data/raw_prospectuses"
LOG_PATH   = "logs/download_log.csv"
LOG_FIELDS = [
    "stock_code", "company_name", "date_filed",
    "board", "headline", "pdf_url", "filename",
    "downloaded", "error"
]

DELAY_BETWEEN_REQUESTS = 2  # seconds — be respectful to the server


# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────

def setup_directories():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs("logs", exist_ok=True)


def load_existing_log():
    """Return a set of pdf_urls already recorded in the log (to skip re-downloads)."""
    seen = set()
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                seen.add(row["pdf_url"])
    return seen


def open_log_writer(existing_records):
    """Open log CSV in append mode; write header only if file is new."""
    file_exists = os.path.exists(LOG_PATH)
    f = open(LOG_PATH, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
    if not file_exists:
        writer.writeheader()
    return f, writer


# ─────────────────────────────────────────────
# QUERYING
# ─────────────────────────────────────────────

def query_year(from_date, to_date, session):
    """
    POST to HKEXnews title search for one year range.
    Returns parsed BeautifulSoup of the response, or None on failure.
    """
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


def parse_results(soup):
    """
    Extract document records from the result table HTML.
    Returns a list of dicts with keys matching LOG_FIELDS (minus downloaded/error).
    """
    records = []
    table = soup.find("table", {"class": "table"})
    if not table:
        print("  [WARN] No results table found in response.")
        return records

    rows = table.find("tbody").find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        date_filed  = cells[0].get_text(strip=True)
        stock_code  = cells[1].get_text(strip=True)
        company_name = cells[2].get_text(strip=True)

        # Headline category text e.g. "Listing Documents - [Offer for Subscription]"
        headline_div = cells[3].find("div", {"class": "headline"})
        headline = headline_div.get_text(strip=True) if headline_div else ""

        # PDF link — skip multi-file HTML index pages (no direct PDF)
        link_tag = cells[3].find("a", href=True)
        if not link_tag:
            continue
        href = link_tag["href"]
        if not href.endswith(".pdf"):
            continue  # skip .htm multi-file pages

        # Filter: only keep rows whose headline matches prospectus keywords
        if not any(kw in headline.lower() for kw in PROSPECTUS_KEYWORDS):
            continue

        pdf_url = PDF_BASE_URL + href
        records.append({
            "stock_code":   stock_code,
            "company_name": company_name,
            "date_filed":   date_filed,
            "board":        "Main Board",
            "headline":     headline,
            "pdf_url":      pdf_url,
            "filename":     "",   # filled during download
            "downloaded":   "no",
            "error":        "",
        })

    return records


# ─────────────────────────────────────────────
# DOWNLOADING
# ─────────────────────────────────────────────

def build_filename(record):
    """
    Construct a safe, consistent filename:
    {stock_code}_{date_filed_compact}.pdf
    e.g. 06658_20260605.pdf
    """
    # date_filed arrives as DD/MM/YYYY HH:MM — extract date only
    date_part = record["date_filed"].split(" ")[0]          # "05/06/2026"
    date_compact = date_part.replace("/", "")[::-1]         # reverse: YYYYMMDD
    # reverse "05062026" → "20260605"
    d, m, y = date_part.split("/")
    date_compact = f"{y}{m}{d}"
    stock = record["stock_code"].replace(" ", "_")
    return f"{stock}_{date_compact}.pdf"


def download_pdf(record, session):
    """
    Download a single PDF. Updates record's filename, downloaded, and error fields.
    Returns the updated record.
    """
    filename = build_filename(record)
    filepath = os.path.join(OUTPUT_DIR, filename)
    record["filename"] = filename

    # Skip if already downloaded
    if os.path.exists(filepath):
        print(f"  [SKIP] Already exists: {filename}")
        record["downloaded"] = "yes"
        return record

    try:
        response = session.get(record["pdf_url"], headers=HEADERS, timeout=60)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(response.content)
        record["downloaded"] = "yes"
        print(f"  [OK]   {filename}  ({len(response.content) // 1024} KB)")
    except requests.RequestException as e:
        record["downloaded"] = "no"
        record["error"] = str(e)
        print(f"  [FAIL] {filename}: {e}")

    return record


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    setup_directories()
    seen_urls = load_existing_log()
    log_file, writer = open_log_writer(seen_urls)

    session = requests.Session()
    total_found = 0
    total_downloaded = 0

    try:
        for from_date, to_date in YEAR_RANGES:
            print(f"\n{'='*50}")
            print(f"Querying {from_date} to {to_date} ...")
            print(f"{'='*50}")

            soup = query_year(from_date, to_date, session)
            if soup is None:
                continue

            records = parse_results(soup)
            print(f"  Found {len(records)} prospectus document(s).")
            total_found += len(records)

            for record in records:
                # Skip if already in log
                if record["pdf_url"] in seen_urls:
                    print(f"  [SKIP] Already logged: {record['pdf_url']}")
                    continue

                # Download
                record = download_pdf(record, session)
                writer.writerow(record)
                log_file.flush()  # write immediately so progress is not lost
                seen_urls.add(record["pdf_url"])

                if record["downloaded"] == "yes":
                    total_downloaded += 1

                time.sleep(DELAY_BETWEEN_REQUESTS)

    finally:
        log_file.close()

    print(f"\n{'='*50}")
    print(f"Done. Found: {total_found}  |  Downloaded: {total_downloaded}")
    print(f"Log saved to: {LOG_PATH}")
    print(f"PDFs saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()