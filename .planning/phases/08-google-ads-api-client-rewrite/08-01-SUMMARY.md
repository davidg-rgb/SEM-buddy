---
phase: 08-google-ads-api-client-rewrite
plan: "01"
subsystem: apis
tags: [google-ads, sdk, error-handling, oauth]
dependency_graph:
  requires: [src/auth/google_ads_auth.py, src/auth/__init__.py]
  provides: [src/apis/errors.py, src/apis/google_ads.py]
  affects: [src/apis/__init__.py]
tech_stack:
  added: [google-ads SDK official client, google.api_core.exceptions]
  patterns: [service-class pattern, centralised GAQL _search helper, typed error hierarchy]
key_files:
  created: [src/apis/errors.py]
  modified: [src/apis/google_ads.py, src/apis/__init__.py]
decisions:
  - GoogleAdsService._search centralises GAQL error wrapping — all 5 GAQL methods delegate here
  - _wrap_google_ads_error converts SDK exceptions to typed errors with actionable hints
  - get_search_volumes delegates to get_keyword_ideas and filters results — avoids duplicate API logic
  - AuthError from Phase 7 propagates as-is from __init__ — callers handle auth separately from API errors
metrics:
  duration_seconds: 125
  completed: "2026-04-01"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 08 Plan 01: Google Ads API Client Rewrite Summary

**One-liner:** Production GoogleAdsService using official SDK with OAuth from Phase 7, typed error hierarchy (ApiError -> GoogleAdsApiError/QuotaExceededError), and 7 async methods for keyword research and campaign data retrieval.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create API error hierarchy | 99f6655 | src/apis/errors.py |
| 2 | Rewrite GoogleAdsService with official SDK | 9981d52 | src/apis/google_ads.py, src/apis/__init__.py |

## What Was Built

### src/apis/errors.py
A typed exception hierarchy where every error carries `message` and `hint` attributes for actionable CLI display:
- `ApiError` — base class
- `GoogleAdsApiError` — wraps `GoogleAdsFailure` proto objects; includes `failure` attribute
- `QuotaExceededError` — defaults to quota-specific message and hint
- `SpyFuApiError`, `ValueSerpApiError` — stubs for future use

### src/apis/google_ads.py
`GoogleAdsService` replaces the old `GoogleAdsClient` stub:
- `__init__(customer_id)` calls `get_google_ads_client()` from Phase 7 auth factory; stores `_ga_service`
- `_search(query)` private helper executes GAQL and wraps all SDK exceptions once
- `_wrap_google_ads_error()` module-level helper maps `GoogleAdsException` and `GoogleAPIError` to typed errors with authentication/authorization/quota-specific hints
- 7 async public methods: `get_keyword_ideas`, `get_search_volumes`, `get_campaigns`, `get_ad_groups`, `get_keywords`, `get_ads`, `get_account_info`

### src/apis/__init__.py
Updated to export `GoogleAdsService` replacing `GoogleAdsClient`.

## Decisions Made

1. **_search centralises error handling** — all GAQL-based methods (`get_campaigns`, `get_ad_groups`, `get_keywords`, `get_ads`, `get_account_info`) route through `_search`, while keyword idea methods wrap errors inline due to using a different SDK service.

2. **_wrap_google_ads_error as module-level function** — used by both `_search` and `get_keyword_ideas`/`get_search_volumes` without duplicating logic.

3. **get_search_volumes delegates to get_keyword_ideas** — avoids reimplementing Keyword Planner request construction; filters results to requested keywords after the call.

4. **AuthError propagates unchanged** — `GoogleAdsService.__init__` does not catch `AuthError`; callers that instantiate the service are responsible for handling auth state. This matches the ARCHITECTURE.md design.

## Verification Results

1. `from src.apis.errors import ApiError, GoogleAdsApiError, QuotaExceededError` — OK
2. `from src.apis.google_ads import GoogleAdsService` — OK
3. `from src.apis import GoogleAdsService` — OK
4. All 7 public methods present — OK
5. `python -m pytest tests/ -x -q` — 106 passed

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all methods are fully implemented. Real API responses require valid OAuth credentials and a Google Ads developer token, but the implementation is complete and will work once credentials are configured.

## Self-Check: PASSED
