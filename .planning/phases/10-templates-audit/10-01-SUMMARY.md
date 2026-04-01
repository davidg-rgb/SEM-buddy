---
phase: 10-templates-audit
plan: "01"
subsystem: templates
tags: [templates, cli, campaign-reuse, typer]
dependency_graph:
  requires: [src/models/campaign.py, src/models/client.py, src/generators/ad_copy_generator.py, src/utils/config_manager.py, src/cli/stage_helpers.py]
  provides: [src/templates/manager.py, src/templates/adapter.py, src/cli/template_commands.py]
  affects: [src/cli/app.py]
tech_stack:
  added: []
  patterns: [Pydantic BaseModel for template schema, placeholder token replacement, lazy import in create_app]
key_files:
  created:
    - src/templates/__init__.py
    - src/templates/manager.py
    - src/templates/adapter.py
    - src/cli/template_commands.py
  modified:
    - src/cli/app.py
decisions:
  - "{Foretag}/{website} as placeholder tokens — ASCII-safe, distinct enough to avoid accidental collisions in ad copy"
  - "geo_targets cleared on save, set from client.geographic_targets on load — ensures correct geographic targeting per client"
  - "Ad copy fully regenerated on apply_template — never copies ad text verbatim from source client"
metrics:
  duration_minutes: 3
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 10 Plan 01: Campaign Template System Summary

Campaign template system with save/load/list/delete CRUD via `~/.sem-master/templates/{name}.json`, plus a Typer CLI (`sem templates`) and template adaptation that regenerates ad copy for the target client using `generate_rsa()`.

## What Was Built

### src/templates/manager.py

`CampaignTemplate` Pydantic model and four CRUD functions:

- `save_template(name, campaign_plan, client, description)` — strips client-specific data (`business_name` → `{Foretag}`, website host → `{website}`, `geo_targets` cleared) from all campaign/extension dicts and writes to `~/.sem-master/templates/{name}.json`.
- `load_template(name)` — reads and validates back to `CampaignTemplate`; raises `FileNotFoundError` if missing.
- `list_templates()` — globs `*.json`, returns summary dicts (name, description, created_at, source_client, source_industry); returns `[]` if directory absent.
- `delete_template(name)` — removes the JSON file; raises `FileNotFoundError` if missing.

### src/templates/adapter.py

`apply_template(template, client, keyword_groups=None)`:

- Recursively replaces `{Foretag}` / `{website}` tokens with the new client's values.
- Sets `geo_targets` from `client.geographic_targets` (overrides stripped value).
- If `keyword_groups` is provided and an ad group theme matches a key, keyword list is updated from the supplied groups.
- Calls `generate_rsa(theme, client, kw_texts, final_url)` for every ad group — ad copy is always freshly generated for the new client.
- Reconstructs `CampaignPlan` with adapted campaigns + substituted extensions.

### src/cli/template_commands.py

`template_app = typer.Typer(name="templates")` with four commands:

| Command | What it does |
|---------|-------------|
| `sem templates list` | Rich table of all saved templates |
| `sem templates save <name> [client]` | Saves client's campaign.json as template |
| `sem templates load <name> [client]` | Applies template to target client, writes campaign.json |
| `sem templates delete <name>` | Removes template file |

### src/cli/app.py

`template_app` imported and registered as `app.add_typer(template_app, name="templates", ...)` inside `create_app()`, following the existing lazy-import pattern.

## Verification

All five checks passed:

```
Manager OK
Adapter OK
CLI OK
App OK
template_app registered: ['config', 'accounts', 'auth', 'intake', 'research', 'competitors', 'keywords', 'campaign', 'validate', 'export', 'report', 'pipeline', 'templates']
```

## Commits

| Hash | Message |
|------|---------|
| 27ca2fe | feat(10-01): add campaign template manager and adapter |
| 35bc5a0 | feat(10-01): add template CLI commands and register in app.py |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All four template operations are fully wired. The `apply_template` function uses live `generate_rsa()` to produce real ad copy — no placeholder data flows to output.

## Self-Check: PASSED

Files exist:
- src/templates/__init__.py: FOUND
- src/templates/manager.py: FOUND
- src/templates/adapter.py: FOUND
- src/cli/template_commands.py: FOUND
- src/cli/app.py: MODIFIED (template_app registered at line 64 and 80)

Commits exist: 27ca2fe, 35bc5a0 — both in git log.
