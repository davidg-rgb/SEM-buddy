---
phase: 07-oauth-token-management
plan: "01"
subsystem: auth
tags: [oauth, credentials, token-refresh, keyring, fernet, google-auth]
dependency_graph:
  requires: [src/utils/config_manager.py]
  provides: [src/auth/__init__.py, src/auth/oauth.py, src/auth/credentials.py, src/auth/token_refresh.py]
  affects: [src/cli/auth_commands.py (future), src/auth/google_ads_auth.py (future)]
tech_stack:
  added: [google-auth>=2.27, google-auth-oauthlib>=1.2, google-ads>=24.0, keyring>=25.0, cryptography>=42.0]
  patterns: [InstalledAppFlow desktop OAuth, keyring+Fernet fallback storage, auto-refresh on expiry]
key_files:
  created:
    - src/auth/__init__.py
    - src/auth/oauth.py
    - src/auth/credentials.py
    - src/auth/token_refresh.py
  modified:
    - pyproject.toml
decisions:
  - "Port retry in run_oauth_flow increments port+1 up to 3 attempts total, covering most ephemeral port conflicts"
  - "Fernet key stored in keyring where available; falls back to ~/.sem-master/credentials/.keyfile with chmod 0o600"
  - "ensure_valid_token raises AuthError with 'sem auth login' hint for both RefreshError and missing refresh_token"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 07 Plan 01: OAuth Token Management Core — Summary

One-liner: OAuth 2.0 InstalledAppFlow with port-retry, keyring-primary/Fernet-fallback credential storage, and auto-refresh on expiry.

## What Was Built

Four modules forming the complete token lifecycle foundation for all Google Ads API access:

- **`src/auth/__init__.py`**: Package root exporting `AuthError` and `StorageError` exceptions used across all auth modules.
- **`src/auth/oauth.py`**: Desktop OAuth flow via `InstalledAppFlow.from_client_secrets_file`. Opens browser consent page, retries on port conflict (up to 3 attempts, incrementing port each time), raises `AuthError` on user denial or network failure.
- **`src/auth/credentials.py`**: Secure storage with keyring as primary backend and Fernet-encrypted file (`~/.sem-master/credentials/tokens.enc`) as fallback. The Fernet key is itself stored in the keyring, falling back to `~/.sem-master/credentials/.keyfile`. `store_tokens`, `load_tokens`, and `clear_tokens` all handle both backends transparently.
- **`src/auth/token_refresh.py`**: `ensure_valid_token` returns credentials unchanged if valid, auto-refreshes via `google.auth.transport.requests.Request()` if expired, and re-persists via `store_tokens` after a successful refresh. `check_expiry` returns a status dict with `valid`, `expires_at`, and `minutes_remaining`.

**pyproject.toml** updated with all five auth dependencies: google-auth, google-auth-oauthlib, google-ads, keyring, cryptography.

## Verification

All auth modules importable without errors:
```
from src.auth import AuthError; from src.auth.oauth import run_oauth_flow; ...
from src.auth.token_refresh import ensure_valid_token, check_expiry
→ All auth modules importable OK
```

All 106 existing tests continue to pass (37 original + 69 from untracked test files picked up by pytest).

## Decisions Made

1. **Port retry range**: Up to 3 attempts (ports 8080, 8081, 8082 by default). After 3 failures raises `AuthError`. This covers most transient port conflicts without hanging indefinitely.
2. **Fernet key fallback path**: `~/.sem-master/credentials/.keyfile` with `chmod 0o600` attempt (no-op on Windows). Acceptable because the file lives inside the user's home directory.
3. **`ensure_valid_token` covers `credentials.valid == False` edge case**: If credentials are not expired but still invalid (e.g., revoked), raises `AuthError` with re-auth hint rather than silently returning bad credentials.
4. **Timezone-aware datetimes**: Both `_dict_to_credentials` and `check_expiry` normalize naive datetimes to UTC to match google-auth library expectations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed auth dependencies before running verification**
- **Found during:** Task 1 verification
- **Issue:** `google-auth-oauthlib`, `keyring`, and `cryptography` packages not yet installed in the Python environment.
- **Fix:** Ran `pip install "google-auth>=2.27" "google-auth-oauthlib>=1.2" "google-ads>=24.0" "keyring>=25.0" "cryptography>=42.0"` before verifying imports.
- **Files modified:** None (runtime environment only)
- **Commit:** Inline before Task 1 commit

## Known Stubs

None — all functions are fully implemented. `run_oauth_flow` requires a real `client_secret.json` to complete (this is expected; no stub).

## Self-Check: PASSED
