---
phase: 06-config-account-management
plan: "01"
subsystem: core-foundation
tags: [cli, models, config, typer, pydantic]
dependency_graph:
  requires: []
  provides:
    - ManagedAccount Pydantic model with name/customer_id validation
    - config_manager with dot-notation YAML get/set for ~/.sem-master/config.yaml
    - sem CLI entry point (typer app) with --version and --help
    - src/accounts/ package stub for plans 02-03
  affects:
    - 06-02 (accounts_commands imports ManagedAccount, accounts package)
    - 06-03 (config_commands imports config_manager)
    - All subsequent plans (sem CLI entry point)
tech_stack:
  added:
    - typer[all]>=0.12 (CLI framework with Rich integration)
    - rich>=13.0 (terminal formatting)
    - pyyaml>=6.0 (YAML config file management)
  patterns:
    - Typer app factory pattern (create_app / main separation for testability)
    - Pydantic v2 field_validator for format enforcement
    - Deep-merge strategy for config defaults (upgrades add missing keys)
key_files:
  created:
    - src/models/account.py (ManagedAccount with name/customer_id validators)
    - src/utils/config_manager.py (load/save/get/set with dot-notation)
    - src/cli/__init__.py (CLI package init)
    - src/cli/app.py (Root Typer app, sem entry point)
    - src/accounts/__init__.py (accounts package stub for plans 02-03)
  modified:
    - src/models/client.py (added google_ads_customer_id field)
    - src/utils/config.py (removed Google Ads OAuth fields, added valueserp_api_key)
    - pyproject.toml (version 2.0.0, typer/rich/pyyaml deps, sem entry point, removed spacy)
    - requirements.txt (added typer/rich/pyyaml, removed spacy/pyenchant)
decisions:
  - Typer app factory (create_app returns app, main calls it) enables unit testing without subprocess
  - Deep-merge defaults in load_config so config upgrades add new keys without overwriting user values
  - model_post_init for datetime defaults (avoids Pydantic v2 default_factory issue with None sentinel)
metrics:
  duration: "4 minutes"
  completed: "2026-04-01T13:18:46Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 4
---

# Phase 06 Plan 01: Foundation Layer Summary

**One-liner:** Typer CLI entry point with sem --version/--help, ManagedAccount Pydantic model, and ~/.sem-master/config.yaml management via dot-notation YAML module.

## What Was Built

This plan established the foundation layer that all subsequent Phase 6 plans depend on:

1. **ManagedAccount model** (`src/models/account.py`) — Pydantic v2 model with field validators enforcing kebab-case name (`^[a-z0-9-]+$`) and Google Ads Customer ID format (`^\d{3}-\d{3}-\d{4}$`). Positive budget validation included.

2. **config_manager** (`src/utils/config_manager.py`) — Creates `~/.sem-master/config.yaml` with DEFAULT_CONFIG on first access. Deep-merge strategy ensures config upgrades add missing keys without overwriting existing values. Dot-notation `get_value("defaults.language_id")` and `set_value("active_client", "example")` with persistence.

3. **sem CLI entry point** (`src/cli/app.py`) — Typer app factory with `create_app()` / `main()` separation for testability. `sem --version` prints "SEM Master v2.0.0" with Rich formatting. `sem --help` shows auto-generated help. `rich_markup_mode="rich"` enables markup in all command help strings.

4. **Settings simplified** (`src/utils/config.py`) — Removed Google Ads OAuth credential fields (now handled by OAuth module in Phase 7). Added `valueserp_api_key`. Settings now loads only API keys from `.env`.

5. **ClientProfile extended** (`src/models/client.py`) — Added optional `google_ads_customer_id: str | None` field for MCC account binding.

6. **Dependencies updated** (`pyproject.toml`, `requirements.txt`) — Version bumped to 2.0.0. Added typer[all], rich, pyyaml. Removed spacy and pyenchant (per INF-08).

## Verification Results

- `sem --version` → "SEM Master v2.0.0" (via installed script and direct python invocation)
- `sem --help` → Typer auto-generated help with Rich formatting
- `load_config()` → creates `~/.sem-master/config.yaml` with defaults, returns `{"version": "2.0", ...}`
- `get_value("defaults.language_id")` → 1053
- `set_value("defaults.industry", "tandvard")` → persists to YAML
- ManagedAccount name/customer_id validators reject invalid formats
- All 106 tests pass (no regressions)

## Deviations from Plan

### Auto-added Missing Functionality

**1. [Rule 2 - Missing] Created src/accounts/__init__.py**
- **Found during:** Task 2 — plan frontmatter lists `src/accounts/__init__.py` in `files_modified` but no task action creates it
- **Fix:** Created minimal package init stub so plans 02-03 can import from `src.accounts`
- **Files modified:** `src/accounts/__init__.py`
- **Commit:** bb2839f

## Known Stubs

- `src/accounts/__init__.py` — Empty package stub. Accounts manager (list/add/remove/switch) implemented in Plan 06-02.
- `src/cli/app.py` — No command groups registered yet. `config_app` and `accounts_app` registered in Plans 06-02 and 06-03.

These stubs are intentional scaffolding, not blocking the plan's goal of establishing the foundation layer.

## Self-Check: PASSED
