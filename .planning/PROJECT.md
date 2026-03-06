# SEM Master

**Core value:** Automate Google Ads campaign creation for Swedish/Nordic clients - from intake to Google Ads Editor CSV export.

## Current Milestone: v0.2.0 - Polish & Verify

**Goal:** Fix data quality issues, improve Swedish NLP, verify all export formats, add tests and git infrastructure.

**Target features:**
- Fix Swedish diacritics in all data files (proper å, ä, ö characters)
- Improve compound word splitting algorithm
- Verify and fix Google Ads Editor CSV export format
- Verify and fix PDF report generation
- Initialize git repository with proper structure
- Add test suite with smoke tests
- Create JSON validation schemas
- End-to-end pipeline smoke test

## Validated (v0.1.0 - Initial Build)

- Pydantic v2 data models with Swedish ad character validation (30/90 char limits)
- 5 scrapers: site crawler, GBP, reviews, social, transparency center
- 3 API clients: Google Ads Keyword Planner, SpyFu, ValueSERP
- 3 analysis modules: brand, site, competitor
- 5 generators: keywords, ad copy, campaign builder, CSV exporter, reports
- 3 utils: config, Swedish NLP, PDF reader
- Swedish data: stopwords, negative keywords, CTAs, ad patterns, 10 industry verticals
- 7 Google Ads Editor CSV templates
- Report markdown template
- 7 Claude Code skills (sem-master through sem-report)

## Tech Stack

- Python 3.11+, Pydantic v2, Playwright, httpx, BeautifulSoup4
- pandas, openpyxl (exports), pypdf (document reading), spaCy (NLP)
- Claude Code skills as interface layer

---
*Last updated: 2026-03-06*
