# Roadmap: SEM Master

## Milestones

- ✅ **v0.2.0 Polish & Verify** - Phases 1-5 (shipped 2026-03-06)
- 🚧 **v2.0 OAuth CLI Rework** - Phases 6-11 (in progress)

## Phases

<details>
<summary>✅ v0.2.0 Polish & Verify (Phases 1-5) - SHIPPED 2026-03-06</summary>

### Phase 1: Git Baseline
**Goal**: Establish version control so every subsequent change is tracked and reversible.
**Plans**: 1 plan

Plans:
- [x] 01-01: Initialize git repo with baseline commit and .gitignore

### Phase 2: Swedish Diacritics
**Goal**: All Swedish text across data files, report generator, and NLP utilities uses correct diacritics.
**Plans**: 1 plan

Plans:
- [x] 02-01: Fix diacritics in data files, report generator, and NLP utilities

### Phase 3: CSV Export & NLP Improvements
**Goal**: CSV exports pass Google Ads Editor import validation, compound word splitting produces meaningful Swedish components.
**Plans**: 2 plans

Plans:
- [x] 03-01: Fix CSV export format (remove Row Type column, add Campaign column, split files)
- [x] 03-02: Improve Swedish compound splitter with simplemma dictionary

### Phase 4: PDF Report Generation
**Goal**: Users can generate a styled PDF report from campaign analysis with correct Swedish characters.
**Plans**: 1 plan

Plans:
- [x] 04-01: Implement PDF report generation via markdown-pdf

### Phase 5: Test Suite & Validation
**Goal**: Automated tests verify all fixes remain correct and JSON schemas enforce data file structure.
**Plans**: 1 plan

Plans:
- [x] 05-01: Add pytest suite (37 tests) and JSON schemas for data files

</details>

---

### 🚧 v2.0 OAuth CLI Rework (In Progress)

**Milestone Goal:** Rework from API-key prototype to production CLI tool with Google Ads OAuth 2.0, MCC multi-client management, Typer CLI, campaign templates, and audit mode.

## Phase Details

### Phase 6: Config & Account Management
**Goal**: Operator can install the `sem` CLI and manage client accounts and configuration without touching the codebase.
**Depends on**: Phase 5 (existing codebase)
**Requirements**: CFG-01, CFG-02, CFG-03, CFG-04, ACCT-01, ACCT-02, ACCT-03, ACCT-04, ACCT-05, CLI-01, CLI-04, CLI-05
**Success Criteria** (what must be TRUE):
  1. `pip install -e .` makes `sem` available as a command with `--version` and `--help`
  2. `sem config show` displays defaults; `sem config set defaults.industry tandvard` updates `~/.sem-master/config.yaml`
  3. `sem accounts add acme 123-456-7890 --industry bygg_renovering --budget 25000` creates a client directory with `account.yaml`
  4. `sem accounts list` shows all registered clients; `sem accounts switch acme` sets the active client
  5. `sem accounts info` shows active client details; `sem accounts remove acme` archives the directory
**Plans**: 3 plans

Plans:
- [x] 06-01-PLAN.md — Foundation: models, config_manager, CLI entry point, dependencies
- [x] 06-02-PLAN.md — Account management: CRUD, per-client config, pipeline state
- [x] 06-03-PLAN.md — CLI commands: config and accounts subcommands with rich output

### Phase 7: OAuth & Token Management
**Goal**: Operator can authenticate with the Google Ads API via OAuth 2.0 and tokens are stored securely with automatic refresh.
**Depends on**: Phase 6 (config manager needed for MCC ID storage)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, ACCT-06
**Success Criteria** (what must be TRUE):
  1. `sem auth setup` prints a complete Google Cloud project setup guide
  2. `sem auth login` opens the browser, completes the OAuth consent flow, and stores tokens in the OS keyring
  3. `sem auth status` shows token validity, MCC info, and expiry time
  4. `sem auth logout` clears all stored credentials from all storage backends
  5. Expired tokens are automatically refreshed; `sem accounts add` verifies account accessibility under MCC via the API
**Plans**: TBD

### Phase 8: Google Ads API Client Rewrite
**Goal**: The Google Ads API client uses the official SDK with live keyword and campaign data, and a dry-run service substitutes realistic synthetic data when no credentials are present.
**Depends on**: Phase 7 (OAuth auth layer)
**Requirements**: GADS-01, GADS-02, GADS-03, GADS-04, GADS-05, DRY-01, DRY-02
**Success Criteria** (what must be TRUE):
  1. `GoogleAdsService.get_keyword_ideas()` returns real volume, CPC, and competition data from the Keyword Planner API
  2. `GoogleAdsService.get_campaigns()` returns live campaign data from a linked Google Ads account
  3. API errors surface as typed exceptions with actionable hints rather than raw SDK stack traces
  4. `--dry-run` flag is accepted on pipeline commands and routes all API calls to `DryRunGoogleAdsService`
  5. `DryRunGoogleAdsService` returns realistic synthetic data for every API method, with no credentials required
**Plans**: TBD

### Phase 9: CLI Pipeline Commands
**Goal**: Every pipeline stage is callable as an individual `sem <stage> <client>` command, the full pipeline runs end-to-end, and dry-run completes without API credentials.
**Depends on**: Phase 6 (account context), Phase 8 (Google Ads client for keywords stage)
**Requirements**: CLI-02, CLI-03, PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, DRY-03, DRY-04
**Success Criteria** (what must be TRUE):
  1. Every stage command (`sem intake`, `sem research`, `sem competitors`, `sem keywords`, `sem campaign`, `sem validate`, `sem export`, `sem report`) executes for a named client and writes output to the correct directory
  2. `sem pipeline run acme` executes all stages in sequence with a rich progress display
  3. `sem pipeline run acme --from keywords --to export` executes only the specified range of stages
  4. Running a stage out of order (e.g., `sem keywords acme` before `sem intake acme`) returns a clear prerequisite error
  5. `sem pipeline run acme --dry-run` completes end-to-end and the generated report contains a visible "DRY RUN" warning
**Plans**: TBD
**UI hint**: no

### Phase 10: Templates & Audit
**Goal**: Operator can save and reuse winning campaign structures as templates, and can pull live campaign data to compare against generated recommendations.
**Depends on**: Phase 8 (Google Ads client for audit fetch), Phase 9 (pipeline for template application)
**Requirements**: TMPL-01, TMPL-02, TMPL-03, TMPL-04, AUD-01, AUD-02, AUD-03
**Success Criteria** (what must be TRUE):
  1. `sem templates save standard-service acme` saves a reusable template stripped of client-specific data
  2. `sem templates list` shows all saved templates with name, description, and creation date
  3. `sem templates load standard-service new-client` applies the template to a different client with adapted copy, keywords, and geo targets
  4. `sem audit acme` fetches live Google Ads data and outputs a structured diff showing missing/extra campaigns, keyword gaps, ad copy diffs, and budget diffs
  5. The audit report is written to `clients/acme/audits/` and is readable as a standalone document
**Plans**: TBD

### Phase 11: Testing & Polish
**Goal**: All new modules have unit tests, the end-to-end dry-run pipeline passes, all existing tests continue passing, and project docs reflect the v2.0 architecture.
**Depends on**: Phases 6-10 (tests cover all new features)
**Requirements**: INF-04, INF-05, INF-06, INF-07, INF-08
**Success Criteria** (what must be TRUE):
  1. `pytest` runs tests for auth, accounts, CLI, templates, and audit modules without errors
  2. An end-to-end dry-run pipeline test (`test_pipeline_dry_run.py`) passes from intake through report generation
  3. All 37 existing v0.2.0 tests continue passing (no regressions)
  4. `CLAUDE.md` and `.env.example` reflect the v2.0 OAuth-based architecture
  5. `pip show` confirms spacy and pyenchant are no longer in the dependency tree
**Plans**: TBD

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Git Baseline | v0.2.0 | 1/1 | Complete | 2026-03-06 |
| 2. Swedish Diacritics | v0.2.0 | 1/1 | Complete | 2026-03-06 |
| 3. CSV Export & NLP | v0.2.0 | 2/2 | Complete | 2026-03-06 |
| 4. PDF Report | v0.2.0 | 1/1 | Complete | 2026-03-06 |
| 5. Test Suite & Validation | v0.2.0 | 1/1 | Complete | 2026-03-06 |
| 6. Config & Account Management | v2.0 | 3/3 | Complete   | 2026-04-01 |
| 7. OAuth & Token Management | v2.0 | 0/TBD | Not started | - |
| 8. Google Ads API Client Rewrite | v2.0 | 0/TBD | Not started | - |
| 9. CLI Pipeline Commands | v2.0 | 0/TBD | Not started | - |
| 10. Templates & Audit | v2.0 | 0/TBD | Not started | - |
| 11. Testing & Polish | v2.0 | 0/TBD | Not started | - |

---
*Last updated: 2026-04-01 — Phase 6 planned (3 plans, 3 waves)*
