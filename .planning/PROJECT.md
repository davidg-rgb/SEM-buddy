# SEM Master

## What This Is

A terminal-based Google Ads campaign automation tool for a solo SEM consultancy serving Swedish/Nordic clients. Takes client inputs, generates complete campaigns (keywords, ad copy, structure), and outputs strategic reports + Google Ads Editor CSV files. Operated by a single consultant managing multiple client accounts via MCC.

## Core Value

Automate the entire Google Ads campaign creation pipeline — from client intake to export-ready CSV — so a solo SEM consultant can deliver agency-quality campaigns at scale.

## Current Milestone: v2.0 - OAuth CLI Rework

**Goal:** Rework from API-key prototype to production CLI tool with Google Ads OAuth 2.0, MCC multi-client management, Typer CLI, campaign templates, and audit mode.

**Target features:**
- Google Ads OAuth 2.0 authentication (desktop flow, MCC pattern)
- Secure token storage (keyring + Fernet fallback)
- Multi-client account management with Google Ads Customer ID binding
- Typer CLI (`sem` command) with subcommands for all pipeline stages
- Dry-run mode for demos/pitches without API credentials
- Campaign template system (save/load winning structures)
- Audit mode (pull live data, diff against recommendations)
- Google Ads API client rewrite using official SDK
- Pipeline state management per client

## Requirements

### Validated (v0.1.0 + v0.2.0)

- Pydantic v2 data models with Swedish ad character validation (30/90 char limits)
- 5 scrapers: site crawler, GBP, reviews, social, transparency center
- 3 API clients: Google Ads Keyword Planner (stub), SpyFu, ValueSERP
- 3 analysis modules: brand, site, competitor
- 5 generators: keywords, ad copy, campaign builder, CSV exporter, reports
- Swedish NLP: compound splitting (simplemma), diacritics variants, stopwords
- Swedish data: stopwords, negative keywords, CTAs, ad patterns, 10 industry verticals
- 7 Google Ads Editor CSV files (UTF-8 BOM), PDF reports, XLSX keyword export
- 11-check campaign validator
- 37 tests passing (models, NLP, CSV, data files, integration)
- Git infrastructure with proper .gitignore

### Active

- [ ] OAuth 2.0 authentication for Google Ads API
- [ ] Secure credential storage and token refresh
- [ ] MCC multi-client account management
- [ ] Typer CLI with `sem` command entry point
- [ ] Per-client pipeline state tracking
- [ ] Dry-run mode (synthetic data, no API credentials needed)
- [ ] Campaign template system
- [ ] Live campaign audit mode
- [ ] Google Ads API client using official SDK

### Out of Scope

- Multi-user auth/permissions — sole operator is superuser
- Web UI / dashboard — terminal/CLI only
- Direct campaign upload to Google Ads — export CSVs for Google Ads Editor
- Database backend — file-based storage sufficient for solo use
- CI/CD pipeline — local development only for now
- Multi-language support — Swedish only

## Context

- Solo SEM consultancy tool — one operator, multiple clients
- Currently manages one Google Ads account, architecting for multiple under MCC
- All ad copy and client-facing output in Swedish
- v0.2.0 complete: all core generators, scrapers, exporters working
- Google Ads API client is currently a stub (NotImplementedError) — needs real OAuth implementation
- ARCHITECTURE.md contains full blueprint with function signatures, data models, CLI command tree
- simplemma handles Swedish compound splitting (pyenchant unavailable on Windows)

## Constraints

- **Platform**: Windows 11 primary, bash shell (Git Bash)
- **Python**: 3.11+
- **Google Ads API**: Requires approved developer token (Basic access) — may delay live testing
- **Character limits**: Headlines ≤30, descriptions ≤90, paths ≤15, sitelinks ≤25 (Pydantic enforced)
- **CSV encoding**: UTF-8 BOM for Excel compatibility
- **Swedish market**: Geo ID 2752, Language ID 1053

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Typer for CLI framework | Type-hint-driven, auto-help, rich integration, less boilerplate than Click | — Pending |
| google-ads SDK (official) | Native GAQL, MCC traversal, OAuth token refresh built-in | — Pending |
| OAuth Desktop flow | Standard for CLI tools, no persistent server, Google Ads API supported | — Pending |
| keyring + Fernet fallback | OS-native credential storage with portable fallback | — Pending |
| YAML for config | Supports comments, nested structures, readable for operator config | — Pending |
| Modular monolith | Single operator, single machine, shared Pydantic models, easy to test | — Pending |
| simplemma for NLP | pyenchant unavailable on Windows, simplemma handles compound splitting | ✓ Good |
| markdown-pdf for reports | AGPL license acceptable for tool use, Swedish char support | ✓ Good |
| review_date field naming | Avoids shadowing Python's date type | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-01 after milestone v2.0 started*
