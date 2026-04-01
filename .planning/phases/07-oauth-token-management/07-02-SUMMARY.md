---
phase: 07-oauth-token-management
plan: "02"
subsystem: auth-cli
tags: [auth, cli, google-ads, oauth, mcc]
dependency_graph:
  requires: [07-01]
  provides: [google_ads_auth, auth_commands, setup_guide, mcc_verification]
  affects: [src/cli/app.py, src/cli/accounts_commands.py]
tech_stack:
  added: []
  patterns: [lazy-import-in-create_app, non-blocking-api-verification, rich-panel-guided-output]
key_files:
  created:
    - src/auth/google_ads_auth.py
    - src/cli/auth_commands.py
    - scripts/setup_google_cloud.py
  modified:
    - src/cli/app.py
    - src/cli/accounts_commands.py
decisions:
  - "Auth CLI commands use lazy import inside create_app() — consistent with Phase 06 pattern"
  - "MCC verification is non-blocking (--verify flag, warning on failure) — account created locally regardless"
  - "setup_google_cloud.py mirrors auth setup command — standalone for use before CLI installed"
metrics:
  duration: ~4 minutes
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_created: 3
  files_modified: 2
---

# Phase 07 Plan 02: Auth CLI Commands & MCC Verification Summary

**One-liner:** Complete auth CLI journey (setup guide, OAuth login, token status, logout) plus authenticated GoogleAdsClient factory and ACCT-06 MCC account verification.

## What Was Built

### Task 1: google_ads_auth.py, auth_commands.py, setup_google_cloud.py

**src/auth/google_ads_auth.py** — Authenticated client factory:
- `build_google_ads_config(credentials, developer_token, login_customer_id)` builds a dict for `GoogleAdsClient.load_from_dict()`, stripping hyphens from customer IDs
- `get_google_ads_client(customer_id)` loads stored tokens, refreshes if expired, reads developer_token and mcc_customer_id from config, raises `AuthError` with actionable messages if unconfigured

**src/cli/auth_commands.py** — Full auth lifecycle commands:
- `sem auth setup` — 8-step Rich-formatted guide for Google Cloud project, OAuth credentials, and developer token configuration
- `sem auth login` — Checks for client_secret.json, runs `run_oauth_flow()`, stores tokens, handles `AuthError`
- `sem auth status` — Loads tokens, calls `check_expiry()`, renders Rich panel with validity, expiry time, MCC ID, and developer token status
- `sem auth logout` — Calls `clear_tokens()`, idempotent

**scripts/setup_google_cloud.py** — Standalone setup guide identical to `sem auth setup`, runnable without the CLI package installed.

### Task 2: app.py wire-up and ACCT-06 MCC verification

**src/cli/app.py** — `auth_app` registered under `sem auth` following the lazy-import-inside-create_app() pattern from Phase 06.

**src/cli/accounts_commands.py** — `--verify` flag added to `sem accounts add`:
- Calls `get_google_ads_client()` inside the if-block (avoids import errors when auth not configured)
- Uses `CustomerService.list_accessible_customers()` to get accessible resource names
- Warning on inaccessible account — non-blocking, account still created locally
- Catches all exceptions with informative fallback message

## Verification Results

```
OK: auth command group present in sem --help
OK: auth setup / login / status / logout all registered
OK: sem auth status -> "Not authenticated" when no tokens
OK: sem auth logout -> "All credentials cleared." (idempotent)
OK: python scripts/setup_google_cloud.py -> prints full guide
106 tests passed (all existing tests unbroken)
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — no placeholder data or hardcoded empty values introduced. The `get_google_ads_client()` factory makes real API calls; it will raise `AuthError` if credentials are not configured (intended behavior, not a stub).

## Self-Check: PASSED

Files exist:
- src/auth/google_ads_auth.py: FOUND
- src/cli/auth_commands.py: FOUND
- scripts/setup_google_cloud.py: FOUND
- src/cli/app.py: FOUND (modified)
- src/cli/accounts_commands.py: FOUND (modified)

Commits exist:
- 8f9f542: feat(07-02): add google_ads_auth client factory, auth CLI commands, and setup guide
- bc4f4d3: feat(07-02): wire auth commands into CLI app and add ACCT-06 MCC verification
