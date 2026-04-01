# State

## Project Reference

**Core value:** Automate the entire Google Ads campaign creation pipeline for a solo SEM consultant
**Current milestone:** v2.0 - OAuth CLI Rework

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-04-01 — Milestone v2.0 started

## Performance Metrics

- Phases completed: 0/6
- Requirements completed: 0/TBD
- Tests passing: 37/37

## Accumulated Context

- Review model uses `review_date` field (not `date`) to avoid shadowing
- CSV export produces 7 per-entity-type files (UTF-8 BOM)
- Swedish data files use proper diacritics (å, ä, ö)
- Compound splitter uses simplemma dictionary-based approach
- pyenchant Swedish dict not available on Windows; simplemma handles it
- PDF generation via markdown-pdf library
- industry_keywords.json keys now use Swedish chars (tandvård, advokatbyrå, etc.)
- ARCHITECTURE.md contains full v2.0 blueprint with function signatures and verification checklist
- spacy listed in deps but unused — to be removed in v2.0
- Google Ads API client is currently a stub — real implementation in v2.0

## Decisions

- Removed fabricated Row Type column from CSV export
- Extensions (sitelinks/callouts) applied to ALL campaigns during export
- Swedish section headers in reports (Sammanfattning, Kampanjstruktur, etc.)
- simplemma for compound splitting (pyenchant optional on Windows)
- markdown-pdf for PDF generation (AGPL license, acceptable for tool use)

## Blockers

None

## Next Steps

- Define v2.0 requirements
- Create roadmap from ARCHITECTURE.md phases
- Begin Phase 6: Config & Account Management
