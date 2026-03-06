# Roadmap - v0.2.0 Polish & Verify

## Overview

Fix data quality issues (Swedish diacritics), improve NLP compound splitting, verify all export formats (CSV + PDF), and add test infrastructure. Every phase delivers a verifiable capability that downstream phases depend on.

**Phases:** 5
**Depth:** Standard
**Coverage:** 14/14 requirements mapped

---

## Phase 1: Git Baseline

**Goal:** Establish version control so every subsequent change is tracked and reversible.

**Dependencies:** None (first phase)

**Requirements:** INF-01

**Success Criteria:**
1. Running `git log` shows a baseline commit containing all v0.1.0 source files
2. A `.gitignore` excludes `__pycache__/`, `.env`, `*.pyc`, and IDE files
3. `git status` shows a clean working tree after the baseline commit

---

## Phase 2: Swedish Diacritics

**Goal:** All Swedish text across data files, report generator, and NLP utilities uses correct diacritics (a, a, o) instead of ASCII approximations.

**Dependencies:** Phase 1 (baseline must exist before modifying files)

**Requirements:** DQ-01, DQ-02, DQ-03, DQ-04

**Success Criteria:**
1. Searching all JSON data files for known ASCII approximations ("tjanst", "sokord", "Fa offert") returns zero matches
2. Report generator output contains correct Swedish section headers ("Sammanfattning", "Affarsstrategi", "Kampanjstruktur")
3. `generate_diacritics_variants("tjanst")` returns `["tjanst", "tjänst"]` -- the old broken `_DIACRITICS_MAP` dict is removed
4. All hardcoded Swedish strings in `report_generator.py` use proper diacritics

---

## Phase 3: CSV Export & NLP Improvements

**Goal:** CSV exports pass Google Ads Editor import validation, and compound word splitting produces meaningful Swedish word components.

**Dependencies:** Phase 2 (diacritics must be fixed before NLP and export work -- correct Swedish text is input to both)

**Requirements:** EXP-01, EXP-02, EXP-03, EXP-05, NLP-01, NLP-02

**Parallelization:** EXP-01..03 + EXP-05 (CSV fixes) can be worked independently from NLP-01..02 (compound splitter). No code overlap.

**Success Criteria:**
1. CSV output files contain no `Row Type` column in any of the 7 entity types
2. Sitelink and callout CSV rows include a `Campaign` column
3. Export produces 7 separate files (`01_campaigns.csv` through `07_callouts.csv`) plus `README_import_order.txt`
4. `split_compound("badrumsrenovering")` returns `["badrums", "renovering"]` using dictionary-based decomposition
5. Keyword expansion generates compound splits, plural/singular forms, and diacritics variants as suggestions

---

## Phase 4: PDF Report Generation

**Goal:** Users can generate a styled PDF report from campaign analysis with correct Swedish characters.

**Dependencies:** Phase 2 (Swedish diacritics must be correct in report generator)

**Note:** Independent of Phase 3 -- can start as soon as Phase 2 completes.

**Requirements:** EXP-04

**Success Criteria:**
1. Running the report generator produces a PDF file (not just Markdown)
2. The PDF renders Swedish characters (a, a, o) correctly without mojibake
3. The PDF contains all report sections: summary, business analysis, campaign structure, keywords

---

## Phase 5: Test Suite & Validation

**Goal:** Automated tests verify that all fixes from Phases 2-4 remain correct, and JSON schemas enforce data file structure.

**Dependencies:** Phases 2, 3, 4 (validates work from all prior phases)

**Requirements:** INF-02, INF-03

**Success Criteria:**
1. `pytest` runs a full test suite covering: model validation, Swedish NLP, CSV export schema, data file diacritics
2. An integration smoke test runs the pipeline end-to-end (intake -> analysis -> export) without errors
3. JSON Schema files exist for each Swedish data file and validate current file structure
4. All tests pass on a clean checkout

---

## Progress

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 1 | Git Baseline | INF-01 | Pending |
| 2 | Swedish Diacritics | DQ-01, DQ-02, DQ-03, DQ-04 | Pending |
| 3 | CSV Export & NLP | EXP-01, EXP-02, EXP-03, EXP-05, NLP-01, NLP-02 | Pending |
| 4 | PDF Report | EXP-04 | Pending |
| 5 | Test Suite & Validation | INF-02, INF-03 | Pending |

## Dependency Graph

```
Phase 1 (Git Baseline)
  └── Phase 2 (Swedish Diacritics)
        ├── Phase 3 (CSV Export & NLP)
        │     └── Phase 5 (Test Suite & Validation)
        └── Phase 4 (PDF Report) ──┘
```

Phases 3 and 4 can run in parallel after Phase 2 completes. Phase 5 waits for both.

---
*Last updated: 2026-03-06*
