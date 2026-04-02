# SEM Master — SEO Analysis Feature Architecture Blueprint

> Generated from: `docs/SEO_REQUIREMENTS.md`
> Date: 2026-04-02
> Status: DRAFT — Pending Review

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Requirements Analysis](#2-requirements-analysis)
3. [Architecture Decision Records](#3-architecture-decision-records)
4. [Tech Stack](#4-tech-stack)
5. [Project Structure](#5-project-structure)
6. [Module & Function Definitions](#6-module--function-definitions)
7. [Data Models](#7-data-models)
8. [Interface Contracts](#8-interface-contracts)
9. [Data Flow Diagrams](#9-data-flow-diagrams)
10. [Dependency Map](#10-dependency-map)
11. [Cross-Cutting Concerns](#11-cross-cutting-concerns)
12. [Extensibility Guide](#12-extensibility-guide)
13. [Risk Register](#13-risk-register)
14. [Implementation Roadmap](#14-implementation-roadmap)
15. [Build Verification Checklist](#15-build-verification-checklist)

---

## 1. Executive Summary

This blueprint extends SEM Master with a comprehensive SEO analysis engine. Given any publicly accessible URL, the system performs deep on-page and technical SEO analysis, scores the site across five weighted categories, compares against competitor pages, and produces a prioritized list of specific, implementable fixes in Swedish with estimated business impact.

The feature integrates as an **optional side-stage** — a new `sem seo run` CLI command that operates independently or feeds data into the existing 8-stage SEM pipeline. It reuses the project's existing Playwright, httpx, Pydantic v2, and report generation infrastructure without introducing new Python dependencies.

**Key deliverables:**
- **14 new source files** across models, scrapers, analysis, generators, CLI, and tests
- **3 modified files** (CLI app registration, DigitalPresence model, CLAUDE.md)
- **1 new skill** (`sem-seo`) for Claude Code integration
- **0 new Python package dependencies**

---

## 2. Requirements Analysis

### 2.1 Core Features

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F-SEO-001 | Single Page SEO Scraping | Extract all SEO-relevant data from one rendered page via Playwright | Critical |
| F-SEO-002 | Site-Wide SEO Crawl | Crawl up to N pages, build internal link graph, detect orphan pages | Critical |
| F-SEO-003 | robots.txt & Sitemap Parsing | Fetch and parse robots.txt directives and sitemap.xml URLs | Critical |
| F-SEO-004 | Lighthouse Performance Scoring | Run Lighthouse CLI for Core Web Vitals and performance/accessibility/SEO scores | High |
| F-SEO-005 | Five-Category Scoring Engine | Score pages across On-page (30%), Technical (25%), Content (20%), Links (15%), Schema (10%) | Critical |
| F-SEO-006 | Issue Detection & Fix Generation | Produce actionable Swedish issues with severity, fix instructions, and impact estimates | Critical |
| F-SEO-007 | Competitor SEO Comparison | Scrape and score competitor pages, produce gap analysis | High |
| F-SEO-008 | Markdown Report Generation | Swedish-language report with scorecard, issues, competitor table, action plan | Critical |
| F-SEO-009 | PDF Export | Convert markdown report to PDF via existing `pdf_generator.py` | Medium |
| F-SEO-010 | XLSX Export | Export structured SEO data to multi-sheet XLSX workbook | Medium |
| F-SEO-011 | CLI Command | `sem seo run <url>` with mode, competitors, client, output, dry-run flags | Critical |
| F-SEO-012 | Pipeline Integration | Store results in `clients/{name}/seo/` when `--client` flag used | High |
| F-SEO-013 | Dry-Run Mode | Synthetic data path that exercises full analysis and report pipeline without network | High |
| F-SEO-014 | Claude Code Skill | `sem-seo` skill with appropriate trigger descriptions | Low |

### 2.2 User Roles & Journeys

**Single role: SEM Consultant (sole operator)**

**Journey 1 — Quick Page Audit:**
`sem seo run https://example.se` → scrape single page → analyze → score → print report to stdout/file.

**Journey 2 — Full Site Audit:**
`sem seo run https://example.se --mode site --max-pages 30` → crawl site → analyze each page + cross-page issues → aggregate scorecard → report.

**Journey 3 — Competitive SEO Comparison:**
`sem seo run https://example.se --competitors https://rival1.se,https://rival2.se` → scrape client + competitors → score all → gap analysis → report with comparison table.

**Journey 4 — SEM Pipeline Integration:**
`sem seo run https://example.se --client "klient-ab"` → full analysis → store in `clients/klient-ab/seo/` → data available for SEM keyword/campaign stages.

**Journey 5 — Demo/Testing:**
`sem seo run https://example.se --dry-run` → synthetic data → full pipeline → validates report generation works.

### 2.3 Constraints

| Constraint | Value |
|-----------|-------|
| Python version | >= 3.11 (per pyproject.toml) |
| New Python packages | 0 (must use existing deps) |
| Lighthouse CLI | Optional system dependency, graceful fallback |
| Single page target time | < 30 seconds |
| Site crawl target time (30 pages) | < 5 minutes (1.5s delay between pages) |
| All client-facing text | Swedish |
| Internal code language | English |
| Line length | 100 chars (per ruff config) |
| Test framework | pytest + pytest-asyncio |

### 2.4 Integrations

| System | Integration Type | Notes |
|--------|-----------------|-------|
| Existing SEM pipeline | Optional data feed | Via `--client` flag; stores JSON in client dir |
| Lighthouse CLI | Subprocess | `lighthouse <url> --output=json --chrome-flags="--headless"` |
| Playwright | Browser automation | Reuses existing dependency for DOM inspection |
| httpx | HTTP client | For robots.txt, sitemap.xml, HTTP header checks |
| BeautifulSoup + lxml | HTML/XML parsing | For sitemap XML parsing |
| markdown-pdf | PDF generation | Via existing `pdf_generator.py` |
| openpyxl | XLSX generation | For multi-sheet data export |

### 2.5 Resolved Ambiguities

| # | Ambiguity | Resolution |
|---|-----------|-----------|
| A1 | Should SEO be a mandatory pipeline stage? | **No.** Optional side-stage. Does not modify `PIPELINE_STAGES` or `STAGE_PREREQUISITES` in `state.py`. SEO data is stored alongside pipeline data but doesn't gate other stages. |
| A2 | Modify existing `site_crawler.py` or create new scraper? | **New scraper.** SEO collects fundamentally different data (schema markup, canonical tags, HTTP headers). Modifying `site_crawler.py` risks breaking the existing 8-stage pipeline. |
| A3 | How to handle Lighthouse unavailability? | **Graceful fallback.** Check `shutil.which("lighthouse")`. If absent, skip CWV scoring, set `lighthouse` field to `None`, include advisory note in report. Technical score computed from non-CWV checks only. |
| A4 | Output location for standalone mode (no `--client`)? | **Current working directory.** Write `seo_report.md` (and PDF/XLSX if requested) to cwd. Print report path to console. |
| A5 | How does SEO data feed into the SEM pipeline? | **Passive integration.** Add optional `seo_data` field to `DigitalPresence` model. Research commands can check for `clients/{name}/seo/seo_analysis.json` and load it if present. No code changes to research stage required initially — just model extension. |

---

## 3. Architecture Decision Records

### ADR-SEO-001: Separate SEO Scraper

**Decision:** Create `src/scrapers/seo_scraper.py` as a new file, not modify `site_crawler.py`.

**Alternatives:**
1. Extend `_extract_page()` in `site_crawler.py` to also collect SEO data
2. Create a wrapper that calls `site_crawler.crawl_site()` then enriches results
3. New independent scraper (chosen)

**Rationale:** The existing `_extract_page()` returns `CrawledPage` which has a different shape from SEO data (no schema, canonical, hreflang, images, HTTP headers). Extending it would either (a) bloat `CrawledPage` with 20+ new fields most consumers don't need, or (b) require a conditional path that complicates the function. A separate scraper follows the project's pattern of one-scraper-per-concern (gbp_scraper, review_scraper, social_scraper, transparency_scraper) and keeps both codepaths independently testable.

### ADR-SEO-002: Optional Side-Stage Architecture

**Decision:** SEO is not added to `PIPELINE_STAGES` in `state.py`.

**Alternatives:**
1. Add "seo" as stage 2.5 between research and competitors
2. Add "seo" as an optional stage with skip capability
3. Keep SEO completely outside the pipeline state machine (chosen)

**Rationale:** Adding to `PIPELINE_STAGES` requires modifying `update_state()` validation, `check_prerequisites()`, `initialize_state()`, and `get_next_stage()`. It also means every existing client's `workflow_state.json` needs migration. The SEO feature provides value independently and does not produce data that other pipeline stages strictly depend on. Keeping it outside avoids all migration risk and lets users run SEO analysis at any time, even before intake.

### ADR-SEO-003: Lighthouse via CLI Subprocess

**Decision:** Use Lighthouse CLI via `asyncio.create_subprocess_exec`, not Chrome DevTools Protocol.

**Alternatives:**
1. Chrome DevTools Protocol via MCP tools
2. Google PageSpeed Insights API (requires API key)
3. Lighthouse CLI subprocess (chosen)

**Rationale:** Lighthouse CLI bundles all audits in a single invocation, outputs structured JSON, and requires no API keys. CDP would require implementing individual audit collection logic. PageSpeed Insights API introduces a paid-API dependency which contradicts the no-paid-APIs requirement. The CLI approach is the simplest, and `shutil.which("lighthouse")` provides a clean availability check. `asyncio.create_subprocess_exec` keeps it non-blocking.

### ADR-SEO-004: Score-Based Issue System

**Decision:** Issues carry machine-readable `severity`, `category`, `effort` fields plus human-readable Swedish `fix_suggestion` and `impact_estimate` strings.

**Rationale:** Machine-readable fields enable programmatic sorting (high→low severity, impact/effort ratio) and XLSX export with filterable columns. Swedish text fields enable direct client-facing presentation. This dual approach means the report generator can both auto-sort and display readable content. The effort field (low/medium/high) enables a "quick wins first" action plan.

### ADR-SEO-005: Swedish-First Issue Templates

**Decision:** Issue titles, descriptions, fix suggestions, and impact estimates are generated in Swedish at analysis time, not translated post-hoc.

**Rationale:** Translation post-hoc risks awkward phrasing and misses Swedish market context (e.g., Swedish SERP behaviors, local business norms). The project already generates all client-facing content in Swedish (ad copy, reports, CLI output). Hard-coding Swedish in the analyzer follows this established pattern and produces natural-sounding recommendations.

---

## 4. Tech Stack

No additions to the existing tech stack. All features built using:

| Layer | Technology | Existing Dependency |
|-------|-----------|-------------------|
| Browser automation | Playwright (async) | `playwright>=1.40` |
| HTTP client | httpx (async) | `httpx>=0.25` |
| HTML parsing | BeautifulSoup4 + lxml | `beautifulsoup4>=4.12`, `lxml>=4.9` |
| Data validation | Pydantic v2 | `pydantic>=2.5` |
| CLI framework | Typer + Rich | `typer[all]>=0.12`, `rich>=13.0` |
| PDF generation | markdown-pdf | `markdown-pdf>=1.13` |
| XLSX export | openpyxl | `openpyxl>=3.1` |
| Performance audit | Lighthouse CLI | System dep, optional |
| XML parsing (sitemap) | lxml.etree | `lxml>=4.9` |

---

## 5. Project Structure

New and modified files shown with annotations. Existing unchanged files omitted.

```
src/
  models/
    seo.py                          # NEW — All SEO Pydantic models (PageSeoData, SiteSeoData, scores, issues, etc.)
    research.py                     # MOD — Add optional seo_data field to DigitalPresence
  scrapers/
    seo_scraper.py                  # NEW — Playwright-based SEO data extraction (per-page and site-wide)
    robots_sitemap.py               # NEW — httpx-based robots.txt + sitemap.xml fetcher/parser
    lighthouse_runner.py            # NEW — Lighthouse CLI subprocess wrapper with graceful fallback
  analysis/
    seo_analyzer.py                 # NEW — 5-category scoring engine, issue detection, fix generation
    seo_competitor.py               # NEW — Competitor SEO comparison and gap analysis
  generators/
    seo_report_generator.py         # NEW — Swedish markdown/PDF/XLSX SEO report builder
  cli/
    seo_commands.py                 # NEW — `sem seo` Typer command group
    app.py                          # MOD — Register seo_app Typer group
tests/
  test_seo_models.py               # NEW — Pydantic model validation tests
  test_seo_scraper.py              # NEW — Scraper unit tests (mocked Playwright Page)
  test_seo_analyzer.py             # NEW — Scoring engine + issue generation tests
  test_seo_competitor.py           # NEW — Competitor comparison + gap analysis tests
  test_seo_report.py               # NEW — Report generation tests
CLAUDE.md                          # MOD — Add sem seo command docs
~/.claude/skills/sem-seo/SKILL.md  # NEW — Claude Code skill definition
```

---

## 6. Module & Function Definitions

### 6.1 Models Module (`src/models/seo.py`)

**Purpose:** Define all Pydantic v2 data models for SEO analysis — from raw scraped data through scoring to final analysis result.

No functions — pure data definitions. See [Section 7: Data Models](#7-data-models) for complete field-level specifications.

### 6.2 SEO Scraper Module (`src/scrapers/seo_scraper.py`)

**Purpose:** Extract comprehensive SEO data from web pages using Playwright. Provides both single-page deep-dive and multi-page site crawl modes.

---

#### `extract_page_seo(page: Page, url: str) -> PageSeoData`

**Purpose:** Extract all SEO-relevant data from a single rendered Playwright page. This is the core extraction function that all higher-level functions call.

**Params:**
- `page` (playwright.async_api.Page): An already-navigated Playwright page instance. Must have completed navigation (caller is responsible for `page.goto()`).
- `url` (str): The URL of the page being analyzed. Used as the canonical reference URL in the returned model.

**Returns:** `PageSeoData` — fully populated model with all on-page SEO data points: title, meta tags, headings, images, links, schema markup, OG/Twitter tags, render-blocking resources.

**Side effects:** None. Reads DOM state only via `page.evaluate()`.

**Error cases:**
- JavaScript evaluation timeout: Catch, log warning, return partial data with available fields populated and missing fields at defaults.
- Malformed DOM (e.g., missing `<head>`): Fields that depend on missing elements return empty defaults per Pydantic model.

**Called by:** `crawl_seo_single()`, `crawl_seo_site()`, `analyze_competitor_seo()` (in `seo_competitor.py`)

**Calls:** None (leaf function — all work done via `page.evaluate()` JavaScript snippets)

**Implementation notes:**

The function executes a series of `page.evaluate()` calls to extract data from the DOM. Key JavaScript snippets:

1. **Meta tags extraction:**
```javascript
() => {
  const metas = document.querySelectorAll('meta');
  return Array.from(metas).map(m => ({
    name: m.getAttribute('name') || m.getAttribute('property') || m.getAttribute('http-equiv') || '',
    content: m.getAttribute('content') || ''
  }));
}
```

2. **Schema markup (JSON-LD):**
```javascript
() => {
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');
  return Array.from(scripts).map(s => {
    try { return JSON.parse(s.textContent); }
    catch { return null; }
  }).filter(Boolean);
}
```

3. **Canonical tag:**
```javascript
() => document.querySelector('link[rel="canonical"]')?.href || null
```

4. **Hreflang tags:**
```javascript
() => Array.from(document.querySelectorAll('link[rel="alternate"][hreflang]'))
  .map(l => ({ lang: l.getAttribute('hreflang'), url: l.href }))
```

5. **Image audit:**
```javascript
() => Array.from(document.querySelectorAll('img')).map(img => ({
  src: img.src,
  alt: img.alt || '',
  has_alt: img.hasAttribute('alt') && img.alt.trim() !== '',
  width: img.naturalWidth || img.width || null,
  height: img.naturalHeight || img.height || null,
  is_lazy_loaded: img.loading === 'lazy' || img.hasAttribute('data-src')
}))
```

6. **Internal/external link extraction:**
```javascript
() => {
  const origin = window.location.origin;
  return Array.from(document.querySelectorAll('a[href]')).map(a => ({
    url: a.href,
    anchor_text: a.innerText?.trim() || '',
    is_external: !a.href.startsWith(origin),
    is_nofollow: a.rel?.includes('nofollow') || false
  }));
}
```

7. **Render-blocking resources:**
```javascript
() => {
  const blocking = [];
  document.querySelectorAll('link[rel="stylesheet"]:not([media="print"]):not([media="none"])').forEach(l => blocking.push(l.href));
  document.querySelectorAll('script:not([defer]):not([async]):not([type="module"]):not([type="application/ld+json"])').forEach(s => { if (s.src) blocking.push(s.src); });
  return blocking;
}
```

8. **Heading hierarchy:**
```javascript
() => Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
  .map(h => ({ tag: h.tagName.toLowerCase(), text: h.innerText?.trim() || '' }))
```

9. **Open Graph & Twitter Card:**
```javascript
() => {
  const og = Array.from(document.querySelectorAll('meta[property^="og:"]'))
    .map(m => ({ name: m.getAttribute('property'), content: m.content }));
  const tw = Array.from(document.querySelectorAll('meta[name^="twitter:"]'))
    .map(m => ({ name: m.name, content: m.content }));
  return { og, tw };
}
```

10. **Robots meta:**
```javascript
() => document.querySelector('meta[name="robots"]')?.content || ''
```

---

#### `_extract_http_details(response: Response | None, url: str) -> dict`

**Purpose:** Extract HTTP-level details from a Playwright Response object — status code, redirect chain, response headers.

**Params:**
- `response` (playwright.async_api.Response | None): The response from `page.goto()`.
- `url` (str): The original requested URL.

**Returns:** `dict` with keys: `status_code` (int), `redirect_chain` (list[str]), `content_type` (str), `http_headers` (dict[str, str]).

**Side effects:** None.

**Error cases:** If response is unavailable (e.g., page was navigated without capturing response), return defaults: `status_code=0`, empty redirect chain, empty headers.

**Called by:** `crawl_seo_single()`, `crawl_seo_site()` (before calling `extract_page_seo()`)

**Calls:** None.

**Implementation notes:** The caller captures the `Response` object from `page.goto()` and passes it or the page. This function inspects `page.context` request/response chain. Alternatively, the caller can pass the response object directly — see `crawl_seo_single()` for the exact pattern.

---

#### `crawl_seo_single(url: str) -> PageSeoData`

**Purpose:** Perform a complete SEO analysis of a single page. Launches Playwright browser, navigates, extracts all data, merges HTTP details into the model, closes browser.

**Params:**
- `url` (str): The URL to analyze. Must be a valid HTTP/HTTPS URL.

**Returns:** `PageSeoData` with HTTP details (status_code, redirect_chain, content_type, http_headers) merged in.

**Side effects:**
- Launches and closes a headless Chromium browser instance.
- Makes one HTTP request to the target URL.

**Error cases:**
- URL unreachable (DNS failure, timeout): Raise `ConnectionError` with descriptive message. Caller handles.
- Page load timeout (>15s): Catch Playwright `TimeoutError`, return partial `PageSeoData` with `status_code=0` and available fields.
- Browser launch failure: Raise `RuntimeError`. Likely cause: Playwright not installed (`playwright install chromium` not run).

**Called by:** `run()` in `seo_commands.py`, `analyze_competitor_seo()` in `seo_competitor.py`

**Calls:** `extract_page_seo()`, `_check_http_details()`

---

#### `crawl_seo_site(url: str, max_pages: int = 30) -> SiteSeoData`

**Purpose:** Crawl an entire website collecting SEO data from each page. Follows internal links breadth-first up to `max_pages`. Mirrors the crawl loop pattern from `site_crawler.py:crawl_site()`.

**Params:**
- `url` (str): Starting URL (homepage). Internal links from this domain are followed.
- `max_pages` (int): Maximum pages to crawl. Default 30.

**Returns:** `SiteSeoData` — aggregated site-level data including list of `PageSeoData` for each crawled page, plus computed `orphan_pages` list.

**Side effects:**
- Launches and closes a headless Chromium browser instance.
- Makes HTTP requests to up to `max_pages` URLs on the target domain.
- 1.5 second delay between page loads (matching `site_crawler.py` convention).

**Error cases:**
- Individual page failures: Log warning, skip page, continue crawl.
- All pages fail: Return `SiteSeoData` with empty pages list and `total_pages_crawled=0`.
- URL unreachable: First page failure raises `ConnectionError`.

**Called by:** `run()` in `seo_commands.py`

**Calls:** `extract_page_seo()`, `_check_http_details()`

**Implementation notes:**
- Uses the same BFS crawl loop as `site_crawler.py:crawl_site()`:
  ```
  visited set, to_visit queue, while to_visit and len(pages) < max_pages
  ```
- After crawl completes, computes orphan pages: pages that exist in `SiteSeoData.pages` but are not in any other page's `internal_links`.
- Browser context configured with same user agent and locale as existing crawler:
  ```python
  user_agent="Mozilla/5.0 (compatible; SEMMasterBot/1.0)"
  locale="sv-SE"
  ```

---

#### `generate_synthetic_page_data(url: str) -> PageSeoData`

**Purpose:** Generate realistic synthetic SEO data for dry-run mode. Produces data that exercises all scoring paths.

**Params:**
- `url` (str): The URL to use in the synthetic data.

**Returns:** `PageSeoData` with plausible values including some deliberate issues (missing alt text, short meta description, no schema) to demonstrate the scoring system.

**Side effects:** None.

**Called by:** `run()` in `seo_commands.py` (when `--dry-run` flag set)

**Calls:** None.

---

#### `generate_synthetic_site_data(url: str) -> SiteSeoData`

**Purpose:** Generate realistic synthetic site-level SEO data for dry-run mode. Creates 5-8 synthetic pages with varying quality levels.

**Params:**
- `url` (str): The base URL for the synthetic site.

**Returns:** `SiteSeoData` with synthetic pages, robots.txt, sitemap data, and some orphan pages.

**Side effects:** None.

**Called by:** `run()` in `seo_commands.py` (when `--dry-run` flag set)

**Calls:** `generate_synthetic_page_data()`

---

### 6.3 Robots & Sitemap Module (`src/scrapers/robots_sitemap.py`)

**Purpose:** Fetch and parse `robots.txt` and `sitemap.xml` files using httpx (no browser needed).

---

#### `fetch_robots_txt(domain: str) -> RobotsTxtData`

**Purpose:** Fetch and parse a domain's robots.txt file.

**Params:**
- `domain` (str): Domain name (e.g., "example.se"). Protocol prefix will be added as `https://`.

**Returns:** `RobotsTxtData` — parsed structure with `exists`, `allows_crawling`, `sitemap_urls`, `disallowed_paths`, `raw_content`.

**Side effects:** One HTTP GET request to `https://{domain}/robots.txt`.

**Error cases:**
- 404 response: Return `RobotsTxtData(exists=False, allows_crawling=True)`.
- Connection error: Log warning, return `RobotsTxtData(exists=False)`.
- Malformed robots.txt: Parse what's parseable, ignore malformed lines.

**Called by:** `crawl_seo_site()`, `run()` in `seo_commands.py`

**Calls:** None (uses httpx directly).

**Implementation notes:**
- Parse `User-agent: *` directives only (sufficient for SEO audit).
- Extract all `Sitemap:` directives into `sitemap_urls`.
- Check `Disallow: /` (blocks all crawling) to set `allows_crawling`.
- Store `raw_content` for display in technical SEO report section.

---

#### `fetch_sitemap(url: str) -> SitemapData`

**Purpose:** Fetch and parse a single sitemap XML file. Handles both regular sitemaps and sitemap index files.

**Params:**
- `url` (str): Full URL to the sitemap file (e.g., `https://example.se/sitemap.xml`).

**Returns:** `SitemapData` — with `exists`, `url`, `page_count`, `urls` list, `last_modified`.

**Side effects:** One or more HTTP GET requests (if sitemap index, follows child sitemap links — max 5 children to avoid runaway).

**Error cases:**
- 404: Return `SitemapData(exists=False, url=url)`.
- Invalid XML: Log warning, return `SitemapData(exists=False)`.
- Sitemap index with >5 children: Parse first 5, log that additional sitemaps were skipped.

**Called by:** `discover_sitemaps()`

**Calls:** Recursive self-call for sitemap index entries (max depth 1, max children 5).

**Implementation notes:**
- Uses `lxml.etree.fromstring()` for XML parsing.
- Handles namespace: `{http://www.sitemaps.org/schemas/sitemap/0.9}`.
- Detects sitemap index via `<sitemapindex>` root element vs `<urlset>`.

---

#### `discover_sitemaps(domain: str, robots_data: RobotsTxtData) -> list[SitemapData]`

**Purpose:** Discover all sitemaps for a domain. Checks robots.txt references first, then tries common paths.

**Params:**
- `domain` (str): Domain name.
- `robots_data` (RobotsTxtData): Previously fetched robots.txt data (to avoid re-fetching).

**Returns:** List of `SitemapData` objects. May be empty if no sitemaps found.

**Side effects:** HTTP GET requests to each candidate sitemap URL.

**Error cases:** All errors handled per-sitemap via `fetch_sitemap()`. Never raises.

**Called by:** `crawl_seo_site()`, `run()` in `seo_commands.py`

**Calls:** `fetch_sitemap()`

**Implementation notes:**
- Check `robots_data.sitemap_urls` first.
- If no sitemaps from robots.txt, try: `https://{domain}/sitemap.xml`, `https://{domain}/sitemap_index.xml`.
- Deduplicate by URL.

---

### 6.4 Lighthouse Runner Module (`src/scrapers/lighthouse_runner.py`)

**Purpose:** Run Google Lighthouse CLI as a subprocess and parse the JSON output for performance and SEO scores.

---

#### `lighthouse_available() -> bool`

**Purpose:** Check if the Lighthouse CLI is installed and available on PATH.

**Params:** None.

**Returns:** `True` if `shutil.which("lighthouse")` finds the binary, `False` otherwise.

**Side effects:** None.

**Called by:** `run()` in `seo_commands.py`, `run_lighthouse()`

**Calls:** `shutil.which()`

---

#### `run_lighthouse(url: str, categories: list[str] | None = None) -> LighthouseResult`

**Purpose:** Execute Lighthouse CLI against a URL and parse the JSON output into a `LighthouseResult` model.

**Params:**
- `url` (str): URL to audit.
- `categories` (list[str] | None): Lighthouse categories to audit. Default: `["performance", "accessibility", "best-practices", "seo"]`.

**Returns:** `LighthouseResult` with scores and Core Web Vitals metrics.

**Side effects:**
- Spawns a Lighthouse CLI subprocess.
- Writes temporary JSON file (cleaned up after parsing).
- Takes 10-30 seconds per URL.

**Error cases:**
- Lighthouse not installed: Return empty `LighthouseResult` with all scores `None`. Log advisory.
- Lighthouse process timeout (60s): Kill process, return empty result.
- Lighthouse process crash: Return empty result, log error with stderr output.
- Malformed JSON output: Return empty result, log error.

**Called by:** `run()` in `seo_commands.py`

**Calls:** `lighthouse_available()`, `asyncio.create_subprocess_exec()`

**Implementation notes:**
- Command: `lighthouse {url} --output=json --output-path={tmpfile} --chrome-flags="--headless --no-sandbox" --quiet`
- Parse categories: `json_data["categories"][cat]["score"]` (0.0-1.0, multiply by 100).
- Parse CWV from `json_data["audits"]`:
  - LCP: `audits["largest-contentful-paint"]["numericValue"]`
  - FID/TBT: `audits["total-blocking-time"]["numericValue"]` (TBT is proxy for FID)
  - CLS: `audits["cumulative-layout-shift"]["numericValue"]`
  - FCP: `audits["first-contentful-paint"]["numericValue"]`
  - SI: `audits["speed-index"]["numericValue"]`
  - TTFB: `audits["server-response-time"]["numericValue"]`
- Parse opportunities: `json_data["audits"]` where `details.type == "opportunity"`.
- Timeout: 60 seconds via `asyncio.wait_for()`.

---

### 6.5 SEO Analyzer Module (`src/analysis/seo_analyzer.py`)

**Purpose:** Score SEO health across five categories, detect issues, and generate specific Swedish fix suggestions with impact estimates.

---

#### `analyze_page_seo(page: PageSeoData, lighthouse: LighthouseResult | None = None) -> SeoScorecard`

**Purpose:** Score a single page across all five SEO categories. Entry point for single-page analysis mode.

**Params:**
- `page` (PageSeoData): Complete SEO data for one page.
- `lighthouse` (LighthouseResult | None): Lighthouse results if available.

**Returns:** `SeoScorecard` with overall weighted score, per-category scores, and all detected issues.

**Side effects:** None (pure function).

**Error cases:** None — handles all edge cases (empty data, missing fields) via defaults.

**Called by:** `run()` in `seo_commands.py`, `analyze_site_seo()`, `analyze_competitor_seo()` in `seo_competitor.py`

**Calls:** `_score_on_page()`, `_score_technical()`, `_score_content()`, `_score_links()`, `_score_schema()`

**Implementation notes:**
- Weighted score calculation:
  ```python
  overall = (on_page * 0.30 + technical * 0.25 + content * 0.20 + links * 0.15 + schema * 0.10)
  ```
- Aggregates issues from all five scoring functions.
- Generates `summary_sv` — a 2-3 sentence Swedish summary of the findings.

---

#### `analyze_site_seo(site: SiteSeoData, lighthouse: LighthouseResult | None = None) -> SeoScorecard`

**Purpose:** Score an entire site. Runs per-page scoring then adds site-level checks (cross-page duplicates, orphan pages, sitemap/robots.txt).

**Params:**
- `site` (SiteSeoData): Complete site-level data with all crawled pages.
- `lighthouse` (LighthouseResult | None): Lighthouse results (typically for homepage only).

**Returns:** `SeoScorecard` with aggregated scores and both page-level and site-level issues.

**Side effects:** None (pure function).

**Called by:** `run()` in `seo_commands.py`

**Calls:** `analyze_page_seo()` (for each page), `_detect_site_level_issues()`

**Implementation notes:**
- Per-category scores are averaged across all pages.
- Site-level issues added on top: duplicate titles, duplicate meta descriptions, orphan pages, missing sitemap, robots.txt problems.
- Homepage gets Lighthouse data; other pages don't (one Lighthouse run per analysis).

---

#### `_score_on_page(page: PageSeoData) -> tuple[float, list[SeoIssue]]`

**Purpose:** Score on-page SEO factors. Weight: 30% of overall.

**Params:**
- `page` (PageSeoData): Page data to score.

**Returns:** Tuple of (score 0-100, list of issues found).

**Checks performed (each contributes to score):**

| Check | Points | Ideal | Issue if Failing |
|-------|--------|-------|-----------------|
| Title present | 15 | Non-empty | "Saknar title-tagg" (HIGH) |
| Title length | 10 | 50-60 chars | "Title-tagg for kort/lang" (MEDIUM) |
| Meta description present | 15 | Non-empty | "Saknar meta-beskrivning" (HIGH) |
| Meta description length | 10 | 120-160 chars | "Meta-beskrivning for kort/lang" (MEDIUM) |
| H1 present | 15 | Exactly 1 | "Saknar H1-tagg" / "Flera H1-taggar" (HIGH) |
| Heading hierarchy valid | 10 | No skipped levels | "Bruten rubrikhierarki" (MEDIUM) |
| Canonical tag present | 10 | Self-referencing | "Saknar canonical-tagg" (MEDIUM) |
| OG tags present | 10 | og:title + og:description + og:image | "Saknar Open Graph-taggar" (LOW) |
| Twitter Card present | 5 | twitter:card + twitter:title | "Saknar Twitter Card-taggar" (LOW) |

**Called by:** `analyze_page_seo()`

**Calls:** None.

---

#### `_score_technical(page: PageSeoData, lighthouse: LighthouseResult | None) -> tuple[float, list[SeoIssue]]`

**Purpose:** Score technical SEO factors. Weight: 25% of overall.

**Params:**
- `page` (PageSeoData): Page data.
- `lighthouse` (LighthouseResult | None): Lighthouse data.

**Returns:** Tuple of (score 0-100, list of issues).

**Checks performed:**

| Check | Points | Ideal | Issue if Failing |
|-------|--------|-------|-----------------|
| Status code 200 | 15 | 200 | "Sidan returnerar statuskod {X}" (HIGH) |
| No redirect chain | 10 | 0-1 redirects | "Omdirigerings-kedja ({N} steg)" (MEDIUM) |
| HTTPS | 15 | URL starts with https | "Sidan anvander inte HTTPS" (HIGH) |
| LCP | 15 | <2500ms | "LCP for hog: {X}ms" (HIGH if >4000, MEDIUM if >2500) |
| CLS | 10 | <0.1 | "CLS for hogt: {X}" (HIGH if >0.25, MEDIUM if >0.1) |
| TBT/FID | 10 | TBT <200ms | "Total Blocking Time for hog" (MEDIUM) |
| Render-blocking resources | 10 | 0-2 | "{N} resurser blockerar rendering" (LOW/MEDIUM) |
| Robots meta allows indexing | 15 | index,follow or empty | "Sidan blockerar indexering" (HIGH) |

If Lighthouse is unavailable, CWV checks are skipped and remaining checks are rescaled to 100.

**Called by:** `analyze_page_seo()`

**Calls:** None.

---

#### `_score_content(page: PageSeoData) -> tuple[float, list[SeoIssue]]`

**Purpose:** Score content quality factors. Weight: 20% of overall.

**Params:**
- `page` (PageSeoData): Page data.

**Returns:** Tuple of (score 0-100, list of issues).

**Checks performed:**

| Check | Points | Ideal | Issue if Failing |
|-------|--------|-------|-----------------|
| Word count adequate | 40 | >= 300 words | "Tunt innehall ({N} ord)" (HIGH if <100, MEDIUM if <300) |
| Word count good | 20 | >= 800 words | Bonus points, no issue |
| Word count excellent | 10 | >= 1500 words | Bonus points, no issue |
| Images present | 15 | >= 1 image | "Sidan saknar bilder" (LOW) |
| Images have alt text | 15 | 100% | "{N} bilder saknar alt-text" (MEDIUM) |

**Called by:** `analyze_page_seo()`

**Calls:** None.

---

#### `_score_links(page: PageSeoData, site: SiteSeoData | None = None) -> tuple[float, list[SeoIssue]]`

**Purpose:** Score link structure. Weight: 15% of overall.

**Params:**
- `page` (PageSeoData): Page data.
- `site` (SiteSeoData | None): Site data (for orphan page detection in site mode).

**Returns:** Tuple of (score 0-100, list of issues).

**Checks performed:**

| Check | Points | Ideal | Issue if Failing |
|-------|--------|-------|-----------------|
| Internal links present | 30 | >= 3 | "For fa interna lankar ({N})" (MEDIUM) |
| Internal links adequate | 20 | >= 5 | Bonus points |
| External links present | 15 | >= 1 | "Inga externa lankar" (LOW) |
| No broken links | 20 | 0 broken | "{N} trasiga lankar" (HIGH) |
| Page not orphaned | 15 | Linked from >=1 other page | "Foraldralos sida" (MEDIUM) (site mode only) |

**Called by:** `analyze_page_seo()`, `analyze_site_seo()`

**Calls:** None.

---

#### `_score_schema(page: PageSeoData) -> tuple[float, list[SeoIssue]]`

**Purpose:** Score structured data / schema markup. Weight: 10% of overall.

**Params:**
- `page` (PageSeoData): Page data.

**Returns:** Tuple of (score 0-100, list of issues).

**Checks performed:**

| Check | Points | Ideal | Issue if Failing |
|-------|--------|-------|-----------------|
| JSON-LD present | 40 | >= 1 block | "Saknar schema markup (JSON-LD)" (MEDIUM) |
| Schema type appropriate | 30 | LocalBusiness, Product, FAQ, etc. | "Schema-typ saknas for {page type}" (LOW) |
| Required fields present | 30 | Per schema type | "Schema saknar obligatoriska falt" (LOW) |

**Called by:** `analyze_page_seo()`

**Calls:** None.

**Implementation notes:**
- Schema appropriateness heuristics:
  - Homepage/about: `LocalBusiness` or `Organization`
  - Product/service pages: `Product` or `Service`
  - FAQ page (detected by heading content): `FAQPage`
  - Contact page (detected by form + address): `LocalBusiness` with `address`
  - Blog post: `Article` or `BlogPosting`
- Page type detection is heuristic-based on URL path and content keywords.

---

#### `_detect_site_level_issues(site: SiteSeoData) -> list[SeoIssue]`

**Purpose:** Detect issues that only appear at the site level, not per-page.

**Params:**
- `site` (SiteSeoData): Complete site data.

**Returns:** List of site-level `SeoIssue` objects.

**Checks:**
- Duplicate title tags across pages → "Duplicerade title-taggar ({N} sidor)" (MEDIUM)
- Duplicate meta descriptions → "Duplicerade meta-beskrivningar ({N} sidor)" (MEDIUM)
- Orphan pages (not linked from any other page) → "Foraldralosa sidor ({N} sidor)" (MEDIUM)
- Missing robots.txt → "Saknar robots.txt" (LOW)
- Missing sitemap → "Saknar sitemap.xml" (MEDIUM)
- robots.txt blocks crawling → "robots.txt blockerar crawlning" (HIGH)

**Called by:** `analyze_site_seo()`

**Calls:** None.

---

#### `_generate_impact_estimate(issue_type: str, severity: str, count: int) -> str`

**Purpose:** Generate a Swedish impact estimate string for an issue based on type and severity.

**Params:**
- `issue_type` (str): Machine-readable issue type (e.g., "missing_meta_description").
- `severity` (str): "high", "medium", or "low".
- `count` (int): Number of affected pages.

**Returns:** Swedish string like "Uppskattat +15-25% CTR i Googles sokresultat".

**Side effects:** None.

**Called by:** All `_score_*` functions when creating `SeoIssue` objects.

**Calls:** None.

**Implementation notes:**
- Uses a lookup table of issue_type → impact template string.
- Impact estimates are conservative ranges based on industry benchmarks:
  - Missing title: "Sidor utan title-tagg syns ofta inte i sokresultat alls"
  - Missing meta desc: "Uppskattat +15-25% CTR med optimerade meta-beskrivningar"
  - Missing H1: "Forbattrar Googles forstaelse av sidans amne, kan oka relevansranking"
  - Slow LCP: "Google prioriterar sidor med LCP under 2.5s — kan forbattra ranking"
  - Missing schema: "Mojliggor rich snippets, uppskattat +20-30% synlighet i SERP"
  - Missing sitemap: "Forbattrar crawlningseffektivitet, snabbare indexering av nya sidor"

---

### 6.6 SEO Competitor Module (`src/analysis/seo_competitor.py`)

**Purpose:** Scrape and score competitor pages, produce gap analysis comparing client vs. competitors.

---

#### `analyze_competitor_seo(client_url: str, competitor_urls: list[str], client_scorecard: SeoScorecard, client_page: PageSeoData) -> SeoCompetitorAnalysis`

**Purpose:** Scrape each competitor URL, score it, and produce a comparative analysis.

**Params:**
- `client_url` (str): Client's URL (for reference).
- `competitor_urls` (list[str]): List of competitor URLs to analyze.
- `client_scorecard` (SeoScorecard): Client's already-computed scorecard.
- `client_page` (PageSeoData): Client's page data (for field-level comparison).

**Returns:** `SeoCompetitorAnalysis` with competitor profiles, gaps, and advantages.

**Side effects:**
- Launches Playwright browser for each competitor URL.
- Makes HTTP requests.

**Error cases:**
- Competitor URL unreachable: Skip competitor, log warning, include note in result.
- Partial competitor data: Score with available data.

**Called by:** `run()` in `seo_commands.py`

**Calls:** `crawl_seo_single()` (from `seo_scraper.py`), `analyze_page_seo()` (from `seo_analyzer.py`), `_compute_gaps()`, `_identify_advantages()`

---

#### `_compute_gaps(client: PageSeoData, client_score: SeoScorecard, competitor: PageSeoData, competitor_score: SeoScorecard) -> list[SeoGap]`

**Purpose:** Compare client and competitor on specific SEO dimensions and return gaps where competitor is stronger.

**Params:**
- `client` (PageSeoData): Client's page data.
- `client_score` (SeoScorecard): Client's scorecard.
- `competitor` (PageSeoData): Competitor's page data.
- `competitor_score` (SeoScorecard): Competitor's scorecard.

**Returns:** List of `SeoGap` objects.

**Side effects:** None.

**Comparison dimensions:**
- Schema types present (competitor has FAQ schema, client doesn't)
- Content length (competitor has significantly more content)
- CWV scores (competitor is faster)
- Internal link count (competitor has better internal linking)
- Image optimization (competitor has better alt text coverage)
- Meta description quality (competitor has optimized meta descriptions, client doesn't)
- Heading structure (competitor has proper hierarchy, client doesn't)

Each gap generates a specific Swedish `recommendation` string.

**Called by:** `analyze_competitor_seo()`

**Calls:** None.

---

#### `_identify_advantages(client_score: SeoScorecard, competitor_scores: list[SeoScorecard]) -> list[str]`

**Purpose:** Identify categories where the client outperforms all competitors.

**Params:**
- `client_score` (SeoScorecard): Client's scorecard.
- `competitor_scores` (list[SeoScorecard]): All competitor scorecards.

**Returns:** List of Swedish advantage description strings.

**Side effects:** None.

**Called by:** `analyze_competitor_seo()`

**Calls:** None.

---

#### `generate_synthetic_competitor_data(competitor_urls: list[str], client_scorecard: SeoScorecard) -> SeoCompetitorAnalysis`

**Purpose:** Generate synthetic competitor data for dry-run mode.

**Params:**
- `competitor_urls` (list[str]): Competitor URLs to use in synthetic data.
- `client_scorecard` (SeoScorecard): Client scorecard (to create plausible comparisons).

**Returns:** `SeoCompetitorAnalysis` with synthetic competitor profiles and gaps.

**Called by:** `run()` in `seo_commands.py` (when `--dry-run`)

**Calls:** None.

---

### 6.7 SEO Report Generator Module (`src/generators/seo_report_generator.py`)

**Purpose:** Generate Swedish SEO analysis reports in Markdown, PDF, and XLSX formats.

---

#### `generate_seo_report(result: SeoAnalysisResult) -> str`

**Purpose:** Generate a complete markdown SEO report in Swedish.

**Params:**
- `result` (SeoAnalysisResult): Complete analysis result.

**Returns:** Markdown string.

**Side effects:** None.

**Called by:** `run()` in `seo_commands.py`

**Calls:** `_summary_section()`, `_scorecard_section()`, `_critical_issues_section()`, `_technical_section()`, `_on_page_section()`, `_content_section()`, `_links_section()`, `_schema_section()`, `_competitor_section()`, `_action_plan_section()`

---

#### `_summary_section(result: SeoAnalysisResult) -> str`

**Purpose:** Generate "Sammanfattning" section — executive summary with overall score and top 3 findings.

**Called by:** `generate_seo_report()`

---

#### `_scorecard_section(scorecard: SeoScorecard) -> str`

**Purpose:** Generate "SEO-poang" section — table with category, score, grade (A-F), issue count.

**Grade mapping:**
- A: 90-100
- B: 80-89
- C: 70-79
- D: 60-69
- E: 50-59
- F: 0-49

**Called by:** `generate_seo_report()`

---

#### `_critical_issues_section(issues: list[SeoIssue]) -> str`

**Purpose:** Generate "Kritiska problem" section — high-severity issues with fix suggestions and impact estimates.

**Called by:** `generate_seo_report()`

---

#### `_technical_section(page: PageSeoData | None, lighthouse: LighthouseResult | None) -> str`

**Purpose:** Generate "Teknisk SEO" section — CWV metrics table, HTTP details, robots.txt status, sitemap status.

**Called by:** `generate_seo_report()`

---

#### `_on_page_section(result: SeoAnalysisResult) -> str`

**Purpose:** Generate "On-page SEO" section — per-page audit table with title, meta desc, H1, canonical status.

**Called by:** `generate_seo_report()`

---

#### `_content_section(result: SeoAnalysisResult) -> str`

**Purpose:** Generate "Innehallsanalys" section — content quality, word counts, thin page list.

**Called by:** `generate_seo_report()`

---

#### `_links_section(result: SeoAnalysisResult) -> str`

**Purpose:** Generate "Lankstruktur" section — internal/external link summary, orphan pages.

**Called by:** `generate_seo_report()`

---

#### `_schema_section(result: SeoAnalysisResult) -> str`

**Purpose:** Generate "Schema & Strukturerad data" section — JSON-LD type listing, recommendations.

**Called by:** `generate_seo_report()`

---

#### `_competitor_section(analysis: SeoCompetitorAnalysis | None) -> str`

**Purpose:** Generate "Konkurrentjamforelse" section — scorecard comparison table and gap list. Returns empty string if no competitor analysis.

**Called by:** `generate_seo_report()`

---

#### `_action_plan_section(issues: list[SeoIssue]) -> str`

**Purpose:** Generate "Handlingsplan" section — prioritized action items sorted by impact/effort ratio.

**Implementation notes:**
- Sort order: High impact + Low effort first (quick wins), then High impact + Medium/High effort, then Medium impact, then Low.
- Each action item formatted as a checklist: `- [ ] {fix_suggestion} — {impact_estimate} (Insats: {effort})`

**Called by:** `generate_seo_report()`

---

#### `export_seo_pdf(result: SeoAnalysisResult, output_path: str) -> str`

**Purpose:** Export SEO report as PDF using existing `pdf_generator.py`.

**Params:**
- `result` (SeoAnalysisResult): Analysis result.
- `output_path` (str): Path for the PDF file.

**Returns:** Output path string.

**Side effects:** Writes PDF file.

**Called by:** `run()` in `seo_commands.py`

**Calls:** `generate_seo_report()`, `pdf_generator.generate_pdf_report()`

---

#### `export_seo_xlsx(result: SeoAnalysisResult, output_path: str) -> str`

**Purpose:** Export SEO data to multi-sheet XLSX workbook.

**Params:**
- `result` (SeoAnalysisResult): Analysis result.
- `output_path` (str): Path for the XLSX file.

**Returns:** Output path string.

**Side effects:** Writes XLSX file.

**Sheets:**
1. **Oversikt** (Overview): Overall score, category scores, grade
2. **Problem** (Issues): All issues with severity, category, fix, impact, effort, affected URLs
3. **Sidor** (Pages): Per-page data — URL, title, title length, meta desc, H1, word count, schema types, internal links count
4. **Konkurrenter** (Competitors): Competitor scores and gaps (if competitor analysis present)

**Called by:** `run()` in `seo_commands.py`

**Calls:** `generate_seo_report()` (for report data), `openpyxl.Workbook()`

---

### 6.8 CLI Commands Module (`src/cli/seo_commands.py`)

**Purpose:** Define the `sem seo` Typer command group. Orchestrates scraping, analysis, and report generation.

---

#### `run(url, mode, competitors, client, output, max_pages, skip_lighthouse, dry_run) -> None`

**Purpose:** Main CLI entry point for SEO analysis. Orchestrates the full pipeline: scrape → analyze → score → compare → report.

**Params (Typer-decorated):**
- `url` (str, Argument): URL to analyze. Required.
- `mode` (str, Option `--mode/-m`): "single" or "site". Default: "single".
- `competitors` (str | None, Option `--competitors/-c`): Comma-separated competitor URLs. Default: None.
- `client` (str | None, Option `--client`): Client name for pipeline integration. Default: None.
- `output` (str, Option `--output/-o`): "markdown", "pdf", or "xlsx". Default: "markdown".
- `max_pages` (int, Option `--max-pages`): Max pages for site crawl. Default: 30.
- `skip_lighthouse` (bool, Option `--skip-lighthouse`): Skip Lighthouse analysis. Default: False.
- `dry_run` (bool, Option `--dry-run`): Use synthetic data. Default: False.

**Returns:** None (CLI command, exits via typer.Exit on error).

**Side effects:**
- Launches browser(s) for scraping.
- Writes report files to disk.
- If `--client` is set, writes to `clients/{name}/seo/` directory.
- Prints progress and summary to console via Rich.

**Error cases:**
- Invalid URL: Print error, exit 1.
- Client not found (if `--client` used): Print error, exit 1.
- Network failures: Print error with suggestion to use `--dry-run`.

**Called by:** Typer CLI framework.

**Calls:** 
- `crawl_seo_single()` or `crawl_seo_site()` or `generate_synthetic_*_data()` (from `seo_scraper.py`)
- `fetch_robots_txt()`, `discover_sitemaps()` (from `robots_sitemap.py`)
- `run_lighthouse()` (from `lighthouse_runner.py`, unless `--skip-lighthouse`)
- `analyze_page_seo()` or `analyze_site_seo()` (from `seo_analyzer.py`)
- `analyze_competitor_seo()` (from `seo_competitor.py`, if `--competitors`)
- `generate_seo_report()`, `export_seo_pdf()`, `export_seo_xlsx()` (from `seo_report_generator.py`)

**Implementation notes:**

Orchestration flow:
```python
# 1. Determine output directory
if client:
    name, client_dir = resolve_client(client)
    output_dir = client_dir / "seo"
else:
    output_dir = Path.cwd()

# 2. Scrape
if dry_run:
    if mode == "site":
        site_data = generate_synthetic_site_data(url)
        page_data = site_data.pages[0] if site_data.pages else None
    else:
        page_data = generate_synthetic_page_data(url)
        site_data = None
else:
    if mode == "site":
        site_data = asyncio.run(crawl_seo_site(url, max_pages=max_pages))
        # Also fetch robots + sitemap
        domain = urlparse(url).netloc
        robots = asyncio.run(fetch_robots_txt(domain))
        sitemaps = asyncio.run(discover_sitemaps(domain, robots))
        site_data.robots_txt = robots
        site_data.sitemaps = sitemaps
        page_data = site_data.pages[0] if site_data.pages else None
    else:
        page_data, http_details = asyncio.run(crawl_seo_single(url))
        # Merge http_details into page_data
        site_data = None

# 3. Lighthouse (optional)
lighthouse = None
if not skip_lighthouse and not dry_run:
    lighthouse = asyncio.run(run_lighthouse(url))

# 4. Analyze
if mode == "site" and site_data:
    scorecard = analyze_site_seo(site_data, lighthouse)
elif page_data:
    scorecard = analyze_page_seo(page_data, lighthouse)

# 5. Competitor comparison (optional)
competitor_analysis = None
if competitors:
    competitor_urls = [u.strip() for u in competitors.split(",")]
    if dry_run:
        competitor_analysis = generate_synthetic_competitor_data(competitor_urls, scorecard)
    else:
        competitor_analysis = asyncio.run(
            analyze_competitor_seo(url, competitor_urls, scorecard, page_data)
        )

# 6. Assemble result
result = SeoAnalysisResult(
    mode=mode,
    analyzed_at=datetime.now(),
    site_data=site_data,
    page_data=page_data,
    lighthouse=lighthouse,
    scorecard=scorecard,
    competitor_analysis=competitor_analysis,
)

# 7. Save JSON
json_path = output_dir / "seo_analysis.json"
json_path.parent.mkdir(parents=True, exist_ok=True)
json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

# 8. Generate report(s)
md_report = generate_seo_report(result)
md_path = output_dir / "seo_report.md"
md_path.write_text(md_report, encoding="utf-8")

if output == "pdf":
    export_seo_pdf(result, str(output_dir / "seo_report.pdf"))
elif output == "xlsx":
    export_seo_xlsx(result, str(output_dir / "seo_report.xlsx"))

# 9. Print summary
```

---

### 6.9 Modification: CLI App Registration (`src/cli/app.py`)

**Change:** Add import and registration of `seo_app`.

**Location in file:** After line 58 (after `report_commands` import), add:
```python
from src.cli.seo_commands import seo_app
```

After line 80 (after `report_app` registration), add:
```python
app.add_typer(seo_app, name="seo", help="SEO-analys — on-page och teknisk SEO.")
```

---

### 6.10 Modification: DigitalPresence Model (`src/models/research.py`)

**Change:** Add optional `seo_data` field.

**Location in file:** `DigitalPresence` class, add new field:
```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.seo import SeoAnalysisResult

class DigitalPresence(BaseModel):
    site_crawl: SiteCrawl | None = None
    google_business: GoogleBusinessProfile | None = None
    reviews: list[Review] = []
    social_profiles: list[SocialProfile] = []
    seo_data: Any | None = None  # SeoAnalysisResult when available
```

**Note:** Use `Any` to avoid circular import. The field is only populated when `clients/{name}/seo/seo_analysis.json` exists and is loaded by pipeline code.

---

## 7. Data Models

All models defined in `src/models/seo.py`. Uses Pydantic v2 `BaseModel`.

### 7.1 Enums

#### `IssueSeverity`

```
Enum(str): "high" | "medium" | "low"
```

#### `IssueCategory`

```
Enum(str): "technical" | "content" | "on_page" | "links" | "schema"
```

### 7.2 Per-Page Scraping Models

#### `MetaTag`

| Field | Type | Constraints |
|-------|------|-------------|
| name | str | Required. The meta tag name/property attribute. |
| content | str | Required. The meta tag content attribute. |

#### `SchemaMarkup`

| Field | Type | Constraints |
|-------|------|-------------|
| schema_type | str | Required. E.g., "LocalBusiness", "Product", "FAQPage". |
| format | Literal["json-ld", "microdata", "rdfa"] | Required. |
| raw_data | dict | Default: {}. Parsed JSON-LD content or extracted microdata key-value pairs. |

#### `ImageAudit`

| Field | Type | Constraints |
|-------|------|-------------|
| src | str | Required. Image source URL. |
| alt | str | Default: "". |
| has_alt | bool | Default: False. True if alt attribute present and non-empty. |
| width | int \| None | Default: None. Natural width in pixels. |
| height | int \| None | Default: None. Natural height in pixels. |
| is_lazy_loaded | bool | Default: False. True if loading="lazy" or data-src present. |

#### `LinkInfo`

| Field | Type | Constraints |
|-------|------|-------------|
| url | str | Required. |
| anchor_text | str | Default: "". |
| is_external | bool | Default: False. |
| is_nofollow | bool | Default: False. |
| status_code | int \| None | Default: None. Populated if link checking is performed. |

#### `PageSeoData`

| Field | Type | Constraints |
|-------|------|-------------|
| url | str | Required. |
| status_code | int | Default: 200. |
| redirect_chain | list[str] | Default: []. |
| title | str | Default: "". |
| title_length | int | Default: 0. Computed from len(title). |
| meta_description | str | Default: "". |
| meta_description_length | int | Default: 0. |
| canonical_url | str \| None | Default: None. |
| is_self_canonical | bool | Default: True. |
| hreflang_tags | list[dict[str, str]] | Default: []. Each dict: {"lang": "sv", "url": "..."}. |
| robots_meta | str | Default: "". E.g., "index, follow". |
| h1 | str | Default: "". |
| h1_count | int | Default: 0. |
| headings | list[dict[str, str]] | Default: []. Each dict: {"tag": "h2", "text": "..."}. |
| heading_hierarchy_valid | bool | Default: True. |
| body_text | str | Default: "". Capped at 50000 chars. |
| word_count | int | Default: 0. |
| images | list[ImageAudit] | Default: []. |
| images_without_alt | int | Default: 0. Computed. |
| internal_links | list[LinkInfo] | Default: []. |
| external_links | list[LinkInfo] | Default: []. |
| schema_markup | list[SchemaMarkup] | Default: []. |
| open_graph | list[MetaTag] | Default: []. |
| twitter_card | list[MetaTag] | Default: []. |
| meta_tags | list[MetaTag] | Default: []. All other meta tags. |
| render_blocking_resources | list[str] | Default: []. CSS/JS URLs. |
| page_load_time_ms | float \| None | Default: None. |
| content_type | str | Default: "". |
| http_headers | dict[str, str] | Default: {}. Selected response headers. |

**Relationships:** Contained within `SiteSeoData.pages`. Referenced by `SeoScorecard.issues[].affected_urls`.

**Common queries:**
- Access by URL: iterate `pages` list (small N, no index needed)
- Filter by issue: via `SeoScorecard.issues[].affected_urls`

### 7.3 Site-Level Models

#### `RobotsTxtData`

| Field | Type | Constraints |
|-------|------|-------------|
| exists | bool | Default: False. |
| allows_crawling | bool | Default: True. |
| sitemap_urls | list[str] | Default: []. |
| disallowed_paths | list[str] | Default: []. |
| raw_content | str | Default: "". |

#### `SitemapData`

| Field | Type | Constraints |
|-------|------|-------------|
| exists | bool | Default: False. |
| url | str | Default: "". |
| page_count | int | Default: 0. |
| urls | list[str] | Default: []. |
| last_modified | str \| None | Default: None. |

#### `SiteSeoData`

| Field | Type | Constraints |
|-------|------|-------------|
| domain | str | Required. |
| crawl_date | datetime | Required. Set at crawl time. |
| pages | list[PageSeoData] | Default: []. |
| robots_txt | RobotsTxtData | Default: RobotsTxtData(). |
| sitemaps | list[SitemapData] | Default: []. |
| total_pages_crawled | int | Default: 0. |
| total_internal_links | int | Default: 0. Computed. |
| total_external_links | int | Default: 0. Computed. |
| orphan_pages | list[str] | Default: []. URLs not linked from any other page. |

**Relationships:** Contains `list[PageSeoData]`. Contains `RobotsTxtData` and `list[SitemapData]`.

### 7.4 Lighthouse Models

#### `CoreWebVitals`

| Field | Type | Constraints |
|-------|------|-------------|
| lcp_ms | float \| None | Default: None. Largest Contentful Paint in ms. |
| fid_ms | float \| None | Default: None. First Input Delay in ms. |
| cls | float \| None | Default: None. Cumulative Layout Shift (unitless). |
| fcp_ms | float \| None | Default: None. First Contentful Paint in ms. |
| ttfb_ms | float \| None | Default: None. Time to First Byte in ms. |
| si_ms | float \| None | Default: None. Speed Index in ms. |
| tbt_ms | float \| None | Default: None. Total Blocking Time in ms. |

#### `LighthouseResult`

| Field | Type | Constraints |
|-------|------|-------------|
| url | str | Default: "". |
| performance_score | float \| None | Default: None. 0-100 scale. |
| accessibility_score | float \| None | Default: None. 0-100 scale. |
| best_practices_score | float \| None | Default: None. 0-100 scale. |
| seo_score | float \| None | Default: None. 0-100 scale. |
| core_web_vitals | CoreWebVitals | Default: CoreWebVitals(). |
| opportunities | list[dict] | Default: []. [{title, description, savings_ms}]. |
| diagnostics | list[dict] | Default: []. [{title, description}]. |

### 7.5 Scoring & Issue Models

#### `SeoIssue`

| Field | Type | Constraints |
|-------|------|-------------|
| category | IssueCategory | Required. |
| severity | IssueSeverity | Required. |
| title | str | Required. Short Swedish description. |
| description | str | Required. Detailed Swedish explanation. |
| affected_urls | list[str] | Default: []. |
| fix_suggestion | str | Required. Specific, implementable fix in Swedish. |
| impact_estimate | str | Required. Concrete expected outcome in Swedish. |
| effort | Literal["low", "medium", "high"] | Default: "low". |

#### `CategoryScore`

| Field | Type | Constraints |
|-------|------|-------------|
| category | IssueCategory | Required. |
| score | float | Required. 0-100. |
| max_score | float | Default: 100.0. |
| issues_found | int | Default: 0. |
| label | str | Default: "". Swedish display label. |

#### `SeoScorecard`

| Field | Type | Constraints |
|-------|------|-------------|
| overall_score | float | Required. 0-100 weighted average. |
| category_scores | list[CategoryScore] | Default: []. |
| issues | list[SeoIssue] | Default: []. |
| summary_sv | str | Default: "". 2-3 sentence Swedish summary. |

### 7.6 Competitor Models

#### `CompetitorSeoProfile`

| Field | Type | Constraints |
|-------|------|-------------|
| url | str | Required. |
| domain | str | Required. |
| scorecard | SeoScorecard | Default: SeoScorecard(overall_score=0). |
| page_data | PageSeoData \| None | Default: None. |
| lighthouse | LighthouseResult \| None | Default: None. |

#### `SeoGap`

| Field | Type | Constraints |
|-------|------|-------------|
| area | str | Required. E.g., "Schema markup", "Sidladdningstid". |
| client_value | str | Required. |
| competitor_value | str | Required. |
| competitor_domain | str | Required. |
| recommendation | str | Required. Actionable fix in Swedish. |

#### `SeoCompetitorAnalysis`

| Field | Type | Constraints |
|-------|------|-------------|
| client_url | str | Required. |
| client_scorecard | SeoScorecard | Required. |
| competitors | list[CompetitorSeoProfile] | Default: []. |
| gaps | list[SeoGap] | Default: []. |
| advantages | list[str] | Default: []. Swedish descriptions. |

### 7.7 Top-Level Result Model

#### `SeoAnalysisResult`

| Field | Type | Constraints |
|-------|------|-------------|
| mode | Literal["single", "site"] | Required. |
| analyzed_at | datetime | Required. |
| site_data | SiteSeoData \| None | Default: None. Populated in site mode. |
| page_data | PageSeoData \| None | Default: None. Populated in single mode (or homepage in site mode). |
| lighthouse | LighthouseResult \| None | Default: None. |
| scorecard | SeoScorecard | Required. |
| competitor_analysis | SeoCompetitorAnalysis \| None | Default: None. |

**Relationships:** Top-level container. Contains all other models.

**Serialization:** `result.model_dump_json(indent=2)` for JSON file output. `SeoAnalysisResult.model_validate_json(json_str)` for loading.

---

## 8. Interface Contracts

### 8.1 CLI Interface (External)

```
COMMAND: sem seo run <url>

Purpose: Run SEO analysis on a URL or website
Auth: None required (no Google Ads API needed)

Arguments:
  url (str, required): URL to analyze

Options:
  --mode/-m (str): "single" | "site". Default: "single"
  --competitors/-c (str): Comma-separated competitor URLs. Default: None
  --client (str): Client name for pipeline storage. Default: None
  --output/-o (str): "markdown" | "pdf" | "xlsx". Default: "markdown"
  --max-pages (int): Max pages for site crawl. Default: 30
  --skip-lighthouse (bool): Skip Lighthouse. Default: False
  --dry-run (bool): Use synthetic data. Default: False

Output:
  Success: Report file(s) written, path printed, summary panel displayed
  Error: Red error message, exit code 1

File outputs (--client mode):
  clients/{name}/seo/seo_analysis.json
  clients/{name}/seo/seo_report.md
  clients/{name}/seo/seo_report.pdf  (if --output pdf)
  clients/{name}/seo/seo_report.xlsx (if --output xlsx)

File outputs (standalone mode):
  ./seo_analysis.json
  ./seo_report.md
  ./seo_report.pdf  (if --output pdf)
  ./seo_report.xlsx (if --output xlsx)

Maps to: seo_commands.run()
```

### 8.2 Internal Module Contracts

#### Contract: Scraper → Analyzer

```
Input: PageSeoData (from seo_scraper) + LighthouseResult (from lighthouse_runner)
Output: SeoScorecard (from seo_analyzer)
Function: analyze_page_seo(page, lighthouse) -> SeoScorecard
Invariant: PageSeoData fields have sensible defaults; analyzer never crashes on empty data.
```

#### Contract: Scraper → Competitor Analyzer

```
Input: client PageSeoData + client SeoScorecard + list of competitor URLs
Output: SeoCompetitorAnalysis
Function: analyze_competitor_seo(client_url, competitor_urls, client_scorecard, client_page)
Invariant: Failed competitor scrapes produce partial results, not exceptions.
```

#### Contract: Analyzer → Report Generator

```
Input: SeoAnalysisResult (aggregates all data)
Output: Markdown string (or PDF/XLSX file)
Function: generate_seo_report(result) -> str
Invariant: Report generator never crashes; missing sections produce "Ej tillganglig" placeholder.
```

#### Contract: CLI → Pipeline (optional)

```
Input: SeoAnalysisResult serialized as JSON
Storage: clients/{name}/seo/seo_analysis.json
Consumer: Any pipeline stage that loads DigitalPresence and checks seo_data field
Invariant: Pipeline stages function identically whether SEO data exists or not.
```

---

## 9. Data Flow Diagrams

### 9.1 Journey 1 — Single Page SEO Audit

```
User: sem seo run https://example.se
  │
  ▼
seo_commands.run(url, mode="single")
  │
  ├──► seo_scraper.crawl_seo_single(url)
  │      ├── Playwright: launch browser
  │      ├── page.goto(url) → capture Response
  │      ├── _check_http_details(page, url) → {status_code, redirect_chain, headers}
  │      ├── extract_page_seo(page, url) → PageSeoData
  │      └── browser.close()
  │      └─► returns (PageSeoData, http_details)
  │
  ├──► lighthouse_runner.run_lighthouse(url)
  │      ├── lighthouse_available() → bool
  │      ├── asyncio.create_subprocess_exec("lighthouse", url, "--output=json", ...)
  │      ├── parse JSON output → LighthouseResult
  │      └─► returns LighthouseResult (or empty if unavailable)
  │
  ├──► seo_analyzer.analyze_page_seo(page_data, lighthouse)
  │      ├── _score_on_page(page) → (score, issues)
  │      ├── _score_technical(page, lighthouse) → (score, issues)
  │      ├── _score_content(page) → (score, issues)
  │      ├── _score_links(page) → (score, issues)
  │      ├── _score_schema(page) → (score, issues)
  │      ├── weighted average → overall_score
  │      └─► returns SeoScorecard
  │
  ├──► Assemble SeoAnalysisResult
  │
  ├──► seo_report_generator.generate_seo_report(result) → markdown string
  │
  ├──► Write seo_analysis.json + seo_report.md
  │
  └──► Console: Rich Panel with score summary
```

### 9.2 Journey 2 — Full Site SEO Audit

```
User: sem seo run https://example.se --mode site --max-pages 30
  │
  ▼
seo_commands.run(url, mode="site", max_pages=30)
  │
  ├──► seo_scraper.crawl_seo_site(url, max_pages=30)
  │      ├── Playwright: launch browser
  │      ├── BFS crawl loop:
  │      │     ├── page.goto(current_url) → Response
  │      │     ├── extract_page_seo(page, url) → PageSeoData
  │      │     ├── Collect internal links → add to queue
  │      │     └── asyncio.sleep(1.5)
  │      ├── Compute orphan_pages
  │      └─► returns SiteSeoData
  │
  ├──► robots_sitemap.fetch_robots_txt(domain) → RobotsTxtData
  ├──► robots_sitemap.discover_sitemaps(domain, robots) → list[SitemapData]
  │
  ├──► lighthouse_runner.run_lighthouse(url)  [homepage only]
  │
  ├──► seo_analyzer.analyze_site_seo(site_data, lighthouse)
  │      ├── For each page: analyze_page_seo(page) → SeoScorecard
  │      ├── Average category scores across pages
  │      ├── _detect_site_level_issues(site) → additional issues
  │      └─► returns aggregated SeoScorecard
  │
  ├──► Assemble SeoAnalysisResult (with site_data)
  ├──► Generate report + write files
  └──► Console output
```

### 9.3 Journey 3 — Competitive SEO Comparison

```
User: sem seo run https://example.se --competitors https://rival1.se,https://rival2.se
  │
  ▼
seo_commands.run(url, competitors="https://rival1.se,https://rival2.se")
  │
  ├──► [Single page or site analysis as in Journey 1/2]
  │     └─► client_scorecard, client_page
  │
  ├──► seo_competitor.analyze_competitor_seo(
  │      client_url, competitor_urls, client_scorecard, client_page)
  │      │
  │      ├── For each competitor URL:
  │      │     ├── seo_scraper.crawl_seo_single(comp_url) → PageSeoData
  │      │     ├── seo_analyzer.analyze_page_seo(comp_page) → SeoScorecard
  │      │     └── Build CompetitorSeoProfile
  │      │
  │      ├── For each competitor:
  │      │     └── _compute_gaps(client, client_score, comp, comp_score) → list[SeoGap]
  │      │
  │      ├── _identify_advantages(client_score, comp_scores) → list[str]
  │      └─► returns SeoCompetitorAnalysis
  │
  ├──► Assemble SeoAnalysisResult (with competitor_analysis)
  ├──► Generate report (includes competitor section)
  └──► Console output
```

### 9.4 Journey 4 — Pipeline Integration

```
User: sem seo run https://example.se --client "klient-ab"
  │
  ▼
seo_commands.run(url, client="klient-ab")
  │
  ├──► stage_helpers.resolve_client("klient-ab") → (name, client_dir)
  │      [If client doesn't exist → error + exit 1]
  │
  ├──► [Full analysis as in Journey 1/2/3]
  │     └─► SeoAnalysisResult
  │
  ├──► Write to clients/klient-ab/seo/:
  │      ├── seo_analysis.json
  │      ├── seo_report.md
  │      └── seo_report.pdf/xlsx (if requested)
  │
  └──► Console: "SEO-analys sparad i clients/klient-ab/seo/"
```

### 9.5 Journey 5 — Dry Run

```
User: sem seo run https://example.se --dry-run
  │
  ▼
seo_commands.run(url, dry_run=True)
  │
  ├──► seo_scraper.generate_synthetic_page_data(url) → PageSeoData
  │      [No network access]
  │
  ├──► seo_analyzer.analyze_page_seo(synthetic_page, None) → SeoScorecard
  │
  ├──► Assemble SeoAnalysisResult
  ├──► Generate report
  └──► Console: "[dim]Dry-run: syntetisk data[/dim]"
```

---

## 10. Dependency Map

### 10.1 Internal Dependencies (module → module)

```
seo_commands.py
  ├── seo_scraper.py
  │     └── models/seo.py (PageSeoData, SiteSeoData)
  ├── robots_sitemap.py
  │     └── models/seo.py (RobotsTxtData, SitemapData)
  ├── lighthouse_runner.py
  │     └── models/seo.py (LighthouseResult, CoreWebVitals)
  ├── seo_analyzer.py
  │     └── models/seo.py (SeoScorecard, SeoIssue, CategoryScore, IssueSeverity, IssueCategory)
  ├── seo_competitor.py
  │     ├── seo_scraper.py (crawl_seo_single)
  │     ├── seo_analyzer.py (analyze_page_seo)
  │     └── models/seo.py (SeoCompetitorAnalysis, CompetitorSeoProfile, SeoGap)
  ├── seo_report_generator.py
  │     ├── models/seo.py (SeoAnalysisResult, all sub-models)
  │     └── generators/pdf_generator.py (generate_pdf_report)
  ├── stage_helpers.py (resolve_client - existing)
  └── models/seo.py (SeoAnalysisResult)

app.py
  └── seo_commands.py (seo_app)

models/research.py
  └── models/seo.py (SeoAnalysisResult - TYPE_CHECKING import only)
```

### 10.2 External Dependencies (packages/services)

| Package | Used By | Purpose | Version |
|---------|---------|---------|---------|
| playwright | seo_scraper.py | Browser automation, DOM extraction | >=1.40 (existing) |
| httpx | robots_sitemap.py | HTTP requests for robots.txt/sitemap | >=0.25 (existing) |
| lxml | robots_sitemap.py | XML parsing for sitemap | >=4.9 (existing) |
| pydantic | models/seo.py | Data validation | >=2.5 (existing) |
| typer | seo_commands.py | CLI framework | >=0.12 (existing) |
| rich | seo_commands.py | Console output | >=13.0 (existing) |
| openpyxl | seo_report_generator.py | XLSX export | >=3.1 (existing) |
| markdown-pdf | seo_report_generator.py (via pdf_generator) | PDF generation | >=1.13 (existing) |
| lighthouse CLI | lighthouse_runner.py | Performance audit | System dep, optional |

---

## 11. Cross-Cutting Concerns

### 11.1 Error Taxonomy

The SEO feature follows the existing project pattern: no custom exception classes. Errors are handled via:

1. **Scraper errors** (network, timeout, parse): Caught within scraper functions, logged via `logging.warning()`, return partial/empty model objects. Never propagate to CLI.
2. **Analysis errors** (unexpected data shape): Defensive coding with defaults. Scoring functions return `(0.0, [])` on error.
3. **CLI errors** (invalid args, missing client): Handled via `typer.Exit(1)` with `console.print("[red]...")`.
4. **Lighthouse errors** (not installed, timeout, crash): Return empty `LighthouseResult`, log advisory.

Error visibility to user:
- **Console output** (via Rich): User-facing error messages in Swedish or English.
- **Log output** (via logging): Technical details for debugging.
- No exceptions should escape to the user as tracebacks — all caught and presented cleanly.

### 11.2 Environment & Configuration

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| ANTHROPIC_API_KEY | No | Not used by SEO feature | - |
| Lighthouse CLI | No | Performance analysis | Graceful skip if missing |

No new environment variables introduced. SEO feature is fully self-contained.

Configuration integration:
- Uses `PROJECT_ROOT`, `CLIENTS_DIR` from existing `src/utils/config.py`.
- No new config entries in `~/.sem-master/config.yaml`.

### 11.3 Naming Conventions

Follows existing project conventions exactly:

| Element | Convention | Examples |
|---------|-----------|----------|
| Python files | snake_case | `seo_scraper.py`, `seo_analyzer.py` |
| Functions | snake_case, verb-first | `analyze_page_seo()`, `fetch_robots_txt()` |
| Private functions | _prefix | `_score_on_page()`, `_detect_site_level_issues()` |
| Classes/Models | PascalCase | `PageSeoData`, `SeoScorecard` |
| Enums | PascalCase class, UPPER values | `IssueSeverity.HIGH` |
| Constants | UPPER_SNAKE | `PIPELINE_STAGES` (not modified) |
| CLI option names | kebab-case | `--skip-lighthouse`, `--max-pages` |
| Test files | test_ prefix | `test_seo_models.py` |
| Client output dirs | kebab-case | `clients/{name}/seo/` |
| Report file names | snake_case | `seo_report.md`, `seo_analysis.json` |

---

## 12. Extensibility Guide

### Adding a New SEO Check

1. Add the check logic to the appropriate `_score_*()` function in `seo_analyzer.py`.
2. Define point allocation and ideal value in the function's scoring table.
3. Create a corresponding `SeoIssue` with Swedish title, description, fix_suggestion, and impact_estimate.
4. Add an entry to `_generate_impact_estimate()` lookup table.
5. If the check needs new scraped data, add a field to `PageSeoData` in `models/seo.py` and extract it in `extract_page_seo()`.
6. Add a test case in `test_seo_analyzer.py`.

### Adding a New Report Section

1. Create a `_new_section(result: SeoAnalysisResult) -> str` function in `seo_report_generator.py`.
2. Add the function call to the `sections` list in `generate_seo_report()`.
3. If the section needs data in XLSX, add a sheet builder in `export_seo_xlsx()`.

### Adding a New Output Format

1. Create an `export_seo_<format>(result, output_path)` function in `seo_report_generator.py`.
2. Add the format as an option in `seo_commands.py` (extend the `--output` Typer option).
3. Add the export call in the CLI orchestration flow.

### Adding Off-Page SEO (Future)

When paid API keys (Ahrefs, Moz) become available:
1. Create `src/scrapers/backlink_scraper.py` with async fetch functions.
2. Add `BacklinkData` model to `models/seo.py`.
3. Add `_score_authority()` function to `seo_analyzer.py` with its own weight.
4. Adjust existing weights (reduce each by proportional amount to make room).
5. Add authority section to report generator.
6. Add `--skip-backlinks` CLI flag.

---

## 13. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Playwright browser launch fails on user's machine | Medium | High | Clear error message with "run `playwright install chromium`" instruction. Test in dry-run mode first. |
| R2 | Lighthouse CLI not installed, user expects performance data | High | Medium | Graceful fallback with advisory message. Documentation explains optional nature and install command. |
| R3 | Target website blocks scraper (bot detection) | Medium | Medium | Use real-ish user agent, respect robots.txt. Log and skip blocked pages. Suggest dry-run for demo. |
| R4 | Large sites (>100 pages) cause memory/time issues | Low | Medium | `max_pages` cap (default 30). 1.5s delay between pages. `body_text` capped at 50K chars per page. |
| R5 | Malformed HTML crashes parsers | Low | Low | All parsing wrapped in try/except. Return partial data on parse failures. |
| R6 | Schema markup in non-JSON-LD formats (microdata, RDFa) harder to parse | Medium | Low | Phase 1 focuses on JSON-LD (95% of modern sites). Microdata/RDFa detected but parsing is best-effort. |
| R7 | Impact estimates are inaccurate / misleading to clients | Medium | Medium | Use conservative ranges. Frame as "uppskattat" (estimated). Include disclaimer in report footer. |
| R8 | Competitor URL returns wildly different content (SPA, auth-gated) | Low | Low | Score with available data. Note in competitor profile if data is limited. |

---

## 14. Implementation Roadmap

### Phase 1: Foundation — Models + Single-Page Scraper

**Goal:** `PageSeoData` model validated and single-page extraction working end-to-end.

**Modules:**
- `src/models/seo.py` — all models (even if not all populated yet)
- `src/scrapers/seo_scraper.py` — `extract_page_seo()`, `crawl_seo_single()`, `generate_synthetic_page_data()`
- `tests/test_seo_models.py` — model validation tests
- `tests/test_seo_scraper.py` — scraper tests (mocked Playwright)

**Dependencies:** None (first phase).

**Definition of done:**
- All Pydantic models defined and pass validation tests
- `crawl_seo_single("https://example.com")` returns populated `PageSeoData`
- `generate_synthetic_page_data()` returns valid `PageSeoData`
- Tests pass: `pytest tests/test_seo_models.py tests/test_seo_scraper.py -v`

---

### Phase 2: Scoring Engine

**Goal:** Given a `PageSeoData`, produce a scored `SeoScorecard` with prioritized Swedish issues.

**Modules:**
- `src/analysis/seo_analyzer.py` — all scoring functions
- `tests/test_seo_analyzer.py`

**Dependencies:** Phase 1 (needs models and scraper output).

**Definition of done:**
- `analyze_page_seo(synthetic_page_data)` returns scored `SeoScorecard`
- All five scoring categories produce scores 0-100
- Issues have Swedish text, fix suggestions, and impact estimates
- Site-level analysis works with multiple pages
- Tests pass: `pytest tests/test_seo_analyzer.py -v`

---

### Phase 3: CLI + Report — Standalone Working

**Goal:** `sem seo run <url>` works end-to-end in single-page mode with markdown output.

**Modules:**
- `src/cli/seo_commands.py` — full CLI command
- `src/generators/seo_report_generator.py` — markdown report generation
- `src/cli/app.py` — registration (modification)
- `tests/test_seo_report.py`

**Dependencies:** Phase 1, Phase 2.

**Definition of done:**
- `sem seo run https://example.com` produces `seo_report.md` in cwd
- `sem seo run https://example.com --dry-run` works without network
- Report contains all 10 sections with Swedish text
- `sem --help` shows `seo` command
- Tests pass: `pytest tests/test_seo_report.py -v`

---

### Phase 4: Site Crawl Mode + robots.txt/Sitemap

**Goal:** `sem seo run <url> --mode site` crawls multiple pages with cross-page analysis.

**Modules:**
- `src/scrapers/seo_scraper.py` — add `crawl_seo_site()`, `generate_synthetic_site_data()`
- `src/scrapers/robots_sitemap.py` — complete module
- `src/analysis/seo_analyzer.py` — add `_detect_site_level_issues()`

**Dependencies:** Phase 1, Phase 2, Phase 3.

**Definition of done:**
- `sem seo run https://example.com --mode site --max-pages 5` crawls and reports
- Orphan pages detected
- Duplicate titles/meta descriptions flagged
- robots.txt and sitemap data included in report
- `--dry-run --mode site` works with synthetic multi-page data

---

### Phase 5: Lighthouse Integration

**Goal:** Core Web Vitals and Lighthouse scores integrated into technical scoring.

**Modules:**
- `src/scrapers/lighthouse_runner.py` — complete module

**Dependencies:** Phase 2 (scoring engine must accept optional Lighthouse data).

**Definition of done:**
- `lighthouse_available()` correctly detects CLI presence
- `run_lighthouse(url)` returns populated `LighthouseResult` when Lighthouse is installed
- Technical score adjusts when Lighthouse data is available
- Graceful fallback: feature works without Lighthouse installed
- Report includes CWV section when data available

**Note:** Can be developed in parallel with Phase 4.

---

### Phase 6: Competitor Comparison

**Goal:** `--competitors` flag produces gap analysis.

**Modules:**
- `src/analysis/seo_competitor.py` — complete module
- `tests/test_seo_competitor.py`

**Dependencies:** Phase 1 (scraper), Phase 2 (analyzer).

**Definition of done:**
- `sem seo run https://example.com --competitors https://rival.com` produces comparison
- Gap analysis identifies specific areas where competitor is stronger
- Advantages section identifies where client is stronger
- Report includes competitor comparison table
- `--dry-run --competitors ...` works with synthetic data
- Tests pass: `pytest tests/test_seo_competitor.py -v`

**Note:** Can be developed in parallel with Phases 4-5.

---

### Phase 7: Exports + Pipeline Integration + Polish

**Goal:** PDF/XLSX export, `--client` flag, skill definition, documentation updates.

**Modules:**
- `src/generators/seo_report_generator.py` — add `export_seo_pdf()`, `export_seo_xlsx()`
- `src/models/research.py` — add `seo_data` field to `DigitalPresence`
- `~/.claude/skills/sem-seo/SKILL.md` — skill definition
- `CLAUDE.md` — add `sem seo` commands

**Dependencies:** All previous phases.

**Definition of done:**
- `sem seo run <url> --output pdf` produces PDF file
- `sem seo run <url> --output xlsx` produces multi-sheet XLSX
- `sem seo run <url> --client "test"` stores in `clients/test/seo/`
- `DigitalPresence.seo_data` accepts `SeoAnalysisResult`
- `sem-seo` skill triggers correctly in Claude Code
- `CLAUDE.md` documents the new command
- All existing tests still pass: `pytest tests/ -v`

### Parallelism Opportunities

```
Phase 1 (Foundation)
  │
  ▼
Phase 2 (Scoring Engine)
  │
  ├──────────────────────┐
  ▼                      ▼
Phase 3 (CLI+Report)   Phase 5 (Lighthouse)  Phase 6 (Competitors)
  │                      │                     │
  ▼                      │                     │
Phase 4 (Site Crawl)    │                     │
  │                      │                     │
  └──────────────────────┴─────────────────────┘
                         │
                         ▼
                  Phase 7 (Polish)
```

Phases 5 and 6 can run in parallel with Phases 3-4 since they only depend on Phase 1-2 outputs.

---

## 15. Build Verification Checklist

### Module: `src/models/seo.py`
- [ ] `IssueSeverity` enum — has values: high, medium, low
- [ ] `IssueCategory` enum — has values: technical, content, on_page, links, schema
- [ ] `MetaTag` — fields: name (str), content (str)
- [ ] `SchemaMarkup` — fields: schema_type, format (Literal), raw_data (dict)
- [ ] `ImageAudit` — fields: src, alt, has_alt, width, height, is_lazy_loaded
- [ ] `LinkInfo` — fields: url, anchor_text, is_external, is_nofollow, status_code
- [ ] `PageSeoData` — all 28 fields defined with correct types and defaults
- [ ] `RobotsTxtData` — fields: exists, allows_crawling, sitemap_urls, disallowed_paths, raw_content
- [ ] `SitemapData` — fields: exists, url, page_count, urls, last_modified
- [ ] `SiteSeoData` — fields: domain, crawl_date, pages, robots_txt, sitemaps, total_pages_crawled, orphan_pages
- [ ] `CoreWebVitals` — fields: lcp_ms, fid_ms, cls, fcp_ms, ttfb_ms, si_ms, tbt_ms
- [ ] `LighthouseResult` — fields: url, 4 scores, core_web_vitals, opportunities, diagnostics
- [ ] `SeoIssue` — fields: category, severity, title, description, affected_urls, fix_suggestion, impact_estimate, effort
- [ ] `CategoryScore` — fields: category, score, max_score, issues_found, label
- [ ] `SeoScorecard` — fields: overall_score, category_scores, issues, summary_sv
- [ ] `CompetitorSeoProfile` — fields: url, domain, scorecard, page_data, lighthouse
- [ ] `SeoGap` — fields: area, client_value, competitor_value, competitor_domain, recommendation
- [ ] `SeoCompetitorAnalysis` — fields: client_url, client_scorecard, competitors, gaps, advantages
- [ ] `SeoAnalysisResult` — fields: mode, analyzed_at, site_data, page_data, lighthouse, scorecard, competitor_analysis
- [ ] All models serialize to JSON via `model_dump_json()` and deserialize via `model_validate_json()`

### Module: `src/scrapers/seo_scraper.py`
- [ ] `extract_page_seo(page, url)` — returns populated `PageSeoData`
- [ ] `extract_page_seo` — extracts JSON-LD schema markup
- [ ] `extract_page_seo` — extracts canonical tag
- [ ] `extract_page_seo` — extracts hreflang tags
- [ ] `extract_page_seo` — extracts OG and Twitter Card tags
- [ ] `extract_page_seo` — extracts image alt text audit data
- [ ] `extract_page_seo` — extracts internal/external links with anchor text
- [ ] `extract_page_seo` — detects render-blocking resources
- [ ] `extract_page_seo` — validates heading hierarchy
- [ ] `extract_page_seo` — handles malformed DOM without crashing
- [ ] `_check_http_details(page, url)` — returns status_code, redirect_chain, headers
- [ ] `crawl_seo_single(url)` — launches browser, extracts data, closes browser
- [ ] `crawl_seo_single` — handles unreachable URL gracefully
- [ ] `crawl_seo_single` — handles page load timeout
- [ ] `crawl_seo_site(url, max_pages)` — crawls BFS up to max_pages
- [ ] `crawl_seo_site` — computes orphan_pages
- [ ] `crawl_seo_site` — respects 1.5s delay between pages
- [ ] `crawl_seo_site` — skips failed pages and continues
- [ ] `generate_synthetic_page_data(url)` — returns valid `PageSeoData`
- [ ] `generate_synthetic_site_data(url)` — returns valid `SiteSeoData`

### Module: `src/scrapers/robots_sitemap.py`
- [ ] `fetch_robots_txt(domain)` — returns `RobotsTxtData`
- [ ] `fetch_robots_txt` — handles 404 (exists=False)
- [ ] `fetch_robots_txt` — handles connection error
- [ ] `fetch_robots_txt` — extracts Sitemap directives
- [ ] `fetch_robots_txt` — detects Disallow: /
- [ ] `fetch_sitemap(url)` — returns `SitemapData`
- [ ] `fetch_sitemap` — handles sitemap index files
- [ ] `fetch_sitemap` — limits child sitemaps to 5
- [ ] `fetch_sitemap` — handles invalid XML
- [ ] `discover_sitemaps(domain, robots)` — tries robots.txt URLs then common paths
- [ ] `discover_sitemaps` — deduplicates by URL

### Module: `src/scrapers/lighthouse_runner.py`
- [ ] `lighthouse_available()` — correctly detects CLI presence
- [ ] `run_lighthouse(url)` — returns populated `LighthouseResult` when available
- [ ] `run_lighthouse` — returns empty `LighthouseResult` when CLI not installed
- [ ] `run_lighthouse` — handles process timeout (60s)
- [ ] `run_lighthouse` — handles process crash
- [ ] `run_lighthouse` — parses all 4 category scores
- [ ] `run_lighthouse` — parses all CWV metrics
- [ ] `run_lighthouse` — cleans up temp files

### Module: `src/analysis/seo_analyzer.py`
- [ ] `analyze_page_seo(page, lighthouse)` — returns `SeoScorecard` with 0-100 score
- [ ] `analyze_page_seo` — weighted calculation: on_page*0.30 + technical*0.25 + content*0.20 + links*0.15 + schema*0.10
- [ ] `analyze_page_seo` — generates Swedish summary_sv
- [ ] `analyze_site_seo(site, lighthouse)` — averages per-page scores
- [ ] `analyze_site_seo` — adds site-level issues
- [ ] `_score_on_page` — checks: title present, title length, meta desc, H1, heading hierarchy, canonical, OG, Twitter
- [ ] `_score_on_page` — all issues have Swedish title, description, fix_suggestion, impact_estimate
- [ ] `_score_technical` — checks: status code, redirects, HTTPS, LCP, CLS, TBT, render-blocking, robots meta
- [ ] `_score_technical` — rescales when Lighthouse unavailable
- [ ] `_score_content` — checks: word count thresholds, images present, images alt text
- [ ] `_score_links` — checks: internal links, external links, broken links, orphan pages
- [ ] `_score_schema` — checks: JSON-LD present, type appropriate, required fields
- [ ] `_detect_site_level_issues` — checks: duplicate titles, duplicate meta, orphan pages, missing robots.txt, missing sitemap
- [ ] `_generate_impact_estimate` — returns Swedish impact string for each issue type
- [ ] All scoring functions handle empty/minimal data without crashing

### Module: `src/analysis/seo_competitor.py`
- [ ] `analyze_competitor_seo(client_url, competitor_urls, client_scorecard, client_page)` — returns `SeoCompetitorAnalysis`
- [ ] `analyze_competitor_seo` — handles unreachable competitor URLs
- [ ] `_compute_gaps(client, client_score, competitor, competitor_score)` — returns list of `SeoGap`
- [ ] `_compute_gaps` — compares schema, content, speed, links, images, meta, headings
- [ ] `_compute_gaps` — each gap has Swedish recommendation
- [ ] `_identify_advantages(client_score, competitor_scores)` — returns Swedish advantage strings
- [ ] `generate_synthetic_competitor_data` — returns valid `SeoCompetitorAnalysis`

### Module: `src/generators/seo_report_generator.py`
- [ ] `generate_seo_report(result)` — returns complete markdown string
- [ ] Report contains section: Sammanfattning
- [ ] Report contains section: SEO-poang (scorecard table)
- [ ] Report contains section: Kritiska problem
- [ ] Report contains section: Teknisk SEO
- [ ] Report contains section: On-page SEO
- [ ] Report contains section: Innehallsanalys
- [ ] Report contains section: Lankstruktur
- [ ] Report contains section: Schema & Strukturerad data
- [ ] Report contains section: Konkurrentjamforelse (conditional)
- [ ] Report contains section: Handlingsplan (sorted by impact/effort)
- [ ] `_scorecard_section` — grade mapping A-F correct
- [ ] `_action_plan_section` — quick wins sorted first
- [ ] `export_seo_pdf(result, path)` — produces valid PDF file
- [ ] `export_seo_xlsx(result, path)` — produces XLSX with 4 sheets
- [ ] XLSX sheets: Oversikt, Problem, Sidor, Konkurrenter
- [ ] Report handles missing sections gracefully (no competitor analysis → section omitted)

### Module: `src/cli/seo_commands.py`
- [ ] `sem seo run <url>` — produces markdown report (single page mode)
- [ ] `sem seo run <url> --mode site` — crawls site
- [ ] `sem seo run <url> --competitors url1,url2` — includes competitor analysis
- [ ] `sem seo run <url> --client "name"` — stores in client directory
- [ ] `sem seo run <url> --output pdf` — produces PDF
- [ ] `sem seo run <url> --output xlsx` — produces XLSX
- [ ] `sem seo run <url> --skip-lighthouse` — skips Lighthouse
- [ ] `sem seo run <url> --dry-run` — uses synthetic data
- [ ] `sem seo run <url> --dry-run --mode site` — synthetic site data
- [ ] `sem seo run <url> --dry-run --competitors url1` — synthetic competitor data
- [ ] Invalid URL → error message + exit 1
- [ ] Missing client → error message + exit 1
- [ ] Writes `seo_analysis.json` alongside report

### Module: `src/cli/app.py` (modification)
- [ ] `seo_app` imported and registered
- [ ] `sem --help` shows `seo` command with Swedish help text
- [ ] Existing commands unchanged

### Module: `src/models/research.py` (modification)
- [ ] `DigitalPresence.seo_data` field added (optional, default None)
- [ ] Existing models unchanged
- [ ] Existing tests still pass

### Data Flows
- [ ] Journey 1 (Single page audit) — happy path works end-to-end
- [ ] Journey 1 — error: unreachable URL handled
- [ ] Journey 2 (Site crawl) — happy path with 5+ pages
- [ ] Journey 2 — site with 0 crawlable pages handled
- [ ] Journey 3 (Competitor comparison) — happy path with 2 competitors
- [ ] Journey 3 — error: one competitor unreachable, analysis continues with others
- [ ] Journey 4 (Pipeline integration) — files stored in correct client directory
- [ ] Journey 5 (Dry run) — all modes work without network

### Integration
- [ ] Existing test suite passes: `pytest tests/ -v`
- [ ] No modifications to existing scraper, analyzer, or generator modules
- [ ] `CLAUDE.md` updated with `sem seo run` documentation
- [ ] `sem-seo` skill file created at `~/.claude/skills/sem-seo/SKILL.md`
