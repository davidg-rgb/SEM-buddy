---
phase: 08-google-ads-api-client-rewrite
plan: "02"
subsystem: apis
tags: [dry-run, google-ads, testing, synthetic-data, factory-pattern]
dependency_graph:
  requires: [08-01]
  provides: [DryRunGoogleAdsService, get_ads_service factory]
  affects: [Phase 09 CLI pipeline, all downstream pipeline consumers]
tech_stack:
  added: [random.Random seeded RNG]
  patterns: [Template Method (override all async methods), Factory Function]
key_files:
  created: [tests/test_google_ads_service.py]
  modified: [src/apis/google_ads.py, src/apis/__init__.py]
decisions:
  - "DryRunGoogleAdsService overrides __init__ entirely — no super().__init__() call — avoiding auth calls"
  - "Seeded RNG uses hash of (customer_id, context) for stable per-customer synthetic data"
  - "Keyword expansion uses separate hash of sorted seeds list for stable per-seed results"
  - "get_search_volumes returns one entry per input keyword (not a subset), unlike real implementation"
metrics:
  duration: ~5 minutes
  completed: 2026-04-01
  tasks_completed: 1
  files_changed: 3
---

# Phase 08 Plan 02: DryRunGoogleAdsService and Factory Summary

DryRunGoogleAdsService with full synthetic Swedish data and get_ads_service factory — enables pipeline dry-runs without API credentials.

## What Was Built

A complete dry-run implementation of GoogleAdsService that:

- Overrides all 7 async methods (`get_keyword_ideas`, `get_search_volumes`, `get_campaigns`, `get_ad_groups`, `get_keywords`, `get_ads`, `get_account_info`) with synthetic Swedish data
- Requires no credentials — skips parent `__init__` auth entirely
- Uses deterministic seeded RNG so identical inputs always return identical outputs
- Generates Swedish keyword expansions using common modifiers (stockholm, bästa, akut, pris, etc.)
- Returns RSA ad copy with headlines capped at 30 chars and descriptions at 90 chars per Google Ads limits
- Factory function `get_ads_service(customer_id, dry_run=False)` selects real vs dry-run implementation

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for DryRunGoogleAdsService | 49f30ac | tests/test_google_ads_service.py |
| 1 (GREEN) | DryRunGoogleAdsService + factory implementation | ae9888a | src/apis/google_ads.py, src/apis/__init__.py |

## Decisions Made

1. **DryRunGoogleAdsService.__init__ skips super().__init__()** — calls `get_google_ads_client` in parent would raise `AuthError` without credentials. Direct attribute assignment is correct for a mock that wants no auth.

2. **Two-level seeding strategy** — keyword ideas use `hash(tuple(sorted(seeds)))` so the same seeds always produce the same expansions regardless of call order. Campaign/ad data uses `hash((customer_id, context))` for per-customer stability.

3. **get_search_volumes returns one entry per input keyword** — unlike the real implementation which filters keyword_ideas results (which may miss some inputs), dry-run always returns exactly one entry per requested keyword, making tests predictable.

4. **Swedish RSA copy hardcoded in module-level constants** — avoids re-generating ad text on every call; all headlines verified at 30 chars or fewer, descriptions at 90 chars or fewer.

## Verification

All verification steps from the plan passed:

```
python -m pytest tests/test_google_ads_service.py -x -q   # 59 passed
python -m pytest tests/ -x -q                              # 165 passed
Factory returns DryRunGoogleAdsService: OK
Keywords returned: 5
Account info: {'id': '123', 'name': 'Dry-Run Test Account', 'currency': 'SEK', 'timezone': 'Europe/Stockholm'}
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- src/apis/google_ads.py contains `class DryRunGoogleAdsService(GoogleAdsService)`: FOUND
- src/apis/google_ads.py contains `def get_ads_service`: FOUND
- tests/test_google_ads_service.py exists: FOUND
- Commit 49f30ac (RED tests): FOUND
- Commit ae9888a (GREEN implementation): FOUND
- 165/165 tests pass: CONFIRMED
