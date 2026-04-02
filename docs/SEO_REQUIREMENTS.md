# SEO Analysis Feature — Requirements Document

## 1. Purpose

Extend SEM Master with comprehensive SEO analysis capabilities. Given a URL, the system scrapes all accessible SEO-relevant data, runs it through a multi-category scoring engine, compares against competitors, and produces a prioritized list of implementable suggestions with estimated impact.

## 2. User Stories

1. **As a consultant**, I want to run `sem seo run <url>` and get a full on-page + technical SEO audit of a single page, so I can present actionable findings to my client.
2. **As a consultant**, I want to run `sem seo run <url> --mode site` to crawl an entire website and get site-wide SEO health metrics, cross-page issues (duplicate titles, orphan pages), and a prioritized fix list.
3. **As a consultant**, I want to compare a client's site against competitor URLs (`--competitors url1,url2`) and see exactly where competitors are stronger, so I can recommend specific improvements.
4. **As a consultant**, I want SEO findings to feed into the existing SEM pipeline (`--client <name>`) so keyword research and campaign strategy benefit from SEO insights.
5. **As a consultant**, I want output in multiple formats (Markdown, PDF, XLSX) for different delivery contexts.
6. **As a consultant**, I want all output in Swedish since my clients are Swedish businesses.
7. **As a consultant**, I want a dry-run mode that works without network access for testing and demos.

## 3. Functional Requirements

### 3.1 Data Collection (Scraping)

#### 3.1.1 On-Page SEO Data (per page)
- **Title tag**: text, character length
- **Meta description**: text, character length
- **Canonical URL**: present/absent, self-referencing or not
- **Hreflang tags**: all lang/url pairs
- **Robots meta tag**: index/noindex, follow/nofollow directives
- **H1 tag**: text, count (should be exactly 1)
- **Heading hierarchy**: all h1-h6 with tag level and text, validate proper nesting
- **Body text**: full text content, word count
- **Images**: src, alt text (present/absent/descriptive), dimensions, lazy loading status
- **Internal links**: URL, anchor text, nofollow status
- **External links**: URL, anchor text, nofollow status
- **Schema markup**: all JSON-LD scripts (parsed), microdata, RDFa — extract type and key fields
- **Open Graph tags**: og:title, og:description, og:image, og:url, og:type
- **Twitter Card tags**: twitter:card, twitter:title, twitter:description, twitter:image
- **All other meta tags**: viewport, charset, etc.
- **Render-blocking resources**: CSS/JS files that block initial render
- **HTTP response**: status code, redirect chain, content-type, cache headers, x-robots-tag

#### 3.1.2 Site-Level Data
- **robots.txt**: exists, allows crawling, sitemap references, disallowed paths, raw content
- **sitemap.xml**: exists, URL count, last modified, discover via robots.txt + common paths
- **Internal link graph**: which pages link to which, identify orphan pages (not linked from any other page)
- **Cross-page metrics**: total pages crawled, total internal/external links

#### 3.1.3 Performance Data (Lighthouse)
- **Lighthouse scores**: Performance, Accessibility, Best Practices, SEO (0-100 each)
- **Core Web Vitals**: LCP (ms), FID (ms), CLS, FCP (ms), TTFB (ms), Speed Index (ms), TBT (ms)
- **Opportunities**: list of performance improvement suggestions with estimated savings
- **Diagnostics**: list of diagnostic findings
- **Requirement**: Lighthouse CLI must be installed (`npm install -g lighthouse`). If not available, this section is skipped gracefully with an advisory message.

### 3.2 Analysis & Scoring

#### 3.2.1 Scoring Categories

Five categories, each scored 0-100, weighted into an overall score:

| Category | Weight | What It Measures |
|----------|--------|-----------------|
| On-page (On-page) | 30% | Title optimization (50-60 chars ideal), meta description (120-160 chars), H1 presence/uniqueness, heading hierarchy, canonical correctness, OG/Twitter tags |
| Technical (Teknisk) | 25% | HTTP status codes, CWV thresholds (LCP <2.5s, CLS <0.1, FID <100ms), TTFB, render-blocking count, robots.txt correctness, sitemap presence, HTTPS |
| Content (Innehall) | 20% | Word count thresholds (300+ acceptable, 800+ good, 1500+ excellent), thin content detection, content-to-HTML ratio |
| Links (Lankar) | 15% | Internal links per page (3+ recommended), orphan page count, broken links, external link presence, anchor text quality |
| Schema (Strukturerad data) | 10% | JSON-LD presence, schema type appropriateness for business type, required field completeness |

#### 3.2.2 Issue Detection

Each issue must include:
- **Category**: which of the 5 categories it belongs to
- **Severity**: High / Medium / Low
- **Title**: short Swedish description (e.g., "Saknar meta-beskrivning")
- **Description**: detailed Swedish explanation of the problem
- **Affected URLs**: which pages have this issue
- **Fix suggestion**: specific, implementable instruction (not vague advice)
- **Impact estimate**: concrete expected outcome (e.g., "Uppskattat +15-25% CTR i sokresultat")
- **Effort**: Low / Medium / High (implementation difficulty)

#### 3.2.3 Issue Examples

| Severity | Issue | Fix | Impact |
|----------|-------|-----|--------|
| High | Saknar meta-beskrivning (12 sidor) | Skriv unika meta-beskrivningar (120-160 tecken) med huvudsokord och CTA for varje sida | Uppskattat +15-25% CTR i Googles sokresultat |
| High | LCP > 4 sekunder | Optimera hero-bilden: konvertera till WebP, max 200KB, ange width/height-attribut | Kan forbattra ranking — Google prioriterar sidor med LCP under 2.5s |
| High | Saknar H1-tagg (5 sidor) | Lagg till en unik H1 per sida som innehaller sidans huvudsokord | Hjalper Google forsta sidans amne, forbattrar relevansranking |
| Medium | Saknar schema markup | Lagg till LocalBusiness JSON-LD med namn, adress, telefon, oppettider | Mojliggor rich snippets, uppskattat +20% synlighet i SERP |
| Medium | Duplicerade title-taggar (3 sidor) | Skriv unika, beskrivande titlar (50-60 tecken) for varje sida | Undviker kannibalisering, forbattrar CTR for varje sida |
| Medium | 8 bilder saknar alt-text | Lagg till beskrivande alt-text med relevanta sokord | Forbattrar tillganglighet och bildsokning |
| Low | Saknar Twitter Card-taggar | Lagg till twitter:card, twitter:title, twitter:description, twitter:image | Forbattrar delningsutseende pa sociala medier |
| Low | 2 CSS-filer blockerar rendering | Flytta icke-kritisk CSS till async-laddning eller inline kritisk CSS | Kan forbattra FCP med 200-500ms |

### 3.3 Competitor Comparison

When competitor URLs are provided:
- Scrape each competitor page/site with the same SEO checks
- Score each competitor using the same scoring engine
- Produce a **gap analysis**: areas where any competitor scores higher than the client
- Produce an **advantages list**: areas where the client outperforms all competitors
- Each gap must include: area name, client's value, competitor's value, competitor domain, actionable recommendation in Swedish

### 3.4 Report Generation

#### 3.4.1 Report Sections (all in Swedish)
1. **Sammanfattning** — Executive summary with overall score, top 3 findings
2. **SEO-poang** — Scorecard table: category, score (0-100), grade (A-F), issue count
3. **Kritiska problem** — High-severity issues with fixes and impact
4. **Teknisk SEO** — CWV metrics, performance details, robots.txt, sitemap status
5. **On-page SEO** — Title/meta/heading audit per page (table format)
6. **Innehallsanalys** — Content quality, word counts, thin pages
7. **Lankstruktur** — Internal/external link summary, orphan pages
8. **Schema & Strukturerad data** — JSON-LD audit, recommended schema types
9. **Konkurrentjamforelse** — Competitor scorecard comparison + gap table (if competitors provided)
10. **Handlingsplan** — Prioritized action items sorted by impact/effort ratio (quick wins first)

#### 3.4.2 Output Formats
- **Markdown** (.md) — default, always generated
- **PDF** (.pdf) — via existing markdown-pdf pipeline
- **XLSX** (.xlsx) — structured data export with sheets: Scorecard, Issues, Pages, Competitors

### 3.5 CLI Interface

```
sem seo run <url>                                         # Single page analysis
sem seo run <url> --mode site                             # Full site crawl (default max 30 pages)
sem seo run <url> --mode site --max-pages 50              # Custom page limit
sem seo run <url> --competitors https://a.se,https://b.se # With competitor comparison
sem seo run <url> --client "klient-ab"                    # Store in client directory, feed SEM pipeline
sem seo run <url> --output pdf                            # PDF output (markdown always generated too)
sem seo run <url> --output xlsx                           # XLSX output
sem seo run <url> --skip-lighthouse                       # Skip Lighthouse performance analysis
sem seo run <url> --dry-run                               # Synthetic data, no network access
```

### 3.6 Pipeline Integration

- SEO is an **optional side-stage**, not a mandatory pipeline stage
- When `--client <name>` is used, results are stored in `clients/{name}/seo/`:
  - `seo_analysis.json` — full structured data
  - `seo_report.md` — Markdown report
  - `seo_report.pdf` / `seo_report.xlsx` — if those formats were requested
- The `DigitalPresence` model gains an optional `seo_data` field
- The existing `site_analyzer.py` can optionally consume SEO data to enrich its output
- SEO does NOT block or modify the existing 8-stage SEM pipeline

### 3.7 Dry-Run Mode

- Returns synthetic/example data for all scraper outputs
- Exercises the full analysis → scoring → report pipeline
- No network access required
- Useful for testing, demos, and development

## 4. Non-Functional Requirements

### 4.1 Language
- All client-facing output (issues, suggestions, reports) in **Swedish**
- All internal code (variable names, docstrings, comments) in **English**

### 4.2 Dependencies
- **No new Python packages** — reuse existing: Playwright, httpx, BeautifulSoup, lxml, Pydantic v2, openpyxl, typer, rich
- **Lighthouse CLI** — system-level dependency, optional (graceful fallback)

### 4.3 Performance
- Single page analysis: target < 30 seconds
- Site crawl (30 pages): target < 5 minutes (1.5s delay between pages, matching existing crawler)
- Competitor analysis adds one single-page analysis per competitor URL

### 4.4 Error Handling
- Unreachable pages: log warning, skip, continue with available data
- Malformed HTML: parse what's available, don't crash
- Missing Lighthouse: skip performance scoring, include advisory in report
- Timeout: 15s per page (matching existing crawler), configurable

### 4.5 Data Validation
- All data passes through Pydantic v2 models
- Scoring functions are pure (no side effects) for testability
- All scraper functions are async

## 5. Architecture Constraints

- Follow existing project patterns: async scrapers, Pydantic models, function-based analysis, Typer CLI
- Separate SEO scraper from existing site_crawler.py (don't modify existing scraper)
- SEO as optional capability, not mandatory pipeline stage
- Models, scrapers, analyzers, generators, CLI commands each in their own files following existing directory structure

## 6. Skill Integration

New `sem-seo` skill at `~/.claude/skills/sem-seo/SKILL.md`:
- Triggers on: "SEO audit", "SEO analys", "teknisk SEO", "on-page SEO", "competitor SEO", "seo-analys"
- Orchestrates the full SEO workflow via Claude Code
- Documents all CLI flags and output formats

## 7. Success Criteria

1. `sem seo run <url>` produces a scored SEO report for any publicly accessible URL
2. `sem seo run <url> --mode site` crawls and audits up to 30 pages with cross-page analysis
3. `sem seo run <url> --competitors <urls>` produces gap analysis
4. All issues have specific, implementable Swedish fix suggestions with impact estimates
5. `--client` flag stores results and makes them available to the SEM pipeline
6. `--dry-run` works without network access
7. All new code has test coverage
8. No existing tests break
