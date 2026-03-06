# Technology Stack: Polish Milestone Additions

**Project:** SEM Master - Google Ads Campaign Automation (Swedish)
**Researched:** 2026-03-06
**Scope:** Stack additions for Swedish NLP improvements, CSV verification, PDF generation, and testing

## Existing Stack (Validated, Not Changed)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | >=3.11 | Runtime |
| Pydantic | >=2.5 | Data models |
| Playwright | >=1.40 | Web scraping |
| httpx | >=0.25 | HTTP client |
| BeautifulSoup4 | >=4.12 | HTML parsing |
| pandas | >=2.1 | Data manipulation |
| openpyxl | >=3.1 | Excel files |
| pypdf | >=3.17 | PDF reading |
| spaCy | >=3.7 | NLP pipeline |

---

## 1. Swedish Compound Word Splitting

### Problem

Current `swedish_nlp.py` uses a hand-crafted suffix list (`_COMPOUND_SUFFIXES`) that only covers ~20 suffixes. It cannot split "badrumsrenovering" because neither "badrum" nor "renovering" is in the suffix list. This approach does not scale.

### Recommended: simplemma (greedy decomposition)

| Field | Value |
|-------|-------|
| Library | `simplemma` |
| Version | >=1.1 |
| Confidence | HIGH (verified via GitHub + PyPI) |
| License | MIT |
| Dependencies | None (pure Python) |

**Why simplemma:**
- Pure Python, zero dependencies -- no C extensions, no model downloads
- Supports Swedish (`sv`) with 658+ word forms in its dictionary
- Has a `greedy=True` mode that performs compound decomposition by iteratively searching for sub-word lemmas
- Already designed for "low-frequency range, notably for compound words and neologisms"
- Fast enough for batch processing (no GPU, no large models)
- Actively maintained (releases through 2025+)

**Usage pattern:**
```python
from simplemma import lemmatize
# Standard lemmatization
lemmatize("badrumsrenovering", lang="sv")  # lemmatizes
# Greedy mode for compound decomposition
lemmatize("badrumsrenovering", lang="sv", greedy=True)  # deeper decomposition
```

**Limitation:** simplemma's greedy mode is closer to stemming than true morphological decomposition. For compound splitting specifically, we should combine it with a dictionary-based approach.

### Supplementary: Hunspell dictionary + pyenchant

| Field | Value |
|-------|-------|
| Library | `pyenchant` |
| Version | >=3.2 |
| Confidence | MEDIUM (approach verified, Swedish dict availability confirmed) |
| System dep | `hunspell-sv` dictionary (sv_SE) |

**Why add pyenchant:**
- Hunspell was specifically designed for languages with "rich morphology and complex word compounding"
- Swedish Hunspell dictionary (sv_SE) exists and is maintained (LGPL 3.0, by Goran Andersson)
- pyenchant can validate whether candidate word segments are real Swedish words
- Combined with simplemma greedy decomposition, gives us: decompose with simplemma, validate segments with pyenchant

**Compound splitting strategy (recommended architecture):**

1. Try simplemma greedy decomposition to get candidate sub-words
2. Validate each candidate segment against Hunspell sv_SE dictionary via pyenchant
3. If validation fails, fall back to the improved suffix-based heuristic
4. Cache results (compound words repeat heavily in keyword lists)

### Rejected Alternatives

| Library | Why Not |
|---------|---------|
| `compound-word-splitter` | Last updated 2017, inactive, depends on pyenchant anyway |
| `lemmy` | Last updated 2019, no compound word support, abandoned |
| SALDO lexicon directly | Requires downloading 1.1M-word XML, parsing it, building custom index -- overkill for this use case |
| spaCy sv_core_news_lg | Does NOT support compound decompounding (confirmed via spaCy GitHub Discussion #11521). spaCy has no plans to add this. |
| Custom ML model | Way too complex for this project scope |

---

## 2. Swedish Diacritics Handling

### Problem

Current `_DIACRITICS_MAP` has a bug: duplicate key `"a"` maps to both `"a"` and `"a"`, so `"a" -> "a"` overwrites `"a" -> "a"`. Data files use ASCII instead of proper Swedish characters.

### Recommended: No new library needed

| Field | Value |
|-------|-------|
| Confidence | HIGH |
| Approach | Fix existing code + use `unicodedata` (stdlib) |

**Why no new library:**
- Python's built-in `unicodedata` module handles normalization (NFC/NFD)
- The diacritics variant generation is a simple mapping problem, not an NLP problem
- Fix the duplicate key bug in `_DIACRITICS_MAP`
- Use `unicodedata.normalize("NFC", text)` to ensure consistent encoding
- Add proper bidirectional mappings: a<->a, a<->a, o<->o

**For data file cleanup:**
- Detect ASCII-encoded Swedish words using regex patterns (`/\b\w*(?:aa|ae|oe)\w*\b/` as indicators)
- Build a mapping of common ASCII approximations to proper Swedish: `aa->a`, `ae->a`, `oe->o`
- Validate corrections against Hunspell dictionary (pyenchant, already added above)

---

## 3. Google Ads Editor CSV Format Verification

### Problem

The CSV exporter produces output but there is no automated verification that the format matches what Google Ads Editor actually accepts. Column names, encoding (UTF-8 BOM), and value formats need validation.

### Recommended: No new library for export. Testing approach below.

| Field | Value |
|-------|-------|
| Confidence | HIGH |
| Approach | Schema validation with existing pandas + Pydantic |

**Google Ads Editor CSV requirements (from official docs):**
- Encoding: UTF-8 BOM (`utf-8-sig`) or UTF-16 Unicode -- current code already uses UTF-8 BOM, which is correct
- Row Type column identifies entity type (Campaign, Ad Group, Keyword, Ad, etc.)
- Column names must match exactly (case-sensitive): `Campaign`, `Ad Group`, `Keyword`, `Criterion Type`, `Final URL`, `Headline 1`, `Description 1`, etc.
- Multi-value cells use semicolons (e.g., `"en;sv"` for languages)
- Status values: `Enabled`, `Paused`, `Removed`
- Criterion Type values: `Broad`, `Phrase`, `Exact`
- Bid Strategy Type values: `Maximize clicks`, `Maximize conversions`, `Target CPA`, `Manual CPC`, etc.

**Validation approach:**
- Define expected column schemas per Row Type using Pydantic models
- Validate that exported CSV can be round-tripped (write -> read -> validate)
- Check encoding is correct (BOM present)
- Verify Swedish characters survive the export (a, a, o in keyword text)

### Recommended testing libraries

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| `pytest` | >=7.4 | Test runner (already in dev deps) | HIGH |
| `pytest-datadir` | >=1.5 | Test fixture data management | HIGH |
| `datatest` | >=0.11 | DataFrame/CSV validation assertions | MEDIUM |

**Why pytest-datadir:**
- Provides `datadir` and `shared_datadir` fixtures that return `pathlib.Path` to test data
- Copies test data to temp directory so tests never modify originals
- Perfect for storing reference CSV files that represent valid Google Ads Editor imports

**Why datatest:**
- Purpose-built for validating pandas DataFrames against expected schemas
- Can assert column presence, value ranges, and data types
- Works naturally with pytest

---

## 4. PDF Generation from Markdown

### Problem

Reports are generated as Markdown but clients need PDF output.

### Recommended: markdown-pdf

| Field | Value |
|-------|-------|
| Library | `markdown-pdf` |
| Version | >=1.13 |
| Confidence | HIGH (verified via PyPI, actively maintained) |
| License | AGPL-3.0-only |
| Dependencies | `markdown-it-py`, `PyMuPDF` |
| Latest release | 1.13.1 (2026-02-18) |

**Why markdown-pdf:**
- Purpose-built for exactly this use case: Markdown in, PDF out
- Two-step pipeline: Markdown -> HTML (via markdown-it-py) -> PDF (via PyMuPDF)
- UTF-8 support confirmed -- critical for Swedish characters (a, a, o)
- CSS styling support for branded reports
- Table of contents generation from headings
- Table rendering support (important for campaign reports)
- Actively maintained (release just 2 weeks ago)
- No headless browser required (unlike Playwright-based approaches)

**Usage pattern:**
```python
from markdown_pdf import MarkdownPdf, Section

pdf = MarkdownPdf(toc_level=2)
pdf.add_section(Section(markdown_content, toc=True))
pdf.meta["title"] = "Campaign Report"
pdf.save("report.pdf")
```

### Rejected Alternatives

| Library | Why Not |
|---------|---------|
| WeasyPrint | Excellent for HTML->PDF but requires converting MD->HTML first, adds complexity. Also has system-level dependencies (Cairo, Pango, GDK-PixBuf). |
| xhtml2pdf | Limited CSS support (no flexbox/grid), HTML-only input |
| fpdf2 | Low-level API, would need to build MD parsing ourselves |
| Playwright PDF | Already in stack but overkill -- spawns headless browser just to render a report |

### License consideration

markdown-pdf is AGPL-3.0. Since SEM Master is a tool (not a library/SaaS), AGPL is acceptable -- the tool generates PDFs for clients, it doesn't distribute the PDF library as part of a service. If licensing becomes a concern, WeasyPrint (BSD) is the fallback.

---

## 5. Testing Framework

### Problem

Project has pytest in dev deps but no structured testing approach for CSV format validation, NLP correctness, or PDF generation.

### Recommended additions

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| `pytest` | >=7.4 | Already present | HIGH |
| `pytest-asyncio` | >=0.23 | Already present | HIGH |
| `pytest-datadir` | >=1.5 | Test data fixtures | HIGH |
| `syrupy` | >=4.6 | Snapshot testing for CSV output | MEDIUM |

**Why syrupy over pytest-snapshot:**
- More actively maintained
- Better diff output
- Supports custom serializers (can snapshot CSV content meaningfully)
- Works naturally with pytest

**Testing strategy by area:**

### NLP Tests
- Unit tests for `split_compound_word()` with known Swedish compounds
- Test corpus: `["badrumsrenovering", "koksrenovering", "taklaggning", "fastighetsskotsel", "stadtjanster"]`
- Assert each splits into expected parts
- Test diacritics variant generation produces valid Swedish words

### CSV Export Tests
- Snapshot tests: generate CSV from known input, compare against approved snapshot
- Schema tests: verify column names match Google Ads Editor spec exactly
- Encoding tests: verify UTF-8 BOM header present, Swedish chars preserved
- Round-trip tests: export -> re-import with pandas -> verify data integrity

### PDF Tests
- Smoke tests: generate PDF from sample markdown, verify file is valid PDF
- Content tests: extract text from generated PDF (using pypdf, already in stack), verify Swedish chars present
- No visual regression testing (overkill for this project)

---

## Installation Summary

### New production dependencies

```
simplemma>=1.1
pyenchant>=3.2
markdown-pdf>=1.13
```

### New dev dependencies

```
pytest-datadir>=1.5
syrupy>=4.6
datatest>=0.11
```

### System dependencies

```bash
# Linux/WSL: Swedish Hunspell dictionary for pyenchant
sudo apt install hunspell-sv

# Windows: pyenchant bundles dictionaries, but Swedish may need manual install
# Download sv_SE.dic and sv_SE.aff from LibreOffice dictionaries
# Place in pyenchant's data directory
```

### Updated pyproject.toml dependencies section

```toml
[project]
dependencies = [
    # ... existing ...
    "simplemma>=1.1",
    "pyenchant>=3.2",
    "markdown-pdf>=1.13",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.23",
    "pytest-datadir>=1.5",
    "syrupy>=4.6",
    "datatest>=0.11",
    "ruff>=0.1",
]
```

---

## Sources

### HIGH Confidence (Context7 / Official Docs / PyPI verified)
- [simplemma GitHub](https://github.com/adbar/simplemma) - Compound decomposition, Swedish support, greedy mode
- [simplemma PyPI](https://pypi.org/project/simplemma/) - Version, license, dependencies
- [markdown-pdf PyPI](https://pypi.org/project/markdown-pdf/) - v1.13.1, features, AGPL license
- [spaCy Swedish Models](https://spacy.io/models/sv) - Confirms no compound splitting capability
- [spaCy Discussion #11521](https://github.com/explosion/spaCy/discussions/11521) - Confirms spaCy will not add compound splitting
- [Google Ads Editor: Prepare CSV](https://support.google.com/google-ads/editor/answer/56368) - CSV format requirements
- [Google Ads Editor: CSV columns](https://support.google.com/google-ads/editor/answer/57747) - Column specifications
- [pytest-datadir PyPI](https://pypi.org/project/pytest-datadir/) - Test data fixtures

### MEDIUM Confidence (WebSearch verified with docs)
- [Hunspell Wikipedia](https://en.wikipedia.org/wiki/Hunspell) - Compound word support for Swedish
- [Swedish Hunspell Dictionary](https://extensions.libreoffice.org/en/extensions/show/swedish-spelling-dictionary-den-stora-svenska-ordlistan) - sv_SE availability
- [pyenchant Tutorial](https://pyenchant.github.io/pyenchant/tutorial.html) - Language support via myspell dicts
- [WeasyPrint](https://weasyprint.org/) - Alternative PDF generation
- [syrupy GitHub](https://github.com/toptal/syrupy) - Snapshot testing

### LOW Confidence (WebSearch only, needs validation)
- Swedish compound splitting via pyenchant + simplemma combined approach -- this specific combination has not been documented in any source, it is my recommendation based on understanding both tools' capabilities
