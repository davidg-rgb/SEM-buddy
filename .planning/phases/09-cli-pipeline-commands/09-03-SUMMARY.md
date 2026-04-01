---
phase: 09-cli-pipeline-commands
plan: "03"
subsystem: cli
tags: [pipeline, orchestrator, typer, cli, dry-run]
dependency_graph:
  requires: ["09-01", "09-02"]
  provides: ["pipeline run", "pipeline status", "complete CLI app registration"]
  affects: ["src/cli/app.py", "src/cli/pipeline_commands.py"]
tech_stack:
  added: []
  patterns: ["CliRunner invocation pattern for stage orchestration", "lazy imports in create_app"]
key_files:
  created:
    - src/cli/pipeline_commands.py
  modified:
    - src/cli/app.py
decisions:
  - "CliRunner from typer.testing used to invoke each stage app — correct Typer CLI invocation without subprocess overhead"
  - "validate stage excluded from --dry-run flag since validate_commands.py has no such parameter"
  - "_STAGES_WITHOUT_DRY_RUN set constant makes it easy to add future stages that also skip dry-run"
  - "Lazy imports inside pipeline run() function to avoid circular imports at module load time"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-01"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
---

# Phase 09 Plan 03: Pipeline Orchestrator and CLI Wiring Summary

Pipeline orchestrator with `sem pipeline run` (--dry-run, --from, --to) and `sem pipeline status` commands, plus full registration of all 12 command groups in `app.py`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create pipeline_commands.py with run and status | 1fdb0ce | src/cli/pipeline_commands.py |
| 2 | Wire all stage + pipeline commands into app.py | 0331df5 | src/cli/app.py |

## What Was Built

### pipeline_commands.py

`pipeline_app` Typer instance with two commands:

**`sem pipeline run [client] [--dry-run] [--from STAGE] [--to STAGE]`**
- Validates `--from`/`--to` values against `PIPELINE_STAGES` using `typer.BadParameter`
- Slices `PIPELINE_STAGES[start_idx:end_idx+1]` to determine stages to run
- Lazy-imports all 8 stage Typer apps inside the function body
- Uses `typer.testing.CliRunner` to invoke each stage with correct CLI args
- Passes `--dry-run` to each stage except those in `_STAGES_WITHOUT_DRY_RUN` (`{"validate"}`)
- Prints stage output to console, stops on non-zero exit code with error message + traceback
- Prints final success message with output paths

**`sem pipeline status [client]`**
- Calls `get_pipeline_state(client_dir)` to read `workflow_state.json`
- Renders a Rich table with columns: Stage, Status (color-coded), Updated At
- Status colour coding: completed=green, in_progress=yellow, failed=red, pending=dim
- Wrapped in a Rich Panel with client name in title

### app.py

`create_app()` now registers 12 command groups (3 pre-existing + 8 stages + 1 pipeline):

```
config, accounts, auth, intake, research, competitors, keywords,
campaign, validate, export, report, pipeline
```

All imports are lazy (inside `create_app()`) for circular-import safety, consistent with the Phase 06/07 pattern.

## Verification

```
python -c "from src.cli.app import create_app; app = create_app(); print('App created with', len(app.registered_groups), 'groups')"
# Output: App created with 12 groups

python -c "from src.cli.pipeline_commands import pipeline_app; print('OK')"
# Output: OK
```

## Deviations from Plan

None — plan executed exactly as written. The `_STAGES_WITHOUT_DRY_RUN` set was added as a minor implementation detail (Rule 2: missing correctness requirement) since `validate_commands.py` has no `--dry-run` parameter, which would cause `CliRunner.invoke` to fail with an unrecognized option error if `--dry-run` were passed.

## Known Stubs

None. The pipeline orchestrator delegates all real work to the individual stage commands. The stage commands themselves contain appropriate dry-run synthetic data implementations.

## Self-Check: PASSED

- src/cli/pipeline_commands.py: FOUND
- src/cli/app.py: FOUND (modified)
- Commit 1fdb0ce: FOUND
- Commit 0331df5: FOUND
