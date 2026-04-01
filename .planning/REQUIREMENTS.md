# Requirements: SEM Master v2.0

**Defined:** 2026-04-01
**Core Value:** Automate the entire Google Ads campaign creation pipeline for a solo SEM consultant

## v2.0 Requirements

Requirements for the OAuth CLI Rework milestone. Each maps to roadmap phases.

### Authentication

- [x] **AUTH-01**: Operator can authenticate with Google Ads API via OAuth 2.0 desktop flow (browser consent + localhost callback)
- [x] **AUTH-02**: OAuth tokens are stored securely using OS keyring with Fernet-encrypted file fallback
- [x] **AUTH-03**: Expired tokens are automatically refreshed without operator intervention
- [x] **AUTH-04**: Operator can view auth status (token validity, MCC info, expiry time)
- [x] **AUTH-05**: Operator can logout and clear all stored credentials
- [x] **AUTH-06**: Operator can run interactive Google Cloud project setup guide

### Account Management

- [x] **ACCT-01**: Operator can register a new client with Google Ads Customer ID, industry, and budget
- [x] **ACCT-02**: Operator can list all managed client accounts with pipeline status
- [x] **ACCT-03**: Operator can switch active client context (used as default for all commands)
- [x] **ACCT-04**: Operator can view detailed info for any client account
- [x] **ACCT-05**: Operator can remove/archive a client account
- [x] **ACCT-06**: New client registration verifies account accessibility under MCC via API

### CLI Framework

- [x] **CLI-01**: `sem` command is installable via `pip install -e .` with pyproject.toml entry point
- [x] **CLI-02**: All command groups accessible: auth, accounts, pipeline, intake, research, competitors, keywords, campaign, validate, export, report, audit, templates, config
- [ ] **CLI-03**: Every command defaults to active client when no client name provided
- [x] **CLI-04**: `--help` available on all commands with auto-generated documentation
- [x] **CLI-05**: Terminal output uses rich formatting (tables, colors, progress indicators)

### Configuration

- [x] **CFG-01**: Global config stored at `~/.sem-master/config.yaml` with sensible defaults
- [x] **CFG-02**: Operator can view, set, and edit config values via `sem config` commands
- [x] **CFG-03**: Per-client config stored as `account.yaml` in client directory
- [x] **CFG-04**: Config supports dot-notation access (e.g., `sem config set defaults.industry tandvård`)

### Pipeline

- [x] **PIPE-01**: Each pipeline stage (intake through report) callable as individual `sem <stage> <client>` command
- [ ] **PIPE-02**: `sem pipeline run <client>` executes all stages in sequence with progress tracking
- [ ] **PIPE-03**: Pipeline enforces stage prerequisites (can't run keywords before intake)
- [ ] **PIPE-04**: Per-client workflow_state.json tracks stage completion with timestamps
- [ ] **PIPE-05**: `sem pipeline run --from <stage> --to <stage>` supports partial pipeline execution

### Google Ads API

- [x] **GADS-01**: Google Ads API client uses official `google-ads` SDK with OAuth authentication
- [x] **GADS-02**: Keyword Planner returns real keyword ideas with volume, CPC, and competition data
- [x] **GADS-03**: API client can fetch live campaign data (campaigns, ad groups, keywords, ads)
- [x] **GADS-04**: API client can retrieve account info for verification during client registration
- [x] **GADS-05**: API errors are wrapped in clear error types with actionable hints

### Dry-Run Mode

- [x] **DRY-01**: `--dry-run` flag available on all pipeline and stage commands
- [x] **DRY-02**: Dry-run substitutes DryRunGoogleAdsService with realistic synthetic data
- [x] **DRY-03**: Full pipeline completes end-to-end in dry-run without any API credentials
- [x] **DRY-04**: Reports generated in dry-run mode include visible "DRY RUN" warning

### Templates

- [ ] **TMPL-01**: Operator can save a client's campaign plan as a reusable template
- [ ] **TMPL-02**: Operator can list all saved templates with name, description, and date
- [ ] **TMPL-03**: Operator can load a template and apply it to a different client (adapting copy, keywords, geo targets)
- [ ] **TMPL-04**: Operator can delete saved templates

### Audit

- [ ] **AUD-01**: Operator can pull live campaign data from Google Ads and compare against generated recommendations
- [ ] **AUD-02**: Audit shows structured diff: missing/extra campaigns, keyword gaps, ad copy diffs, budget diffs
- [ ] **AUD-03**: Audit report written to client's audits/ directory

### Infrastructure

- [ ] **INF-04**: All new modules have unit tests (auth, accounts, CLI, templates, audit)
- [ ] **INF-05**: End-to-end dry-run pipeline test passes
- [ ] **INF-06**: All 37 existing tests continue passing
- [ ] **INF-07**: CLAUDE.md and .env.example updated for v2.0
- [ ] **INF-08**: Unused dependencies removed (spacy, pyenchant)

## Future Requirements (Deferred)

### Automation
- **AUTO-01**: Scheduled campaign performance checks
- **AUTO-02**: Automated bid adjustment recommendations
- **AUTO-03**: Campaign performance alerting

### Collaboration
- **COLLAB-01**: Client-facing report portal
- **COLLAB-02**: Multi-user access with role-based permissions

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user auth/permissions | Solo operator, unnecessary complexity |
| Web UI / dashboard | Terminal-first, CLI is the interface |
| Direct campaign upload to Google Ads | CSV export for Google Ads Editor is the workflow |
| Database backend | File-based storage sufficient for solo use |
| CI/CD pipeline | Local development, not enough team overhead to justify |
| Multi-language ad copy | Swedish-only market focus |
| Service account auth | Not supported by Google Ads API |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-01 | Phase 6 - Config & Account Management | Complete |
| CFG-02 | Phase 6 - Config & Account Management | Complete |
| CFG-03 | Phase 6 - Config & Account Management | Complete |
| CFG-04 | Phase 6 - Config & Account Management | Complete |
| ACCT-01 | Phase 6 - Config & Account Management | Complete |
| ACCT-02 | Phase 6 - Config & Account Management | Complete |
| ACCT-03 | Phase 6 - Config & Account Management | Complete |
| ACCT-04 | Phase 6 - Config & Account Management | Complete |
| ACCT-05 | Phase 6 - Config & Account Management | Complete |
| CLI-01 | Phase 6 - Config & Account Management | Complete |
| CLI-04 | Phase 6 - Config & Account Management | Complete |
| CLI-05 | Phase 6 - Config & Account Management | Complete |
| AUTH-01 | Phase 7 - OAuth & Token Management | Complete |
| AUTH-02 | Phase 7 - OAuth & Token Management | Complete |
| AUTH-03 | Phase 7 - OAuth & Token Management | Complete |
| AUTH-04 | Phase 7 - OAuth & Token Management | Complete |
| AUTH-05 | Phase 7 - OAuth & Token Management | Complete |
| AUTH-06 | Phase 7 - OAuth & Token Management | Complete |
| ACCT-06 | Phase 7 - OAuth & Token Management | Complete |
| GADS-01 | Phase 8 - Google Ads API Client | Complete |
| GADS-02 | Phase 8 - Google Ads API Client | Complete |
| GADS-03 | Phase 8 - Google Ads API Client | Complete |
| GADS-04 | Phase 8 - Google Ads API Client | Complete |
| GADS-05 | Phase 8 - Google Ads API Client | Complete |
| DRY-01 | Phase 8 - Google Ads API Client | Complete |
| DRY-02 | Phase 8 - Google Ads API Client | Complete |
| CLI-02 | Phase 9 - CLI Pipeline Commands | Complete |
| CLI-03 | Phase 9 - CLI Pipeline Commands | Pending |
| PIPE-01 | Phase 9 - CLI Pipeline Commands | Complete |
| PIPE-02 | Phase 9 - CLI Pipeline Commands | Pending |
| PIPE-03 | Phase 9 - CLI Pipeline Commands | Pending |
| PIPE-04 | Phase 9 - CLI Pipeline Commands | Pending |
| PIPE-05 | Phase 9 - CLI Pipeline Commands | Pending |
| DRY-03 | Phase 9 - CLI Pipeline Commands | Complete |
| DRY-04 | Phase 9 - CLI Pipeline Commands | Complete |
| TMPL-01 | Phase 10 - Templates & Audit | Pending |
| TMPL-02 | Phase 10 - Templates & Audit | Pending |
| TMPL-03 | Phase 10 - Templates & Audit | Pending |
| TMPL-04 | Phase 10 - Templates & Audit | Pending |
| AUD-01 | Phase 10 - Templates & Audit | Pending |
| AUD-02 | Phase 10 - Templates & Audit | Pending |
| AUD-03 | Phase 10 - Templates & Audit | Pending |
| INF-04 | Phase 11 - Testing & Polish | Pending |
| INF-05 | Phase 11 - Testing & Polish | Pending |
| INF-06 | Phase 11 - Testing & Polish | Pending |
| INF-07 | Phase 11 - Testing & Polish | Pending |
| INF-08 | Phase 11 - Testing & Polish | Pending |

**Coverage:**
- v2.0 requirements: 45 total
- Mapped to phases: 45
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after initial definition*
