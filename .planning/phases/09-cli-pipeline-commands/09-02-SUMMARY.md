---
phase: 09-cli-pipeline-commands
plan: 02
subsystem: cli
tags: [cli, campaign, validate, export, report, dry-run]
dependency_graph:
  requires:
    - src/cli/stage_helpers.py (from plan 09-01)
    - src/generators/campaign_builder.py
    - src/generators/csv_exporter.py
    - src/generators/report_generator.py
    - src/generators/pdf_generator.py
    - scripts/validate_campaign.py
  provides:
    - src/cli/campaign_commands.py (campaign_app)
    - src/cli/validate_commands.py (validate_app)
    - src/cli/export_commands.py (export_app)
    - src/cli/report_commands.py (report_app)
  affects:
    - src/cli/app.py (needs to register these 4 apps — done in plan 09-03)
tech_stack:
  added: []
  patterns:
    - Typer callback(invoke_without_command=True) for single-command stage groups
    - importlib.util for loading scripts/validate_campaign.py without sys.path mutation
    - DRY RUN banner prepended to markdown then passed to PDF generator directly
key_files:
  created:
    - src/cli/campaign_commands.py
    - src/cli/validate_commands.py
    - src/cli/export_commands.py
    - src/cli/report_commands.py
  modified: []
decisions:
  - importlib.util used to load validate_campaign.py — avoids sys.path mutation while keeping scripts/ at project root
  - DRY RUN banner prepended to markdown string, then the same string passed to generate_pdf_report directly — ensures banner appears in PDF without regenerating markdown inside export_pdf_report
  - Optional data (competitors, digital_presence) uses empty defaults — report/campaign stages can run even if those pipeline stages were skipped
metrics:
  duration: ~3 minutes
  completed: 2026-04-01T14:17:30Z
  tasks_completed: 2
  files_created: 4
---

# Phase 09 Plan 02: Campaign, Validate, Export, Report Stage Commands Summary

**One-liner:** Four Typer CLI commands for the output-generation pipeline stages — campaign builds structure, validate runs 11 checks, export generates CSV+XLSX, report generates markdown+PDF with DRY RUN banner.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Campaign and validate stage commands | 5148f3f | src/cli/campaign_commands.py, src/cli/validate_commands.py |
| 2 | Export and report stage commands with DRY RUN | c2c3666 | src/cli/export_commands.py, src/cli/report_commands.py |

## What Was Built

### campaign_commands.py
- `campaign_app` Typer group with single `@callback(invoke_without_command=True)` command
- Loads `client_profile.json` and `keyword_data.json`, optionally `site_crawl.json` for `DigitalPresence`
- Calls `build_campaigns(profile, keyword_groups, digital_presence)` to produce `CampaignPlan`
- Writes `clients/{name}/campaigns/campaign.json`
- Prints summary panel: campaigns / ad groups / keyword counts

### validate_commands.py
- `validate_app` Typer group
- Loads `campaign.json` as raw dict (not Pydantic model — validator expects plain dict)
- Loads `scripts/validate_campaign.py` via `importlib.util` to avoid sys.path pollution
- Calls `run_all_validations(plan_dict)` (11 checks) then `print_report(results)`
- On failure: sets stage status to "failed", prints warning, exits with code 1
- On pass: calls `complete_stage`

### export_commands.py
- `export_app` Typer group with `--dry-run` and `--keywords-only` flags
- Loads `CampaignPlan` via `model_validate_json`, calls `export_campaign_plan(plan, output_dir)`
- Exports `keyword_report.xlsx` alongside CSV files via `export_keyword_xlsx`
- `--keywords-only` skips CSV export and produces only the XLSX

### report_commands.py
- `report_app` Typer group with `--dry-run` and `--pdf/--no-pdf` flags
- Loads all available pipeline data; uses empty defaults for optional data
- **DRY-04**: When `--dry-run`, prepends `_DRY_RUN_BANNER` to the markdown string
- Passes the banner-prefixed markdown directly to `generate_pdf_report` — ensures DRY RUN warning appears in the PDF without regenerating markdown content
- Writes `strategy_report.md` and `strategy_report.pdf` to `clients/{name}/reports/`

## Deviations from Plan

### Auto-fixed Issues

**[Rule 3 - Blocking] stage_helpers.py already created by parallel Plan 01**
- **Found during:** Pre-execution file check
- **Issue:** Plan assumed stage_helpers.py would not exist; it was already present from Plan 01 running in parallel
- **Fix:** Read existing file and proceeded without recreating it — no action needed
- **Impact:** None — file matched expected interface exactly

None of the 4 command files required fixes.

## Known Stubs

None. All 4 command modules wire to real generators/validators. Optional data (competitors, digital_presence) uses proper empty defaults rather than hardcoded stubs.

## Self-Check: PASSED
