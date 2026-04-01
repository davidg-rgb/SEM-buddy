---
phase: 11-testing-polish
plan: "03"
subsystem: docs-deps
tags: [documentation, dependencies, testing, cleanup]
dependency_graph:
  requires: []
  provides: [updated-claude-md, cleaned-env-example, dep-hygiene-test]
  affects: [developer-onboarding, ci-hygiene]
tech_stack:
  added: []
  patterns: [dependency-hygiene-test]
key_files:
  created:
    - tests/test_deps.py
  modified:
    - CLAUDE.md
    - .env.example
decisions:
  - "CLAUDE.md reflects v2.0 architecture with OAuth CLI, not v0.2.0 API-key approach"
  - ".env.example removes all OAuth-managed fields; only developer token and optional 3rd-party keys remain"
  - "test_deps.py uses simple file read assertions — no imports of src modules, no external deps"
metrics:
  duration: "107s"
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_changed: 3
---

# Phase 11 Plan 03: Documentation and Dependency Hygiene Summary

**One-liner:** Updated CLAUDE.md to v2.0 OAuth CLI architecture, cleaned .env.example, and added spacy/pyenchant absence verification tests.

## What Was Done

### Task 1: Update CLAUDE.md for v2.0

Rewrote `CLAUDE.md` from the v0.2.0 prototype instructions to reflect the fully-built v2.0 architecture:

- Project structure updated to include `auth/`, `accounts/`, `cli/`, `templates/`, `audit/` modules
- All 14 CLI command groups documented (`sem config`, `sem accounts`, `sem auth`, `sem pipeline`, `sem templates`, `sem audit`, etc.)
- OAuth 2.0 authentication flow documented (5-step process from `sem auth setup` to auto-refresh)
- New conventions added: dry-run mode, `{Foretag}/{website}` template placeholders, case-insensitive audit comparator
- API Keys section updated: OAuth replaces `GOOGLE_ADS_CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN`
- Installation section added: `pip install -e ".[dev]"` makes `sem` command available
- Running Tests section added: `python -m pytest tests/ -v`

### Task 2: Update .env.example and create dependency hygiene test

- `.env.example`: Removed `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (now managed by `sem auth login` + OS keyring). Added explanatory comment directing users to `client_secret.json` and keyring flow.
- `tests/test_deps.py`: 4 tests verifying spacy and pyenchant are absent from both `pyproject.toml` and `requirements.txt` (satisfies INF-08). All 4 pass.

## Verification Results

- `grep -c "sem auth" CLAUDE.md` → 4
- `grep -c "OAuth" CLAUDE.md` → 6
- `grep -c "sem pipeline" CLAUDE.md` → 1
- `.env.example` contains 0 occurrences of `GOOGLE_ADS_CLIENT_ID/SECRET/REFRESH_TOKEN`
- `python -m pytest tests/test_deps.py -v` → 4 passed
- `python -m pytest tests/ -q` → 209 passed, 1 pre-existing failure (test_auth.py token refresh mock, unrelated to this plan)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `CLAUDE.md` exists and contains required content (sem auth x4, OAuth x6, sem pipeline x1)
- `.env.example` exists without OAuth credential fields
- `tests/test_deps.py` exists and all 4 tests pass
- Commits `68a586e` and `ab501e3` verified in git log
