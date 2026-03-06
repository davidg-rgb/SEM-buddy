# Architecture: Export Format Integration

**Domain:** Google Ads Editor CSV export + Report generation
**Researched:** 2026-03-06
**Confidence:** MEDIUM-HIGH (verified against official Google documentation and community sources)

## Executive Summary

The current CSV exporter has a critical architectural issue: it uses a fabricated `Row Type` column that Google Ads Editor does not recognize. Google Ads Editor determines entity type from the **combination of columns present** in each row, not from a row-type discriminator. The exporter should produce **separate CSV files per entity type** (or at minimum, separate import operations) rather than a single unified file with a `Row Type` column.

---

## Google Ads Editor CSV Format Specification

### Core Principle: No Row Type Column

**CRITICAL FINDING:** Google Ads Editor does NOT use a `Row Type` column. The current exporter adds this column to every row, which will cause import warnings or failures.

Google Ads Editor identifies entity types by:
1. Which columns are present and populated
2. The combination of identifying fields (e.g., Campaign + Ad Group + Keyword = keyword row)
3. Automatic detection: "Google Ads Editor automatically decides whether to edit an existing item or create a new one based on the set of columns best suited for distinguishing items"

**Confidence:** HIGH - Multiple official sources confirm this behavior.

### Column Name Matching Rules

Google Ads Editor is flexible with column header formatting:
- Case-insensitive: `Campaign` = `campaign` = `CAMPAIGN`
- Space/underscore/no-space equivalent: `Daily Budget` = `daily_budget` = `dailybudget`
- Headers MUST be in English

**Confidence:** HIGH - Official Google documentation.

### Encoding Requirements

| Requirement | Specification | Notes |
|-------------|---------------|-------|
| Encoding | UTF-8 or ASCII | UTF-16 NOT supported for CSV import |
| BOM | UTF-8 BOM acceptable | Current code uses `utf-8-sig` which is correct |
| Excel save | Unicode Text encoding | Windows: Save As > Unicode Text |
| File extension | `.csv` or `.txt` | Editor accepts both |

**Current code status:** The `utf-8-sig` encoding in the exporter is CORRECT for Excel compatibility and Google Ads Editor import.

**Confidence:** HIGH - Official documentation.

### Entity-Specific Column Specifications

#### Campaign Rows

| Column | Required | Current Code | Notes |
|--------|----------|-------------|-------|
| Campaign | YES | `campaign.name` | Identifying field |
| Campaign Type | No | `campaign.campaign_type` | Default: Search |
| Campaign Status | No | `campaign.status` | Paused/Enabled |
| Budget | No | `campaign.budget_sek_daily` | Daily budget amount |
| Budget type | No | `"Daily"` | Daily or Total |
| Bid Strategy Type | No | `campaign.bid_strategy` | e.g., Maximize Clicks |
| Networks | No | `"Google search"` | Semicolon-separated |
| Languages | No | `"sv"` | Semicolon-separated codes |
| Location | No | geo targets | Semicolon-separated |

**Current code issues:**
- Has spurious `Row Type` column (REMOVE)
- Column names appear correct otherwise

#### Ad Group Rows

| Column | Required | Current Code | Notes |
|--------|----------|-------------|-------|
| Campaign | YES | `campaign.name` | Links to campaign |
| Ad Group | YES | `ag.name` | Identifying field |
| Status | No | `"Enabled"` | |
| Max CPC | No | `""` | Leave empty for automated bidding |
| Ad Group Type | No | `"Standard"` | |

**Current code issues:**
- Has spurious `Row Type` column (REMOVE)
- Template file uses `Ad Group` as first column, but code puts `Campaign` first (order doesn't matter for import, but consistency helps)

#### Keyword Rows

| Column | Required | Current Code | Notes |
|--------|----------|-------------|-------|
| Campaign | YES | `campaign.name` | |
| Ad Group | YES | `ag.name` | |
| Keyword | YES | `kw.text` | Identifying field with match type |
| Criterion Type | No | `"Broad"/"Phrase"/"Exact"` | Match type |
| Status | No | `"Enabled"` | |
| Final URL | No | from first ad | Landing page |

**Current code issues:**
- Has spurious `Row Type` column (REMOVE)
- Gets Final URL from first ad in campaign, not per-keyword (acceptable pattern)

#### Responsive Search Ad (RSA) Rows

| Column | Required | Current Code | Notes |
|--------|----------|-------------|-------|
| Campaign | YES | `campaign.name` | |
| Ad Group | YES | `ag.name` | |
| Ad type | YES | `"Responsive search ad"` | Identifies as RSA |
| Headline 1 through Headline 15 | Min 3 | `ad.headlines` | Max 30 chars each |
| Headline 1 position through Headline 15 position | No | Pin positions | 1-3 or empty |
| Description 1 through Description 4 | Min 2 | `ad.descriptions` | Max 90 chars each |
| Description 1 position through Description 4 position | No | Pin positions | 1-2 or empty |
| Final URL | YES | `ad.final_url` | |
| Path 1 | No | `ad.path1` | Max 15 chars |
| Path 2 | No | `ad.path2` | Max 15 chars |
| Status | No | `"Enabled"` | |

**Current code issues:**
- Has spurious `Row Type` column (should be removed; `Ad type` is the correct discriminator)
- Pin positions use string `"1"`, `"2"` -- correct format
- Headline/Description column naming matches Google Ads Editor format

#### Sitelink Rows

| Column | Required | Current Code | Notes |
|--------|----------|-------------|-------|
| Campaign | YES* | MISSING | Must specify campaign scope |
| Sitelink text | YES | `sl.text` | Max 25 chars |
| Description 1 | No | `sl.desc1` | Max 35 chars; both desc required if any |
| Description 2 | No | `sl.desc2` | Max 35 chars |
| Final URL | YES | `sl.final_url` | |
| Status | No | `"Enabled"` | |

**Current code issues:**
- MISSING `Campaign` column -- sitelinks must be scoped to a campaign
- Has spurious `Row Type` column (REMOVE)
- If description 1 is provided, description 2 MUST also be provided

#### Callout Rows

| Column | Required | Current Code | Notes |
|--------|----------|-------------|-------|
| Campaign | YES* | MISSING | Must specify campaign scope |
| Callout text | YES | `co.text` | Max 25 chars |
| Status | No | `"Enabled"` | |

**Current code issues:**
- MISSING `Campaign` column -- callouts must be scoped to a campaign
- Has spurious `Row Type` column (REMOVE)

#### Negative Keyword Rows

| Column | Required | Current Code | Notes |
|--------|----------|-------------|-------|
| Campaign | YES | `campaign.name` | |
| Keyword | YES | `neg_kw` | |
| Criterion Type | No | `"Broad"` | Match type for negatives |

**Current code issues:**
- Has spurious `Row Type` column (REMOVE)
- Missing `Ad Group` column for ad-group-level negatives (current data model has negatives at ad group level but export only specifies campaign)

---

## Single File vs. Multi-File Import

### Recommended Approach: Separate CSV Files Per Entity Type

**Why separate files:**

1. **Google Ads Editor's auto-detection works best with homogeneous rows.** When all rows have the same column structure, the editor reliably identifies entity types. Mixed rows with many empty columns create ambiguity.

2. **Superset column problem.** A single file must include ALL columns from ALL entity types. This means campaign rows have empty Headline 1-15, Description 1-4, Keyword, etc. Google Ads Editor handles this but it's fragile and error-prone.

3. **Import order matters.** Campaigns must exist before ad groups can reference them. Ad groups must exist before keywords and ads. Separate files enforce correct import ordering.

4. **Debugging.** When import fails, separate files make it obvious which entity type has the problem.

**Recommended file structure:**

```
output/
  {client_name}/
    01_campaigns.csv          # Campaign settings
    02_ad_groups.csv          # Ad group settings
    03_keywords.csv           # Keywords with match types
    04_responsive_search_ads.csv  # RSA headlines and descriptions
    05_negative_keywords.csv  # Negative keywords
    06_sitelinks.csv          # Sitelink extensions
    07_callouts.csv           # Callout extensions
    README_import_order.txt   # Instructions for import sequence
```

**Import sequence:**
1. Campaigns first (creates campaign containers)
2. Ad groups (creates ad group containers within campaigns)
3. Keywords (assigns keywords to ad groups)
4. RSAs (assigns ads to ad groups)
5. Negative keywords (assigns negatives)
6. Sitelinks (assigns extensions to campaigns)
7. Callouts (assigns extensions to campaigns)

**Confidence:** MEDIUM - This is a best-practice recommendation based on how Google Ads Editor entity detection works. A single file CAN work but is more fragile.

### Alternative: Keep Single File (With Fixes)

If staying with a single file:
1. REMOVE the `Row Type` column entirely
2. Use the superset of all columns as the header
3. Leave non-applicable columns empty (not null, just empty string)
4. Order rows: campaigns first, then ad groups, then keywords, then ads, then extensions
5. Google Ads Editor will auto-detect entity types from populated columns

**Risk:** Some column name collisions exist. For example, `Status` appears in multiple entity types but `Campaign Status` is different from keyword `Status`. The `Description 1` column is used by both RSAs and sitelinks with different semantics. This makes single-file approach unreliable for mixed entity imports.

---

## Current Exporter: Issues Summary

### Critical Issues (Will Break Import)

| Issue | Location | Fix |
|-------|----------|-----|
| `Row Type` column does not exist in Google Ads Editor | All `_*_rows()` functions | Remove `Row Type` from all row dicts |
| Sitelinks missing `Campaign` column | `_sitelink_rows()` | Add campaign assignment (requires model change or parameter) |
| Callouts missing `Campaign` column | `_callout_rows()` | Add campaign assignment (requires model change or parameter) |

### Moderate Issues (May Cause Warnings)

| Issue | Location | Fix |
|-------|----------|-----|
| Single file with mixed entity types | `export_campaign_plan()` | Split into per-entity-type CSV files |
| `Description 1`/`Description 2` column collision (RSA vs Sitelink) | DataFrame merge | Separate files resolve this |
| Negative keywords at campaign level but model has them at ad group level | `_negative_keyword_rows()` | Include `Ad Group` column or restructure |

### Minor Issues (Cosmetic)

| Issue | Location | Fix |
|-------|----------|-----|
| Template files not used by exporter | `data/templates/google_ads_editor/` | Either use templates to validate columns or remove them |
| Pin positions as strings vs. empty string | `_rsa_rows()` | Already correct, but document clearly |

---

## Report Generation Architecture

### Current State

The report generator (`report_generator.py`) produces:
1. **Markdown strategy report** - Complete, functional
2. **Keyword XLSX export** - Complete, functional

### PDF Generation Gap

The project mentions "Verify and fix PDF report generation" but:
- No PDF generation library is installed (`weasyprint`, `reportlab`, `xhtml2pdf` not in requirements.txt)
- `pypdf` is installed but is for READING PDFs, not generating them
- No PDF generation code exists in the codebase

**Recommended PDF pipeline:**

```
Markdown report string
    |
    v
markdown -> HTML (using markdown or markdown-it-py library)
    |
    v
HTML + CSS template (styling, branding, page layout)
    |
    v
HTML -> PDF (using weasyprint or xhtml2pdf)
    |
    v
output/{client}/strategy_report.pdf
```

**Library recommendation for Markdown-to-PDF:**

| Library | Pros | Cons | Recommendation |
|---------|------|------|----------------|
| weasyprint | Best CSS support, proper page breaks, headers/footers | Heavy install (cairo, pango deps), slow on Windows | Best quality but hardest to install |
| xhtml2pdf | Pure Python, easy install, pip-only | Limited CSS support, older codebase | Good enough for reports |
| markdown + pdfkit (wkhtmltopdf) | Good rendering | Requires wkhtmltopdf binary | External dependency |
| fpdf2 | Lightweight, pure Python | No HTML/Markdown input, manual layout | Too low-level |

**Recommendation:** Use `xhtml2pdf` for simplicity. It handles basic HTML/CSS well enough for strategy reports and installs cleanly with pip. If higher quality is needed later, upgrade to `weasyprint`.

**Confidence:** MEDIUM - Library recommendations based on training data, not verified against latest versions.

### Suggested PDF Generator Architecture

```python
# src/generators/pdf_generator.py

def generate_pdf_report(
    markdown_content: str,
    output_path: str,
    css_path: str | None = None,
) -> str:
    """Convert markdown strategy report to PDF.

    Pipeline: Markdown -> HTML -> PDF
    """
    # 1. Convert markdown to HTML
    # 2. Wrap in HTML template with CSS
    # 3. Render to PDF
    # 4. Return output path
```

Required additions to `requirements.txt`:
```
markdown>=3.5
xhtml2pdf>=0.2.11
```

---

## Suggested Build Order for Fixes

### Phase 1: Fix Critical CSV Issues (Must Do First)

1. **Remove `Row Type` from all row generators** - Simple find-and-delete across 7 functions
2. **Add `Campaign` column to sitelink and callout rows** - Requires deciding campaign scope (apply to all campaigns or first campaign)
3. **Split into per-entity-type CSV files** - Refactor `export_campaign_plan()` to produce multiple files

### Phase 2: Fix Moderate CSV Issues

4. **Fix negative keyword ad group scoping** - Add `Ad Group` column where applicable
5. **Validate column names against templates** - Use template files as column name source of truth
6. **Add import order documentation** - Generate a README with import instructions

### Phase 3: Add PDF Generation

7. **Add `markdown` and `xhtml2pdf` to requirements** - pip install
8. **Create CSS template for PDF styling** - Brand colors, fonts, page layout
9. **Implement `pdf_generator.py`** - Markdown -> HTML -> PDF pipeline
10. **Wire into report generation flow** - Generate both markdown and PDF

### Phase 4: Validation & Testing

11. **Create a test campaign plan and export** - Smoke test with known data
12. **Import test CSV into Google Ads Editor** - Manual verification
13. **Validate PDF output** - Check rendering, page breaks, Swedish characters

---

## Data Model Implications

### Sitelink/Callout Campaign Scope

The current `CampaignPlan` model stores sitelinks and callouts at the plan level, not campaign level:

```python
class CampaignPlan(BaseModel):
    campaigns: list[Campaign] = []
    sitelinks: list[Sitelink] = []      # Plan-level, not campaign-level
    callouts: list[Callout] = []        # Plan-level, not campaign-level
```

For Google Ads Editor export, extensions must be associated with a campaign. Options:

**Option A (Recommended):** Apply all sitelinks/callouts to all campaigns during export. The exporter generates one row per sitelink per campaign.

**Option B:** Add a `campaign_name: str | None` field to `Sitelink` and `Callout` models. This requires model changes but gives finer control.

**Option C:** Add `sitelinks` and `callouts` to the `Campaign` model. Most architecturally clean but requires significant refactoring.

**Recommendation:** Option A for now (export-time association), with Option C as a future improvement.

---

## Sources

- [CSV file columns - Google Ads Editor Help](https://support.google.com/google-ads/editor/answer/57747?hl=en) - Official column reference
- [Prepare a CSV file - Google Ads Editor Help](https://support.google.com/google-ads/editor/answer/56368?hl=en) - Format requirements
- [Import a CSV file - Google Ads Editor Help](https://support.google.com/google-ads/editor/answer/30564?hl=en-GB) - Import behavior
- [How to import a CSV file in Google Ads Editor - Digital Marketing Dan](https://digitalmarketingdan.com/how-to-import-a-csv-file-in-google-ads-editor/) - Practical examples and gotchas
- [6 Free Google Ads Editor Templates - Broadplace](https://broadplace.com/blog/6-free-downloadable-google-ads-editor-templates-for-optimal-efficiency/) - Template column references
- [Required bulksheet data for Google Ads - Adobe Advertising](https://experienceleague.adobe.com/en/docs/advertising/search-social-commerce/campaign-management/management/bulksheets/bulksheet-data-formats/bulksheet-data-google) - Detailed column specifications
- [Google Ads Editor bulk upload guide - AdConversion](https://www.adconversion.com/blog/google-ads-editor) - Best practices
