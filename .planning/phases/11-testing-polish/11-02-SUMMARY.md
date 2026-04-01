---
phase: 11-testing-polish
plan: 02
subsystem: testing
tags: [pytest, typer, pydantic, templates, audit, pipeline, cli, dry-run]

requires:
  - phase: 10-templates-audit
    provides: "Template CRUD (manager.py), audit comparator (comparator.py), CLI audit/template commands"
  - phase: 09-cli-pipeline
    provides: "Pipeline orchestrator, stage commands, dry-run mode for all 8 stages"

provides:
  - "18 unit tests for templates module (save/load/list/delete, client-data stripping)"
  - "10 unit tests for audit comparator (all 7 diff categories, case-insensitive, report formatting)"
  - "5 unit tests for CLI app (create_app, version, help, subcommands)"
  - "5 e2e dry-run pipeline tests (intake/research/competitors individual stages + full 8-stage run + status)"

affects: [ci, integration-testing, quality-assurance]

tech-stack:
  added: []
  patterns:
    - "monkeypatch TEMPLATES_DIR in autouse fixture — prevents polluting ~/.sem-master/templates"
    - "monkeypatch CLIENTS_DIR in src.utils.config, src.cli.stage_helpers, src.accounts.manager — all three must be patched together for pipeline tests"
    - "stage apps invoked via CliRunner with --dry-run before positional arg — matches how invoke_without_command Typer apps parse options"

key-files:
  created:
    - tests/test_templates.py
    - tests/test_audit_comparator.py
    - tests/test_cli_app.py
    - tests/test_pipeline_dry_run.py
  modified:
    - src/cli/pipeline_commands.py
    - src/cli/keywords_commands.py

key-decisions:
  - "Stage apps invoked with [--dry-run, client_name] — option before positional to avoid Typer treating --dry-run as subcommand"
  - "competition fallback None (not 'UNKNOWN') in keywords_commands — None is a valid Pydantic Literal | None field"

patterns-established:
  - "Pipeline bug fix: --dry-run must precede positional [CLIENT] arg in Typer invoke_without_command apps"
  - "Keyword competition: 'UNKNOWN' from missing volume data must be mapped to None before Keyword model construction"

requirements-completed: [INF-04, INF-05]

duration: 8min
completed: 2026-04-01
---

# Phase 11 Plan 02: Testing — Templates, Audit, CLI, Pipeline Summary

**28 new tests for templates CRUD, audit diff engine, CLI subcommand registry, and full 8-stage dry-run pipeline (259 total passing)**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-01T14:52:03Z
- **Completed:** 2026-04-01T14:59:54Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- 8-test template CRUD suite verifying save/load/list/delete and client-data placeholder stripping
- 10-test audit comparator suite covering all 7 diff categories plus case-insensitive matching and Swedish-language report formatting
- 5-test CLI suite verifying app factory, version flag, help text, and all 14 subcommand groups
- 5-test e2e pipeline dry-run suite: individual stage commands plus full 8-stage orchestrated run with no tracebacks
- Auto-fixed 2 pre-existing bugs discovered during test execution

## Task Commits

1. **Task 1: Template manager and audit comparator tests** - `fe0e5eb` (test)
2. **Task 2: CLI app tests and pipeline dry-run tests + bug fixes** - `36b61e9` (test)

## Files Created/Modified

- `tests/test_templates.py` - 8 tests for save/load/list/delete and client-data stripping
- `tests/test_audit_comparator.py` - 10 tests for all audit diff categories and report formatter
- `tests/test_cli_app.py` - 5 tests for app creation, version, help, and 14 subcommand groups
- `tests/test_pipeline_dry_run.py` - 5 e2e tests including full 8-stage pipeline dry-run
- `src/cli/pipeline_commands.py` - Fixed dry-run arg order (--dry-run before positional)
- `src/cli/keywords_commands.py` - Fixed invalid competition fallback 'UNKNOWN' → None

## Decisions Made

- Stage apps invoked with `['--dry-run', client_name]` — Typer's `invoke_without_command` parser treats any arg after the positional as a subcommand, so options must appear first
- `competition` fallback changed from `"UNKNOWN"` to `None` — the Pydantic field is `Literal['LOW','MEDIUM','HIGH'] | None`, and `None` is the correct sentinel for missing API data

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ResponsiveSearchAd min-list validators in test helper**
- **Found during:** Task 1 (Audit comparator tests)
- **Issue:** `_make_plan()` helper created `ResponsiveSearchAd` with only 1 headline and 1 description, failing Pydantic min_length validators (3 headlines, 2 descriptions required)
- **Fix:** Added 2 extra headlines and 1 extra description to satisfy validators
- **Files modified:** tests/test_audit_comparator.py
- **Verification:** All 10 audit comparator tests pass
- **Committed in:** fe0e5eb (Task 1 commit)

**2. [Rule 1 - Bug] Fixed pipeline_commands.py --dry-run arg ordering**
- **Found during:** Task 2 (Pipeline dry-run test)
- **Issue:** `args = [name] + ['--dry-run']` places `--dry-run` after the positional `[CLIENT]` argument; Typer's `invoke_without_command` app treats it as a subcommand name, causing exit code 2 with "No such command '--dry-run'"
- **Fix:** Changed to `args = ['--dry-run', name]` so the option is parsed before the positional
- **Files modified:** src/cli/pipeline_commands.py
- **Verification:** Full 8-stage pipeline dry-run completes with exit code 0
- **Committed in:** 36b61e9 (Task 2 commit)

**3. [Rule 1 - Bug] Fixed keywords_commands.py invalid competition fallback**
- **Found during:** Task 2 (Pipeline dry-run test, stage 5 campaign failure)
- **Issue:** Keywords without volume data received `competition="UNKNOWN"` as fallback, which fails `Literal['LOW','MEDIUM','HIGH']` Pydantic validation in `Keyword` model, crashing the campaign build stage
- **Fix:** Changed fallback to `vol_entry.get("competition") or None` — `None` is a valid value for the `Literal | None` field
- **Files modified:** src/cli/keywords_commands.py
- **Verification:** Campaign stage builds successfully; all 259 tests pass
- **Committed in:** 36b61e9 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All fixes necessary for test correctness and pipeline correctness. No scope creep.

## Issues Encountered

- Windows console encoding (cp1252) prevents printing `result.output` directly in shell — worked around by writing to file with UTF-8 encoding when debugging
- Typer's `invoke_without_command=True` option-before-positional requirement was not documented in the existing pipeline orchestrator — discovered via test execution

## Known Stubs

None — all test files exercise real code paths, no placeholder data wired to production output.

## Next Phase Readiness

- All 4 test files are fully wired to production modules
- 259 tests pass with no regressions
- Pipeline dry-run validated end-to-end (intake → research → competitors → keywords → campaign → validate → export → report)
- Ready for final polish tasks (phase 11 plan 03)

---
*Phase: 11-testing-polish*
*Completed: 2026-04-01*
