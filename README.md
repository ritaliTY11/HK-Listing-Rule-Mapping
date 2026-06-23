# HKEX Prospectus–Listing Rules Knowledge Base (DEMO)

## Project Overview

A legal-tech knowledge base that systematically collects Hong Kong IPO prospectuses and maps their contents to relevant HKEX Listing Rules.

The project aims to transform prospectuses from isolated PDF documents into a structured, searchable corpus that allows users to:

* Search prospectuses by listing rule
* Search listing rules by prospectus content
* Compare disclosure practices across issuers
* Retrieve precedents for specific disclosure requirements
* Track filing trends over time
* Build a foundation for future AI-assisted legal research

---

# Version 1 Scope

## Covered Listing Rules

* Chapter(s): Appendix D
* Rule range: All, may start with financial info

## Covered Prospectuses

* Board: Main Board / GEM / Both (May start with either)
* Number of prospectuses: __________
* Time period: 2020/01/01 - 2026/06/23

---

# Phase 1 — Prospectus Collection

## Objective

Automatically collect IPO prospectuses from HKEX sources.

## Achieved Through

### Programming Language

* Python

### Libraries

* requests
* BeautifulSoup
* ---

### Data Source

* HKEX prospectus repository
* ---

## Resulting Artifacts

```text
data/
└── raw_prospectuses/
    ├── company_a.pdf
    ├── company_b.pdf
    ├── company_c.pdf
    └── ...
```

### Output

A local archive of prospectus PDFs.

---

# Phase 2 — Text Extraction

## Objective

Convert prospectus PDFs into machine-readable text.

## Achieved Through

### Programming Language

* Python

### Libraries

* pdfplumber
* PyMuPDF
* ---

## Resulting Artifacts

```text
data/
├── raw_prospectuses/
└── extracted_text/
    ├── company_a.txt
    ├── company_b.txt
    └── ...
```

### Output

One text file corresponding to each prospectus.

---

# Phase 3 — Prospectus Structuring

## Objective

Identify and separate major prospectus sections.

Examples:

* Risk Factors
* Business
* Financial Information
* Directors and Management
* Industry Overview
* Use of Proceeds
* ---

## Achieved Through

### Programming Language

* Python

### Method

* Heading detection
* Rule-based parsing
* ---

## Resulting Artifacts

```text
data/
└── structured_prospectuses/
    ├── company_a.json
    ├── company_b.json
    └── ...
```

Example:

{
"company": "Company A",
"sections": {
"Risk Factors": "...",
"Business": "...",
"Financial Information": "..."
}
}

### Output

Structured prospectus records.

---

# Phase 4 — Listing Rules Database

## Objective

Create a structured database of selected HKEX Listing Rules.

## Achieved Through

### Programming Language

* Python

### Data Source

* HKEX Listing Rules
* ---

## Resulting Artifacts

```text
data/
└── listing_rules/
    ├── rules.json
    └── rules.db
```

Example:

{
"rule_id": "8.05",
"title": "Profit Requirement",
"chapter": "Chapter 8",
"text": "..."
}

### Output

Searchable rule repository.

---

# Phase 5 — Rule Mapping Dataset

## Objective

Create explicit links between prospectus content and listing rules.

## Achieved Through

### Method

* Manual annotation
* Rule-based matching
* ---

## Resulting Artifacts

```text
data/
└── mappings/
    └── rule_mappings.csv
```

Example:

| Prospectus | Section               | Rule |
| ---------- | --------------------- | ---- |
| Company A  | Financial Information | 8.05 |
| Company B  | Risk Factors          | ____ |

### Output

Ground-truth mapping dataset.

---

# Phase 6 — Search System

## Objective

Enable retrieval of prospectus examples through listing rules.

## Achieved Through

### Programming Language

* Python

### Framework

* Streamlit / Flask / __________

### Database

* SQLite / PostgreSQL / __________

## Resulting Artifacts

```text
app/
├── search.py
├── database.db
└── interface/
```

### Supported Queries

* Rule → Prospectus examples
* Company → Prospectus sections
* Date-filtered searches
* Counsel-filtered searches
* ---

### Output

Interactive search interface.

---

# Phase 7 — Semantic Search

## Objective

Retrieve relevant prospectus passages even when exact rule references are absent.

## Achieved Through

### Embedding Model

* sentence-transformers
* ---

### Vector Storage

* FAISS
* ChromaDB
* ---

## Resulting Artifacts

```text
data/
└── embeddings/
    ├── vectors.index
    └── metadata.json
```

### Output

Natural-language search capability.

Example:

"Show disclosures relating to customer concentration risk."

---

# Phase 8 — AI-Assisted Rule Mapping

## Objective

Automatically suggest candidate listing rules for prospectus passages.

## Achieved Through

### Model

* GPT API
* Claude API
* Legal-BERT
* ---

### Workflow

Prospectus Section
→ Candidate Rule Identification
→ Confidence Score
→ Human Review

## Resulting Artifacts

```text
data/
└── ai_mappings/
    └── suggested_mappings.csv
```

### Output

Semi-automated rule classification.

---

# Phase 9 — Automated Monitoring Agent

## Objective

Continuously monitor HKEX for newly filed prospectuses.

## Achieved Through

### Agent Functions

1. Detect new filings
2. Download prospectuses
3. Extract text
4. Structure content
5. Generate mapping suggestions
6. Update database

### Technology

* Python
* Scheduled jobs
* ---

## Resulting Artifacts

```text
automation/
├── monitor.py
├── downloader.py
├── parser.py
└── updater.py
```

### Output

Self-updating prospectus knowledge base.

---

# Final Deliverable

A searchable legal knowledge system containing:

* HKEX Listing Rules
* IPO Prospectuses
* Rule–Prospectus Mappings
* Metadata Filters
* Semantic Search
* AI-Assisted Classification

Designed for:

* Legal research
* Capital markets due diligence
* Prospectus precedent analysis
* HKEX listing rule study
* Future legal-tech development

