---
phase: 11-testing-polish
plan: "01"
subsystem: testing
tags: [pytest, auth, oauth, keyring, credentials, token-refresh, google-ads, accounts, pipeline-state]

requires:
  - phase: 07-auth
    provides: "oauth.py, credentials.py, token_refresh.py, google_ads_auth.py — all modules under test"
  - phase: 06-accounts
    provides: "accounts/manager.py, accounts/state.py, models/account.py — all modules under test"

provides:
  - "Unit tests for all four auth modules (oauth, credentials, token_refresh, google_ads_auth)"
  - "Unit tests for account manager CRUD operations"
  - "Unit tests for pipeline state machine"

affects: [phase-12, integration-testing, ci-pipeline]

tech-stack:
  added: []
  patterns:
    - "Autouse fixture for CLIENTS_DIR isolation: monkeypatch module-level constant to tmp_path"
    - "Inline import after monkeypatch: import function inside test body after patching module-level names"
    - "Fake keyring store dict: dict-backed set_password/get_password/delete_password replaces OS keyring"
    - "autouse fixture for TOKEN_FILE/KEY_FILE: redirects all file I/O to tmp_path per test"

key-files:
  created:
    - tests/test_auth.py
    - tests/test_accounts.py
    - tests/test_pipeline_state.py
  modified: []

key-decisions:
  - "Inline import inside test body after monkeypatching module attributes — ensures patched constants are used when function runs"
  - "Dict-backed fake keyring — avoids OS keyring dependency, fully deterministic, no side-effects"
  - "autouse fixture for file path redirection — all 23 credential tests run isolated without needing explicit fixture parameter"

patterns-established:
  - "Pattern: monkeypatch module-level Path constants before importing functions that use them at call time"
  - "Pattern: test class per function group — TestRunOAuthFlow, TestCredentials, TestEnsureValidToken, etc."

requirements-completed: [INF-04, INF-06]

duration: 3min
completed: "2026-04-01"
---

# Phase 11 Plan 01: Auth and Accounts Unit Tests Summary

**62 new pytest tests covering OAuth flow retry logic, keyring/file credential storage, token refresh, Google Ads client factory, account CRUD with isolated tmp_path, and pipeline state machine transitions**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-01T14:52:01Z
- **Completed:** 2026-04-01T14:55:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Auth module tests: 23 tests across oauth, credentials (keyring + file fallback), token_refresh, google_ads_auth
- Account manager tests: 19 tests covering create, list, get, remove/archive, active client lifecycle
- Pipeline state tests: 20 tests covering initialize, update, prerequisites checking, next-stage resolution
- Full regression suite: 249 tests pass (37 original + 212 previously committed + 62 new)

## Task Commits

1. **Task 1: Auth module unit tests** - `594ef46` (test)
2. **Task 2: Account manager and pipeline state tests** - `f717cc9` (test)

## Files Created/Modified

- `tests/test_auth.py` - 23 tests for oauth, credentials, token_refresh, google_ads_auth
- `tests/test_accounts.py` - 19 tests for account manager CRUD and active client management
- `tests/test_pipeline_state.py` - 20 tests for pipeline state machine

## Decisions Made

- Inline import inside test body after monkeypatching module attributes — ensures patched constants are used when function runs (discovered when `NameError` occurred in two token refresh tests)
- Dict-backed fake keyring — avoids OS keyring dependency, fully deterministic, no side-effects between tests
- autouse fixture for file path redirection — keeps credential tests clean without explicit fixture parameters

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed NameError in two token refresh tests**
- **Found during:** Task 1 (auth module tests)
- **Issue:** `ensure_valid_token` function not in scope after monkeypatching module attributes; import at top of test file was shadowed
- **Fix:** Added `from src.auth.token_refresh import ensure_valid_token` inside test body after monkeypatching
- **Files modified:** tests/test_auth.py
- **Verification:** Both tests pass after fix
- **Committed in:** 594ef46 (Task 1 commit — fix applied before final commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Minor fix required, no scope change. All planned test cases implemented.

## Issues Encountered

- Two token refresh tests raised `NameError: name 'ensure_valid_token' is not defined` on first run. The test body imported the module for monkeypatching but didn't re-import the function. Fix: add function import after monkeypatching inside the test body.

## Known Stubs

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All auth and accounts modules now have comprehensive unit test coverage
- Full suite of 249 tests passes cleanly
- Ready for integration testing or CI pipeline configuration

---
*Phase: 11-testing-polish*
*Completed: 2026-04-01*
