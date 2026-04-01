---
phase: 09-cli-pipeline-commands
plan: 01
subsystem: cli
tags: [typer, rich, pipeline, stages, keywords, crawl, competitors]

requires:
  - phase: 08-google-ads-api
    provides: get_ads_service factory for dry-run/live keyword volume lookups
  - phase: 07-oauth-auth
    provides: AuthError and auth credential management
  - phase: 06-cli-foundation
    provides: Typer CLI app pattern, accounts manager, pipeline state machine

provides:
  - stage_helpers.py shared module (resolve_client, require_prerequisites, complete_stage, mark_stage_started)
  - intake_commands.py (sem intake command, prompts or dry-run)
  - research_commands.py (sem research command, site crawl or dry-run)
  - competitors_commands.py (sem competitors command, competitor profiles)
  - keywords_commands.py (sem keywords command, full keyword pipeline with volume data)

affects: [09-02, campaign-commands, report-commands]

tech-stack:
  added: []
  patterns:
    - "Stage command pattern: resolve_client + require_prerequisites + mark_stage_started + work + complete_stage"
    - "Dry-run flag on every stage command routes through get_ads_service(dry_run=True)"
    - "Stage exception handler calls update_state(failed) before re-raising"

key-files:
  created:
    - src/cli/stage_helpers.py
    - src/cli/intake_commands.py
    - src/cli/research_commands.py
    - src/cli/competitors_commands.py
    - src/cli/keywords_commands.py
  modified: []

key-decisions:
  - "Stage helpers extracted to stage_helpers.py — keeps each command module small and consistent"
  - "Dry-run mode creates synthetic data for all stages — enables full pipeline testing without API credentials"
  - "competitors stage structures known_competitors from intake profile in non-dry-run mode (real scraper integration deferred to sem-competitor-ads skill)"

patterns-established:
  - "Stage command pattern: all 4 commands follow identical resolve + prereqs + start + work + complete flow"
  - "Failure handling: update_state(failed) called in except block before re-raise in all stage commands"

requirements-completed: [CLI-02, CLI-03, PIPE-01, PIPE-03, PIPE-04]

duration: 3min
completed: 2026-04-01
---

# Phase 09 Plan 01: CLI Pipeline Stage Commands Summary

**Shared stage helper module plus 4 data-gathering pipeline CLI commands (intake, research, competitors, keywords) with --dry-run support and prerequisite enforcement.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-01T14:14:45Z
- **Completed:** 2026-04-01T14:17:34Z
- **Tasks:** 2
- **Files modified:** 5 created

## Accomplishments

- Created `stage_helpers.py` with `resolve_client`, `require_prerequisites`, `complete_stage`, and `mark_stage_started` — extracts the common pattern shared by all stage commands
- Created 4 pipeline stage commands: `intake`, `research`, `competitors`, `keywords` — each enforces prerequisites, supports `--dry-run`, defaults to active client, and updates `workflow_state.json`
- Keywords command integrates full pipeline: seed generation → Swedish expansion → Google Ads volume (via `get_ads_service` factory) → grouping → match type assignment → negative keywords

## Task Commits

1. **Task 1: Create stage_helpers.py shared module** - `6816eed` (feat)
2. **Task 2: Create intake, research, competitors, keywords stage commands** - `68144f8` (feat)

## Files Created/Modified

- `src/cli/stage_helpers.py` - Shared helpers: resolve_client, require_prerequisites, complete_stage, mark_stage_started
- `src/cli/intake_commands.py` - sem intake command: prompts or dry-run synthetic ClientProfile, writes client_profile.json
- `src/cli/research_commands.py` - sem research command: Playwright site crawl or dry-run synthetic SiteCrawl, writes site_crawl.json
- `src/cli/competitors_commands.py` - sem competitors command: structures competitor profiles, dry-run creates 3 synthetic entries
- `src/cli/keywords_commands.py` - sem keywords command: full keyword pipeline with Google Ads API volume data

## Decisions Made

- Stage helpers extracted into `stage_helpers.py` — keeps each command module focused on its own work rather than repeating client resolution and state management logic
- Dry-run creates synthetic data at every stage — enables full end-to-end pipeline testing without any API credentials configured
- Competitors non-dry-run mode structures data from `known_competitors` in the intake profile; real ad scraping deferred to `sem-competitor-ads` skill integration (out of scope for this phase)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 4 data-gathering stage commands ready for registration in `app.py` (done in phase 09-02)
- Stage helpers module is the shared foundation for remaining stage commands (campaign, validate, export, report)
- Full `sem intake → sem research → sem competitors → sem keywords` flow functional with `--dry-run`

## Self-Check: PASSED

All 5 files found, both task commits verified (6816eed, 68144f8).

---
*Phase: 09-cli-pipeline-commands*
*Completed: 2026-04-01*
