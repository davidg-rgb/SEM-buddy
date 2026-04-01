# SEM Master v2.0 — Architecture Blueprint

> Generated from: Scope rework conversation (OAuth + CLI + consultancy model)
> Date: 2026-04-01
> Status: DRAFT — Pending Review

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Requirements Analysis](#2-requirements-analysis)
3. [Architecture Decision Records](#3-architecture-decision-records)
4. [Tech Stack](#4-tech-stack)
5. [Project Structure](#5-project-structure)
6. [Module & Function Definitions](#6-module--function-definitions)
7. [Data Models](#7-data-models)
8. [Interface Contracts](#8-interface-contracts)
9. [Data Flow Diagrams](#9-data-flow-diagrams)
10. [Dependency Map](#10-dependency-map)
11. [Cross-Cutting Concerns](#11-cross-cutting-concerns)
12. [Extensibility Guide](#12-extensibility-guide)
13. [Risk Register](#13-risk-register)
14. [Implementation Roadmap](#14-implementation-roadmap)
15. [Build Verification Checklist](#15-build-verification-checklist)

---

## 1. Executive Summary

SEM Master is a terminal-based Google Ads campaign automation tool for a solo SEM consultancy serving Swedish/Nordic clients. Version 2.0 reworks the project from an API-key-based prototype into a production-ready CLI tool with:

- **Google Ads OAuth 2.0** authentication via MCC (Manager Account) pattern
- **Multi-client account management** under a single operator
- **Unified CLI** (`sem` command) with subcommands for every workflow stage
- **Dry-run mode** for demos and pitches without live API calls
- **Campaign templates** to reuse winning structures across clients
- **Audit mode** to pull live data and compare against recommendations

The existing pipeline (intake → research → competitor analysis → keywords → campaign build → export → report) remains intact. The rework adds a proper auth layer, CLI entry points, and professional account management while keeping the sole operator as superuser.

---

## 2. Requirements Analysis

### 2.1 Core Features

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F-001 | OAuth Authentication | Google Ads OAuth 2.0 desktop flow with localhost callback | Critical |
| F-002 | Token Management | Encrypted storage, auto-refresh, re-auth prompts | Critical |
| F-003 | MCC Account Linking | Link/unlink client Google Ads accounts under MCC | Critical |
| F-004 | CLI Framework | `sem` command with subcommands for all operations | Critical |
| F-005 | Client Management | Create, list, switch, archive clients with Google Ads account binding | Critical |
| F-006 | Pipeline Orchestration | Run full or partial pipeline per client via CLI | Critical |
| F-007 | Dry-Run Mode | Generate everything locally without API calls | High |
| F-008 | Campaign Templates | Save/load winning campaign structures | High |
| F-009 | Audit Mode | Pull live campaign data, compare against recommendations | Medium |
| F-010 | Global Config | `~/.sem-master/config.yaml` for operator-level settings | High |
| F-011 | Pipeline State | Per-client workflow_state.json with stage tracking | Critical |
| F-012 | Google Ads Keyword Planner | Live keyword volume/CPC data via authenticated API | Critical |
| F-013 | Existing Scrapers | Site crawler, GBP, reviews, social, transparency (unchanged) | Critical |
| F-014 | Existing Generators | Keywords, ad copy, campaigns, CSV, reports (unchanged) | Critical |
| F-015 | Existing Validation | 11-check campaign validator (unchanged) | Critical |

### 2.2 User Roles & Journeys

**Single role: Operator (superuser)**

**Journey 1: First-time setup**
```
Install → sem auth setup → Configure Google Cloud project → sem auth login →
Link MCC account → sem accounts add <first-client> → Ready
```

**Journey 2: New client onboarding**
```
sem accounts add <client> → sem intake <client> → sem research <client> →
sem competitors <client> → sem keywords <client> → sem campaign <client> →
sem validate <client> → sem export <client> → sem report <client>
```

**Journey 3: Quick keyword research**
```
sem keywords <client> → Review output → sem export <client> --keywords-only
```

**Journey 4: Campaign audit (existing client)**
```
sem audit <client> → Review live vs recommended diff → Adjust → sem export <client>
```

**Journey 5: Demo/pitch preparation**
```
sem pipeline run <client> --dry-run → Review generated materials → Present to prospect
```

### 2.3 Constraints

| Constraint | Value |
|-----------|-------|
| Python version | 3.11+ |
| Platform | Windows 11 (primary), cross-platform compatible |
| Single operator | No multi-user auth, no RBAC |
| Google Ads API | Requires approved developer token (Basic access) |
| Swedish market | All ad copy in Swedish, geo IDs for Swedish cities |
| Character limits | Headlines ≤30, descriptions ≤90, paths ≤15, sitelinks ≤25 |
| CSV encoding | UTF-8 BOM for Excel compatibility |
| Shell | Bash syntax (Git Bash on Windows) |

### 2.4 Integrations

| System | Auth Method | Purpose |
|--------|-----------|---------|
| Google Ads API | OAuth 2.0 (Desktop flow) | Keyword Planner, campaign data, account management |
| Google Ads Transparency Center | Playwright scraping | Competitor ad intelligence |
| SpyFu API | API key | Competitor keywords, ad history, domain stats |
| ValueSERP API | API key | SERP data, ads, People Also Ask |
| Anthropic API | API key | AI-powered ad copy generation |
| Google Business Profile | httpx scraping | Business data extraction |
| Trustpilot / Reco.se | httpx scraping | Review aggregation |

### 2.5 Resolved Ambiguities

| Question | Decision | Rationale |
|----------|----------|-----------|
| CLI framework: Click vs Typer? | **Typer** | Auto-generates help, type hints align with Pydantic models, less boilerplate |
| Token encryption: keyring vs cryptography? | **keyring** (with cryptography fallback) | OS-native credential storage; fallback for headless/CI environments |
| Config format: YAML vs TOML? | **YAML** | More readable for nested config, already familiar in the ecosystem |
| Where to store credentials? | **`~/.sem-master/credentials/`** | Follows XDG-like convention, separate from project code |
| How to handle MCC vs direct accounts? | **MCC required** | Professional consultancy pattern; direct account support as fallback |
| Google Ads API library? | **`google-ads`** (official Python SDK) | Official support, handles OAuth token refresh, GAQL query builder |

---

## 3. Architecture Decision Records

### ADR-001: Typer for CLI Framework

**Decision:** Use Typer (built on Click) for the CLI framework.

**Alternatives considered:**
- **Click**: More mature, widely used. More verbose, manual type conversion.
- **argparse**: stdlib, no dependency. Verbose, no auto-completion, no rich help.
- **Fire**: Minimal code. Too magical, poor help text, no validation.

**Why Typer:** Type-hint-driven API matches our Pydantic-heavy codebase. Auto-generated `--help`. Rich terminal output via integration with `rich`. Click compatibility means all Click plugins work. Less boilerplate than Click for the same functionality.

### ADR-002: Google Ads Official Python SDK

**Decision:** Use `google-ads` Python SDK (official) for all Google Ads API interactions.

**Alternatives considered:**
- **Raw REST API via httpx**: Full control. Complex auth handling, no GAQL support, manual pagination.
- **google-api-python-client**: Generic Google API client. No GAQL, poor Ads-specific typing.

**Why google-ads SDK:** Handles OAuth token refresh automatically. Native GAQL (Google Ads Query Language) support. Proper typing for Ads resources. MCC traversal built-in. Maintained by Google.

### ADR-003: OAuth Desktop Application Flow

**Decision:** Use OAuth 2.0 Desktop Application flow (installed app) with localhost redirect.

**Alternatives considered:**
- **Service account**: No user consent needed. Cannot access Google Ads API (not supported for Ads).
- **Web server flow**: Standard OAuth. Requires running a web server, overkill for CLI.
- **Device code flow**: Works on headless. Poor UX, Google Ads API support uncertain.

**Why Desktop flow:** Standard for CLI tools accessing Google APIs. Opens browser for consent, catches callback on `localhost:8080`. Google Ads API fully supports this flow. No persistent server needed.

### ADR-004: Keyring for Token Storage

**Decision:** Use `keyring` library for credential storage with `cryptography` (Fernet) fallback.

**Alternatives considered:**
- **Plain file**: Simple. Insecure — tokens in plaintext.
- **cryptography only**: Portable. Requires managing an encryption key.
- **OS keychain only**: Secure. Not available on all platforms/environments.

**Why keyring with fallback:** `keyring` uses Windows Credential Locker (our primary platform), macOS Keychain, or Linux Secret Service. Falls back to encrypted file via Fernet when no system keyring is available. Best of both worlds.

### ADR-005: Modular Monolith Architecture

**Decision:** Keep single-package modular monolith, add `cli/` and `auth/` modules.

**Alternatives considered:**
- **Microservices**: Separate auth, scraping, generation services. Overkill for single operator.
- **Plugin architecture**: Loadable pipeline stages. Over-engineered for current scope.

**Why monolith:** Single operator, single machine. All modules share Pydantic models. No network boundaries needed. Easy to test, deploy, and debug. CLI is the only entry point.

### ADR-006: YAML for Configuration

**Decision:** Use YAML for `~/.sem-master/config.yaml` and per-client config overrides.

**Alternatives considered:**
- **TOML**: Python 3.11+ has tomllib. Write support requires extra library.
- **JSON**: Universal. No comments, verbose for humans.
- **INI**: stdlib support. No nested structures.

**Why YAML:** Supports comments (important for self-documenting config). Nested structures for client overrides. `pyyaml` is battle-tested. More readable than TOML for complex config.

---

## 4. Tech Stack

### Core (unchanged)
| Component | Library | Version | Purpose |
|-----------|---------|---------|---------|
| Runtime | Python | ≥3.11 | Language runtime |
| Models | pydantic | ≥2.5 | Data validation, serialization |
| Browser automation | playwright | ≥1.40 | Site crawling, transparency scraping |
| HTTP client | httpx | ≥0.25 | API calls, scraping |
| HTML parsing | beautifulsoup4 | ≥4.12 | Page content extraction |
| Swedish NLP | simplemma | ≥1.1 | Compound word splitting |
| Spreadsheets | openpyxl | ≥3.1 | XLSX keyword reports |
| DataFrames | pandas | ≥2.1 | Data manipulation |
| PDF generation | markdown-pdf | ≥1.13 | Strategy report PDFs |
| PDF reading | pypdf | ≥3.17 | Brand guide extraction |
| Environment | python-dotenv | ≥1.0 | .env loading for API keys |

### New dependencies (v2.0)
| Component | Library | Version | Purpose |
|-----------|---------|---------|---------|
| CLI framework | typer | ≥0.12 | Command-line interface |
| Terminal UI | rich | ≥13.0 | Colored output, tables, progress |
| Google Ads API | google-ads | ≥25.0 | Ads API (Keyword Planner, campaigns, accounts) |
| Google OAuth | google-auth-oauthlib | ≥1.2 | OAuth 2.0 desktop flow |
| Google Auth | google-auth | ≥2.28 | Credential management, token refresh |
| Config | pyyaml | ≥6.0 | YAML config files |
| Credentials | keyring | ≥25.0 | OS-native credential storage |
| Encryption | cryptography | ≥42.0 | Fernet fallback for token encryption |

### Removed dependencies
| Library | Reason |
|---------|--------|
| spacy | Listed in requirements but unused — simplemma handles all Swedish NLP |
| pyenchant | Unavailable on Windows, simplemma handles compound splitting alone |

---

## 5. Project Structure

```
D:/Kod Projekt/SEM Master/
├── src/
│   ├── __init__.py
│   ├── cli/                              # NEW — CLI entry points
│   │   ├── __init__.py
│   │   ├── app.py                        # Typer app root, registers all command groups
│   │   ├── auth_commands.py              # sem auth login|status|logout
│   │   ├── accounts_commands.py          # sem accounts list|add|remove|switch|info
│   │   ├── pipeline_commands.py          # sem pipeline run|status
│   │   ├── intake_commands.py            # sem intake <client>
│   │   ├── research_commands.py          # sem research <client>
│   │   ├── competitors_commands.py       # sem competitors <client>
│   │   ├── keywords_commands.py          # sem keywords <client>
│   │   ├── campaign_commands.py          # sem campaign <client>
│   │   ├── export_commands.py            # sem export <client>
│   │   ├── report_commands.py            # sem report <client>
│   │   ├── validate_commands.py          # sem validate <client>
│   │   ├── audit_commands.py             # sem audit <client>
│   │   ├── template_commands.py          # sem templates list|save|load|delete
│   │   └── config_commands.py            # sem config show|set|edit
│   ├── auth/                             # NEW — OAuth & credential management
│   │   ├── __init__.py
│   │   ├── oauth.py                      # OAuth 2.0 desktop flow, token exchange
│   │   ├── credentials.py               # Token storage (keyring + Fernet fallback)
│   │   ├── google_ads_auth.py            # Google Ads client factory with OAuth credentials
│   │   └── token_refresh.py             # Auto-refresh logic, expiry detection
│   ├── accounts/                         # NEW — Client account management
│   │   ├── __init__.py
│   │   ├── manager.py                    # Account CRUD, MCC linking, active client context
│   │   ├── config.py                     # Per-client config (budget, industry, brand voice)
│   │   └── state.py                      # Pipeline state machine per client
│   ├── templates/                        # NEW — Campaign template system
│   │   ├── __init__.py
│   │   ├── manager.py                    # Save, load, list, delete templates
│   │   └── adapter.py                    # Apply template to new client context
│   ├── audit/                            # NEW — Live campaign audit
│   │   ├── __init__.py
│   │   ├── fetcher.py                    # Pull live campaign data from Google Ads
│   │   └── comparator.py                # Diff live vs recommended campaigns
│   ├── models/                           # MODIFIED — add account models
│   │   ├── __init__.py
│   │   ├── client.py                     # ClientProfile (add google_ads_customer_id field)
│   │   ├── campaign.py                   # Campaign, AdGroup, Keyword, RSA (unchanged)
│   │   ├── competitor.py                 # CompetitorProfile, TransparencyAd (unchanged)
│   │   ├── research.py                   # DigitalPresence, SiteCrawl, Review (unchanged)
│   │   ├── account.py                    # NEW — ManagedAccount, AccountConfig
│   │   └── template.py                   # NEW — CampaignTemplate model
│   ├── scrapers/                         # UNCHANGED
│   │   ├── __init__.py
│   │   ├── site_crawler.py
│   │   ├── gbp_scraper.py
│   │   ├── review_scraper.py
│   │   ├── social_scraper.py
│   │   └── transparency_scraper.py
│   ├── apis/                             # MODIFIED — replace google_ads.py stub
│   │   ├── __init__.py
│   │   ├── google_ads.py                 # REWRITTEN — uses google-ads SDK + OAuth
│   │   ├── spyfu_client.py              # Unchanged
│   │   └── valueserp_client.py          # Unchanged
│   ├── analysis/                         # UNCHANGED
│   │   ├── __init__.py
│   │   ├── site_analyzer.py
│   │   ├── brand_analyzer.py
│   │   └── competitor_analyzer.py
│   ├── generators/                       # UNCHANGED
│   │   ├── __init__.py
│   │   ├── keyword_generator.py
│   │   ├── ad_copy_generator.py
│   │   ├── campaign_builder.py
│   │   ├── csv_exporter.py
│   │   ├── report_generator.py
│   │   └── pdf_generator.py
│   └── utils/                            # MODIFIED — add config_manager
│       ├── __init__.py
│       ├── config.py                     # MODIFIED — merge with global config loading
│       ├── config_manager.py             # NEW — ~/.sem-master/config.yaml management
│       ├── swedish_nlp.py               # Unchanged
│       └── pdf_reader.py               # Unchanged
├── data/                                 # UNCHANGED
│   ├── schemas/
│   ├── swedish/
│   └── templates/
├── clients/                              # UNCHANGED structure, enhanced content
├── scripts/
│   ├── validate_campaign.py             # Unchanged
│   └── setup_google_cloud.py            # NEW — interactive Google Cloud setup guide
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # MODIFIED — add auth fixtures, mock credentials
│   ├── test_models.py                   # Unchanged
│   ├── test_keyword_generator.py        # Unchanged (or from untracked)
│   ├── test_ad_copy_generator.py        # Unchanged (or from untracked)
│   ├── test_campaign_builder.py         # Unchanged (or from untracked)
│   ├── test_csv_exporter.py             # Unchanged
│   ├── test_report_generator.py         # Unchanged (or from untracked)
│   ├── test_swedish_nlp.py              # Unchanged
│   ├── test_data_files.py              # Unchanged
│   ├── test_integration.py             # Unchanged
│   ├── test_auth.py                     # NEW — OAuth flow, token storage, refresh
│   ├── test_accounts.py                # NEW — Account CRUD, MCC linking
│   ├── test_cli.py                     # NEW — CLI commands via CliRunner
│   ├── test_audit.py                   # NEW — Audit fetcher, comparator
│   ├── test_templates.py              # NEW — Template save/load/apply
│   └── test_pipeline_dry_run.py        # NEW — End-to-end dry-run pipeline
├── pyproject.toml                       # MODIFIED — add new deps, entry point
├── requirements.txt                     # MODIFIED — add new deps
├── .env.example                         # MODIFIED — update credential docs
├── CLAUDE.md                            # MODIFIED — update for v2.0
├── ARCHITECTURE.md                      # THIS FILE
└── README.md
```

### External directory: `~/.sem-master/`
```
~/.sem-master/
├── config.yaml                          # Global operator config
├── credentials/
│   ├── client_secret.json               # OAuth client credentials (from Google Cloud Console)
│   └── tokens.json                      # Encrypted refresh/access tokens (Fernet fallback)
│   (Primary storage: OS keyring via keyring library)
└── templates/
    └── {template-name}.json             # Saved campaign templates
```

---

## 6. Module & Function Definitions

### 6.1 CLI — `src/cli/app.py`

**Purpose:** Root Typer application that registers all command groups and provides the `sem` entry point.

```
create_app() -> typer.Typer
  Purpose: Build and return the Typer app with all registered command groups
  Returns: Configured Typer instance
  Side effects: None
  Error cases: None (construction only)
  Called by: pyproject.toml entry point, tests
  Calls: All *_commands modules to register subcommands

version_callback(value: bool) -> None
  Purpose: Print version and exit when --version is passed
  Called by: Typer framework

main() -> None
  Purpose: Entry point invoked by `sem` command
  Called by: Shell (pyproject.toml [project.scripts])
  Calls: create_app()
```

### 6.2 CLI — `src/cli/auth_commands.py`

**Purpose:** Commands for OAuth authentication and token management.

```
login(force: bool = False) -> None
  Purpose: Run OAuth 2.0 desktop flow — opens browser, waits for consent, stores tokens
  Params:
    - force: If True, re-authenticate even if valid tokens exist
  Returns: None (prints status to terminal)
  Side effects: Stores tokens via credentials.store_tokens()
  Error cases:
    - No client_secret.json found → print setup instructions
    - User cancels browser consent → AuthError
    - Network error during token exchange → AuthError
  Called by: CLI (`sem auth login`)
  Calls: oauth.run_oauth_flow(), credentials.store_tokens()

status() -> None
  Purpose: Display current auth status — token validity, linked MCC, expiry time
  Returns: None (prints rich table to terminal)
  Side effects: None
  Error cases:
    - No tokens found → print "Not authenticated"
  Called by: CLI (`sem auth status`)
  Calls: credentials.load_tokens(), token_refresh.check_expiry()

logout() -> None
  Purpose: Revoke tokens and clear stored credentials
  Returns: None
  Side effects: Removes tokens from keyring/file
  Error cases: None (idempotent)
  Called by: CLI (`sem auth logout`)
  Calls: credentials.clear_tokens()

setup() -> None
  Purpose: Interactive guide for Google Cloud project setup — prints step-by-step instructions
  Returns: None (prints guide to terminal)
  Side effects: None
  Called by: CLI (`sem auth setup`)
  Calls: None
```

### 6.3 CLI — `src/cli/accounts_commands.py`

**Purpose:** Manage client Google Ads accounts under the MCC umbrella.

```
list() -> None
  Purpose: List all managed client accounts with status
  Returns: None (prints rich table: name, customer_id, industry, budget, pipeline_stage)
  Side effects: None
  Called by: CLI (`sem accounts list`)
  Calls: accounts.manager.list_accounts()

add(name: str, customer_id: str, industry: str = None, budget: int = None) -> None
  Purpose: Register a new client account and create client directory
  Params:
    - name: Client slug (kebab-case, used as directory name)
    - customer_id: Google Ads Customer ID (XXX-XXX-XXXX format)
    - industry: Optional industry key from industry_keywords.json
    - budget: Optional monthly budget in SEK
  Returns: None
  Side effects: Creates clients/{name}/ directory tree, writes account config
  Error cases:
    - Client name already exists → ConflictError
    - Invalid customer_id format → ValidationError
    - Customer ID not accessible under MCC → AuthError (checked via API)
  Called by: CLI (`sem accounts add`)
  Calls: accounts.manager.create_account(), google_ads_auth.verify_account_access()

remove(name: str, archive: bool = True) -> None
  Purpose: Remove a client account (optionally archive data)
  Params:
    - name: Client slug
    - archive: If True, move to clients/_archived/{name}/ instead of deleting
  Returns: None
  Side effects: Moves or deletes client directory
  Error cases:
    - Client not found → NotFoundError
  Called by: CLI (`sem accounts remove`)
  Calls: accounts.manager.remove_account()

switch(name: str) -> None
  Purpose: Set active client context (used as default for pipeline commands)
  Params:
    - name: Client slug
  Returns: None
  Side effects: Updates ~/.sem-master/config.yaml active_client field
  Called by: CLI (`sem accounts switch`)
  Calls: accounts.manager.set_active_client()

info(name: str = None) -> None
  Purpose: Show detailed info for a client (defaults to active client)
  Returns: None (prints rich panel with all client details)
  Called by: CLI (`sem accounts info`)
  Calls: accounts.manager.get_account(), accounts.state.get_pipeline_state()
```

### 6.4 CLI — `src/cli/pipeline_commands.py`

**Purpose:** Run full or partial pipeline for a client.

```
run(client: str = None, dry_run: bool = False, from_stage: str = None, to_stage: str = None) -> None
  Purpose: Execute pipeline stages sequentially for a client
  Params:
    - client: Client slug (defaults to active client)
    - dry_run: If True, skip all API calls, use mock/cached data
    - from_stage: Start from this stage (default: first incomplete)
    - to_stage: Stop after this stage (default: last stage)
  Returns: None (prints progress per stage)
  Side effects: Creates/updates all client data files, updates pipeline state
  Error cases:
    - Client not found → NotFoundError
    - No auth tokens (non-dry-run) → AuthError
    - Stage dependency not met → ValidationError
  Called by: CLI (`sem pipeline run`)
  Calls: Each stage command in sequence, accounts.state.update_state()

status(client: str = None) -> None
  Purpose: Show pipeline progress for a client
  Returns: None (prints stage checklist with completion status)
  Called by: CLI (`sem pipeline status`)
  Calls: accounts.state.get_pipeline_state()
```

### 6.5 CLI — Stage Commands (intake, research, competitors, keywords, campaign, validate, export, report)

Each stage command follows the same pattern. Documenting the shared interface:

```
# Pattern for each stage command (intake_commands.py, research_commands.py, etc.)

<stage>(client: str = None, dry_run: bool = False) -> None
  Purpose: Execute the {stage} phase for a client
  Params:
    - client: Client slug (defaults to active client)
    - dry_run: Skip API calls, use mock/cached data
  Returns: None (prints stage output and status)
  Side effects: Writes stage output to clients/{name}/{stage}/
  Error cases:
    - Prerequisite stages not completed → ValidationError with message
    - Client not found → NotFoundError
  Called by: CLI (`sem {stage} <client>`), pipeline_commands.run()
  Calls: Corresponding generator/scraper/API functions, accounts.state.update_state()
```

**Stage-specific details:**

| Stage | Prerequisite | Calls | Output Directory |
|-------|-------------|-------|-----------------|
| `intake` | None | Interactive prompts (typer.prompt) | `clients/{name}/intake/` |
| `research` | intake | scrapers.site_crawler, gbp, reviews, social | `clients/{name}/research/` |
| `competitors` | intake | scrapers.transparency, apis.spyfu, apis.valueserp | `clients/{name}/competitors/` |
| `keywords` | intake, research | generators.keyword_generator, apis.google_ads | `clients/{name}/keywords/` |
| `campaign` | keywords | generators.campaign_builder, ad_copy_generator | `clients/{name}/campaigns/` |
| `validate` | campaign | scripts.validate_campaign | (prints to terminal) |
| `export` | campaign | generators.csv_exporter | `clients/{name}/exports/` |
| `report` | campaign | generators.report_generator, pdf_generator | `clients/{name}/reports/` |

### 6.6 CLI — `src/cli/audit_commands.py`

**Purpose:** Pull live campaign data and compare against recommendations.

```
audit(client: str = None, campaign_id: str = None) -> None
  Purpose: Fetch live campaign data and diff against generated recommendations
  Params:
    - client: Client slug
    - campaign_id: Optional specific campaign to audit (default: all)
  Returns: None (prints diff table to terminal)
  Side effects: Writes audit report to clients/{name}/audits/
  Error cases:
    - No auth tokens → AuthError
    - No generated campaign to compare → ValidationError
    - Google Ads API error → ApiError
  Called by: CLI (`sem audit`)
  Calls: audit.fetcher.fetch_live_campaigns(), audit.comparator.compare()
```

### 6.7 CLI — `src/cli/template_commands.py`

**Purpose:** Save and reuse winning campaign structures.

```
list() -> None
  Purpose: List saved campaign templates
  Called by: CLI (`sem templates list`)
  Calls: templates.manager.list_templates()

save(name: str, client: str = None, description: str = None) -> None
  Purpose: Save current client's campaign as a reusable template
  Params:
    - name: Template name (kebab-case)
    - client: Source client slug
    - description: Optional description
  Side effects: Writes template to ~/.sem-master/templates/{name}.json
  Called by: CLI (`sem templates save`)
  Calls: templates.manager.save_template()

load(name: str, client: str = None) -> None
  Purpose: Apply a template to a client, adapting copy/keywords to their context
  Params:
    - name: Template name
    - client: Target client slug
  Side effects: Writes adapted campaign to clients/{name}/campaigns/
  Called by: CLI (`sem templates load`)
  Calls: templates.manager.load_template(), templates.adapter.apply_template()

delete(name: str) -> None
  Purpose: Delete a saved template
  Called by: CLI (`sem templates delete`)
  Calls: templates.manager.delete_template()
```

### 6.8 CLI — `src/cli/config_commands.py`

**Purpose:** View and modify global configuration.

```
show() -> None
  Purpose: Display current configuration (redacting secrets)
  Called by: CLI (`sem config show`)
  Calls: utils.config_manager.load_config()

set(key: str, value: str) -> None
  Purpose: Set a config value using dot notation (e.g., "defaults.industry=tandvård")
  Called by: CLI (`sem config set`)
  Calls: utils.config_manager.set_value()

edit() -> None
  Purpose: Open config.yaml in $EDITOR
  Called by: CLI (`sem config edit`)
  Calls: subprocess (opens editor)
```

### 6.9 Auth — `src/auth/oauth.py`

**Purpose:** Handle the OAuth 2.0 desktop application flow for Google Ads API.

```
run_oauth_flow(client_secret_path: Path, scopes: list[str], port: int = 8080) -> Credentials
  Purpose: Execute full OAuth 2.0 flow — opens browser, starts localhost server, exchanges code for tokens
  Params:
    - client_secret_path: Path to client_secret.json downloaded from Google Cloud Console
    - scopes: OAuth scopes (default: ["https://www.googleapis.com/auth/adwords"])
    - port: Localhost port for redirect URI
  Returns: google.oauth2.credentials.Credentials object with access_token and refresh_token
  Side effects: Opens browser, starts temporary HTTP server on localhost:{port}
  Error cases:
    - client_secret.json not found → FileNotFoundError
    - User denies consent → AuthError
    - Port already in use → OSError (retry with port+1, up to 3 attempts)
    - Network error → AuthError
  Called by: cli.auth_commands.login()
  Calls: google_auth_oauthlib.flow.InstalledAppFlow

get_oauth_scopes() -> list[str]
  Purpose: Return the required OAuth scopes for Google Ads API
  Returns: ["https://www.googleapis.com/auth/adwords"]
  Called by: run_oauth_flow()
```

### 6.10 Auth — `src/auth/credentials.py`

**Purpose:** Securely store and retrieve OAuth tokens using OS keyring with Fernet fallback.

```
store_tokens(credentials: Credentials) -> None
  Purpose: Persist OAuth tokens to secure storage
  Params:
    - credentials: Google OAuth Credentials object
  Side effects: Stores in OS keyring (primary) or encrypted file (fallback)
  Error cases:
    - Keyring unavailable + write permission error → StorageError
  Called by: auth_commands.login(), token_refresh.refresh_token()
  Calls: keyring.set_password() or _store_encrypted_file()

load_tokens() -> Optional[Credentials]
  Purpose: Retrieve stored OAuth tokens
  Returns: Credentials object if found, None if no tokens stored
  Side effects: None
  Error cases:
    - Corrupted token data → None (treat as not authenticated)
  Called by: google_ads_auth.get_client(), auth_commands.status()
  Calls: keyring.get_password() or _load_encrypted_file()

clear_tokens() -> None
  Purpose: Remove all stored tokens
  Side effects: Deletes from keyring and encrypted file
  Called by: auth_commands.logout()
  Calls: keyring.delete_password(), Path.unlink()

_store_encrypted_file(token_data: dict, path: Path) -> None
  Purpose: Fernet-encrypt and write tokens to file (fallback when keyring unavailable)
  Params:
    - token_data: Dict with access_token, refresh_token, expiry, client_id, client_secret
    - path: File path (~/.sem-master/credentials/tokens.json)
  Called by: store_tokens()

_load_encrypted_file(path: Path) -> Optional[dict]
  Purpose: Read and decrypt Fernet-encrypted token file
  Called by: load_tokens()

_get_or_create_key() -> bytes
  Purpose: Get or generate Fernet encryption key (stored in keyring or derived from machine ID)
  Returns: 32-byte Fernet key
  Called by: _store_encrypted_file(), _load_encrypted_file()
```

### 6.11 Auth — `src/auth/google_ads_auth.py`

**Purpose:** Factory for authenticated Google Ads API client instances.

```
get_google_ads_client(customer_id: str = None) -> GoogleAdsClient
  Purpose: Create an authenticated Google Ads client for API calls
  Params:
    - customer_id: Optional customer ID to operate on (default: MCC login customer)
  Returns: google.ads.googleads.client.GoogleAdsClient instance
  Side effects: May trigger token refresh
  Error cases:
    - No stored tokens → AuthError("Run 'sem auth login' first")
    - Token refresh fails → AuthError("Re-authenticate with 'sem auth login'")
    - Invalid developer token → AuthError
  Called by: apis.google_ads.*, audit.fetcher.*, accounts_commands.add()
  Calls: credentials.load_tokens(), token_refresh.ensure_valid_token()

build_google_ads_config(credentials: Credentials, developer_token: str, login_customer_id: str) -> dict
  Purpose: Build the config dict required by google-ads SDK
  Returns: Dict compatible with GoogleAdsClient.load_from_dict()
  Called by: get_google_ads_client()
```

### 6.12 Auth — `src/auth/token_refresh.py`

**Purpose:** Handle automatic token refresh and expiry detection.

```
ensure_valid_token(credentials: Credentials) -> Credentials
  Purpose: Check if token is valid; refresh if expired; raise if refresh fails
  Params:
    - credentials: Current Credentials object
  Returns: Valid Credentials (possibly refreshed)
  Side effects: Updates stored tokens if refreshed
  Error cases:
    - Refresh token revoked → AuthError
    - Network error during refresh → AuthError
  Called by: google_ads_auth.get_google_ads_client()
  Calls: credentials.store_tokens() (if refreshed)

check_expiry(credentials: Credentials) -> dict
  Purpose: Return expiry info without refreshing
  Returns: {"valid": bool, "expires_at": datetime, "minutes_remaining": int}
  Called by: auth_commands.status()
```

### 6.13 Accounts — `src/accounts/manager.py`

**Purpose:** Client account CRUD operations and active client context management.

```
create_account(name: str, customer_id: str, industry: str = None, budget_sek: int = None) -> ManagedAccount
  Purpose: Register a new client and create directory structure
  Params:
    - name: Client slug (kebab-case)
    - customer_id: Google Ads Customer ID
    - industry: Industry key for keyword seeds
    - budget_sek: Monthly budget in SEK
  Returns: ManagedAccount model
  Side effects: Creates clients/{name}/ with subdirectories, writes account.yaml
  Error cases:
    - Name already exists → ConflictError
    - Invalid customer_id format → ValidationError
  Called by: accounts_commands.add()
  Calls: accounts.config.write_account_config(), accounts.state.initialize_state()

list_accounts() -> list[ManagedAccount]
  Purpose: List all registered client accounts
  Returns: List of ManagedAccount models with pipeline state
  Called by: accounts_commands.list()
  Calls: accounts.config.read_account_config() for each client dir

get_account(name: str) -> ManagedAccount
  Purpose: Get a single account by name
  Returns: ManagedAccount model
  Error cases:
    - Not found → NotFoundError
  Called by: accounts_commands.info(), all stage commands
  Calls: accounts.config.read_account_config()

remove_account(name: str, archive: bool = True) -> None
  Purpose: Remove or archive a client account
  Side effects: Moves to clients/_archived/ or deletes
  Called by: accounts_commands.remove()

set_active_client(name: str) -> None
  Purpose: Update config.yaml with active client
  Side effects: Writes to ~/.sem-master/config.yaml
  Called by: accounts_commands.switch()
  Calls: utils.config_manager.set_value()

get_active_client() -> Optional[str]
  Purpose: Get currently active client slug
  Returns: Client name or None
  Called by: All CLI commands that default to active client
  Calls: utils.config_manager.load_config()
```

### 6.14 Accounts — `src/accounts/config.py`

**Purpose:** Per-client configuration management.

```
write_account_config(client_dir: Path, account: ManagedAccount) -> None
  Purpose: Write account.yaml to client directory
  Called by: accounts.manager.create_account()

read_account_config(client_dir: Path) -> ManagedAccount
  Purpose: Read account.yaml from client directory
  Called by: accounts.manager.get_account(), list_accounts()

update_account_config(client_dir: Path, updates: dict) -> None
  Purpose: Merge updates into existing account.yaml
  Called by: Various CLI commands that modify client settings
```

### 6.15 Accounts — `src/accounts/state.py`

**Purpose:** Pipeline state machine — tracks which stages are complete for each client.

```
PIPELINE_STAGES = ["intake", "research", "competitors", "keywords", "campaign", "validate", "export", "report"]

initialize_state(client_dir: Path) -> dict
  Purpose: Create initial workflow_state.json with all stages pending
  Returns: State dict
  Side effects: Writes workflow_state.json
  Called by: accounts.manager.create_account()

get_pipeline_state(client_dir: Path) -> dict
  Purpose: Read current pipeline state
  Returns: Dict mapping stage names to status (pending/in_progress/completed/failed)
  Called by: pipeline_commands.status(), accounts_commands.info()

update_state(client_dir: Path, stage: str, status: str, metadata: dict = None) -> None
  Purpose: Update a stage's status with optional metadata (timestamp, duration, error)
  Called by: All stage commands after execution

check_prerequisites(client_dir: Path, stage: str) -> tuple[bool, list[str]]
  Purpose: Verify prerequisite stages are completed
  Returns: (ok, list of missing prerequisites)
  Called by: All stage commands before execution

get_next_stage(client_dir: Path) -> Optional[str]
  Purpose: Return the first incomplete stage
  Returns: Stage name or None if all complete
  Called by: pipeline_commands.run()
```

### 6.16 Templates — `src/templates/manager.py`

**Purpose:** Save and manage reusable campaign templates.

```
save_template(name: str, campaign_plan: CampaignPlan, client: ClientProfile, description: str = None) -> Path
  Purpose: Extract campaign structure into a reusable template, stripping client-specific data
  Returns: Path to saved template file
  Side effects: Writes to ~/.sem-master/templates/{name}.json
  Called by: template_commands.save()
  Calls: _strip_client_specifics()

load_template(name: str) -> CampaignTemplate
  Purpose: Load a saved template
  Returns: CampaignTemplate model
  Error cases: NotFoundError if template doesn't exist
  Called by: template_commands.load()

list_templates() -> list[dict]
  Purpose: List all saved templates with name, description, creation date
  Returns: List of template summaries
  Called by: template_commands.list()

delete_template(name: str) -> None
  Purpose: Delete a template file
  Called by: template_commands.delete()
```

### 6.17 Templates — `src/templates/adapter.py`

**Purpose:** Apply a template to a new client context, replacing placeholders.

```
apply_template(template: CampaignTemplate, client: ClientProfile, keyword_groups: dict) -> CampaignPlan
  Purpose: Adapt a template's structure to a specific client — replace brand names, URLs, keywords, geo targets
  Params:
    - template: Source template
    - client: Target client profile
    - keyword_groups: Client's keyword groups (from keyword stage)
  Returns: New CampaignPlan adapted for the client
  Side effects: None
  Error cases:
    - Template requires more ad groups than client has keyword groups → ValidationError
  Called by: template_commands.load()
  Calls: generators.ad_copy_generator (for new headlines/descriptions)
```

### 6.18 Audit — `src/audit/fetcher.py`

**Purpose:** Pull live campaign data from Google Ads API.

```
fetch_live_campaigns(customer_id: str, campaign_ids: list[str] = None) -> list[dict]
  Purpose: Query Google Ads API for current campaign state
  Params:
    - customer_id: Google Ads Customer ID
    - campaign_ids: Optional filter (default: all campaigns)
  Returns: List of campaign dicts with structure, keywords, ads, performance metrics
  Side effects: API call to Google Ads
  Error cases:
    - AuthError if tokens invalid
    - ApiError if account access denied
  Called by: audit_commands.audit()
  Calls: google_ads_auth.get_google_ads_client()

fetch_keyword_performance(customer_id: str, date_range: str = "LAST_30_DAYS") -> list[dict]
  Purpose: Get keyword-level performance data
  Returns: List of dicts with keyword, impressions, clicks, ctr, avg_cpc, conversions
  Called by: audit_commands.audit()
  Calls: google_ads_auth.get_google_ads_client()
```

### 6.19 Audit — `src/audit/comparator.py`

**Purpose:** Compare live campaign data against generated recommendations.

```
compare(live_campaigns: list[dict], recommended_plan: CampaignPlan) -> dict
  Purpose: Produce a structured diff between live and recommended campaigns
  Returns: Dict with:
    - missing_campaigns: campaigns in recommendation not in live
    - extra_campaigns: campaigns live but not in recommendation
    - keyword_gaps: recommended keywords not in live campaigns
    - keyword_waste: live keywords not in recommendation (potential waste)
    - ad_copy_diffs: headlines/descriptions that differ
    - budget_diffs: budget allocation differences
    - bid_strategy_diffs: bid strategy differences
  Called by: audit_commands.audit()

format_audit_report(diff: dict, client_name: str) -> str
  Purpose: Format the diff as a readable terminal report and markdown file
  Returns: Markdown string
  Called by: audit_commands.audit()
```

### 6.20 APIs — `src/apis/google_ads.py` (REWRITTEN)

**Purpose:** Google Ads API client using official SDK with OAuth authentication.

```
class GoogleAdsService:
  def __init__(self, customer_id: str):
    Purpose: Initialize service for a specific customer account
    Calls: google_ads_auth.get_google_ads_client()

  async get_keyword_ideas(self, seeds: list[str], geo_id: int = 2752, language_id: int = 1053, page_size: int = 1000) -> list[dict]
    Purpose: Get keyword suggestions from Keyword Planner
    Returns: List of dicts with text, avg_monthly_searches, competition, avg_cpc_micros, competition_index
    Error cases: AuthError, ApiError, QuotaExceededError
    Called by: keywords_commands, keyword_generator

  async get_search_volumes(self, keywords: list[str], geo_id: int = 2752, language_id: int = 1053) -> list[dict]
    Purpose: Get search volume and CPC data for specific keywords
    Returns: List of dicts with keyword, monthly_searches, avg_cpc_sek, competition
    Called by: keywords_commands

  async get_campaigns(self, include_removed: bool = False) -> list[dict]
    Purpose: Fetch all campaigns from the account
    Returns: List of campaign dicts
    Called by: audit.fetcher

  async get_ad_groups(self, campaign_id: str) -> list[dict]
    Purpose: Fetch ad groups for a campaign
    Called by: audit.fetcher

  async get_keywords(self, ad_group_id: str = None) -> list[dict]
    Purpose: Fetch keywords (optionally filtered by ad group)
    Called by: audit.fetcher

  async get_ads(self, ad_group_id: str = None) -> list[dict]
    Purpose: Fetch responsive search ads
    Called by: audit.fetcher

  async get_account_info(self) -> dict
    Purpose: Get basic account info (name, currency, timezone)
    Called by: accounts_commands.add() (for verification)

class DryRunGoogleAdsService(GoogleAdsService):
  Purpose: Mock service that returns synthetic data for dry-run mode
  Overrides: All async methods return realistic but fake data
  Called by: Any command with --dry-run flag
```

### 6.21 Utils — `src/utils/config_manager.py` (NEW)

**Purpose:** Manage the global `~/.sem-master/config.yaml` configuration file.

```
CONFIG_DIR = Path.home() / ".sem-master"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
  "version": "2.0",
  "active_client": None,
  "mcc_customer_id": None,
  "developer_token": None,
  "defaults": {
    "dry_run": False,
    "industry": None,
    "geo_targets": [{"name": "Sverige", "id": 2752}],
    "language_id": 1053,
    "ad_schedule": "07:00-21:00"
  },
  "api_keys": {
    "spyfu": None,
    "valueserp": None,
    "anthropic": None
  }
}

ensure_config_dir() -> Path
  Purpose: Create ~/.sem-master/ and subdirectories if they don't exist
  Returns: Path to config directory
  Side effects: Creates directories
  Called by: All config operations

load_config() -> dict
  Purpose: Load config.yaml, creating with defaults if missing
  Returns: Config dict
  Called by: Nearly everything — auth, accounts, pipeline, CLI

save_config(config: dict) -> None
  Purpose: Write config dict to config.yaml
  Called by: set_value(), auth_commands (to store MCC ID)

get_value(key: str) -> Any
  Purpose: Get a config value by dot-notation key (e.g., "defaults.industry")
  Called by: config_commands.show(), various modules

set_value(key: str, value: Any) -> None
  Purpose: Set a config value by dot-notation key
  Called by: config_commands.set(), accounts.manager.set_active_client()
```

### 6.22 Utils — `src/utils/config.py` (MODIFIED)

**Purpose:** Merge existing Settings model with new config_manager. Keep `.env` loading for API keys, delegate to config_manager for everything else.

```
class Settings(BaseModel):
  # REMOVED: google_ads_developer_token, google_ads_client_id, google_ads_client_secret, google_ads_refresh_token
  # KEPT: spyfu_api_key, anthropic_api_key, valueserp_api_key (loaded from .env)
  # ADDED: loaded from config.yaml via config_manager
  spyfu_api_key: Optional[str]
  valueserp_api_key: Optional[str]
  anthropic_api_key: Optional[str]

get_settings() -> Settings
  Purpose: Load settings from .env (API keys only, OAuth handled by auth module)
  MODIFIED: No longer loads Google Ads credentials from .env
  Called by: apis.spyfu_client, apis.valueserp_client, generators (for Anthropic)
```

### 6.23 Scripts — `scripts/setup_google_cloud.py` (NEW)

**Purpose:** Interactive script that walks through Google Cloud project setup.

```
main() -> None
  Purpose: Print step-by-step instructions for:
    1. Creating Google Cloud project
    2. Enabling Google Ads API
    3. Creating OAuth 2.0 Desktop App credentials
    4. Downloading client_secret.json
    5. Applying for Google Ads API developer token
    6. Setting up MCC account
    7. Running `sem auth login`
  Returns: None (prints to terminal with rich formatting)
  Called by: CLI or direct execution
```

---

## 7. Data Models

### 7.1 ManagedAccount (NEW) — `src/models/account.py`

| Field | Type | Constraints |
|-------|------|-------------|
| name | str | required, kebab-case, unique, regex `^[a-z0-9-]+$` |
| customer_id | str | required, format `XXX-XXX-XXXX`, @field_validator |
| display_name | str | required, human-readable business name |
| industry | Optional[str] | key from industry_keywords.json |
| monthly_budget_sek | Optional[int] | positive integer |
| brand_voice | Optional[str] | free text description |
| website_url | Optional[str] | valid URL |
| contact_email | Optional[str] | valid email |
| contact_name | Optional[str] | |
| notes | Optional[str] | free text |
| created_at | datetime | auto-generated |
| updated_at | datetime | auto-updated |

Relationships:
- ManagedAccount 1:1 ClientProfile (via name → clients/{name}/intake/intake.json)
- ManagedAccount 1:1 PipelineState (via name → clients/{name}/workflow_state.json)

Common queries:
- list_accounts() — dashboard listing
- get_account(name) — detail view, pipeline operations

### 7.2 CampaignTemplate (NEW) — `src/models/template.py`

| Field | Type | Constraints |
|-------|------|-------------|
| name | str | required, kebab-case |
| description | Optional[str] | |
| source_client | str | original client name |
| source_industry | str | industry key |
| created_at | datetime | auto-generated |
| campaign_structures | list[dict] | campaign shapes without client-specific data |
| ad_group_patterns | list[dict] | ad group themes, keyword patterns |
| extension_patterns | dict | sitelink/callout patterns |
| budget_strategy | dict | budget allocation ratios, bid strategy rules |

Common queries:
- list_templates() — template browser
- load_template(name) — apply to new client

### 7.3 ClientProfile (MODIFIED) — `src/models/client.py`

**Added field:**

| Field | Type | Constraints |
|-------|------|-------------|
| google_ads_customer_id | Optional[str] | format `XXX-XXX-XXXX` |

All other fields unchanged.

### 7.4 Existing Models (UNCHANGED)

The following models remain exactly as-is:
- `AdHeadline` (max 30 chars), `AdDescription` (max 90 chars)
- `ResponsiveSearchAd`, `Keyword`, `AdGroup`, `Campaign`, `CampaignPlan`
- `Sitelink`, `Callout`, `StructuredSnippet`, `CallExtension`
- `CompetitorProfile`, `TransparencyAd`
- `CrawledPage`, `SiteCrawl`, `Review`, `SocialProfile`, `GoogleBusinessProfile`, `DigitalPresence`

---

## 8. Interface Contracts

### 8.1 CLI Command Tree

All interaction is via the `sem` CLI. No HTTP API. No web UI.

```
sem
├── auth
│   ├── setup                           # Print Google Cloud setup guide
│   ├── login [--force]                 # Run OAuth flow
│   ├── status                          # Show token info
│   └── logout                          # Clear tokens
├── accounts
│   ├── list                            # List all clients
│   ├── add <name> <customer-id> [--industry] [--budget]  # Register client
│   ├── remove <name> [--no-archive]    # Remove client
│   ├── switch <name>                   # Set active client
│   └── info [name]                     # Show client details
├── intake [client] [--dry-run]         # Client onboarding
├── research [client] [--dry-run]       # Scrape digital presence
├── competitors [client] [--dry-run]    # Competitor analysis
├── keywords [client] [--dry-run]       # Keyword research & grouping
├── campaign [client] [--dry-run]       # Build campaign structure
├── validate [client]                   # Run 11 validation checks
├── export [client] [--keywords-only]   # Generate CSV + XLSX
├── report [client] [--pdf] [--no-pdf]  # Generate strategy report
├── audit [client] [--campaign-id]      # Live vs recommended diff
├── pipeline
│   ├── run [client] [--dry-run] [--from] [--to]  # Run full/partial pipeline
│   └── status [client]                 # Show pipeline progress
├── templates
│   ├── list                            # List saved templates
│   ├── save <name> [client] [--description]  # Save campaign as template
│   ├── load <name> [client]            # Apply template to client
│   └── delete <name>                   # Delete template
├── config
│   ├── show                            # Display config
│   ├── set <key> <value>               # Set config value
│   └── edit                            # Open in editor
└── --version                           # Print version
```

### 8.2 CLI Command Contracts

#### `sem auth login`
```
Purpose: Authenticate with Google Ads API via OAuth 2.0
Auth: None (this establishes auth)
Input:
  --force: bool (default: False) — re-authenticate even if tokens valid
Flow:
  1. Check for ~/.sem-master/credentials/client_secret.json
  2. If missing → print "Run 'sem auth setup' first" and exit
  3. Start localhost:8080 server for callback
  4. Open browser to Google consent URL
  5. User grants consent → receive auth code
  6. Exchange code for access_token + refresh_token
  7. Store tokens via credentials.store_tokens()
  8. Verify by calling Google Ads API for account info
  9. Store MCC customer ID in config.yaml
Output:
  Success: "✓ Authenticated as {email}. MCC: {customer_id}"
  Error: "✗ Authentication failed: {reason}"
Maps to: auth_commands.login() → oauth.run_oauth_flow() → credentials.store_tokens()
```

#### `sem accounts add <name> <customer-id>`
```
Purpose: Register a new client account
Auth: Required (verifies account access under MCC)
Input:
  name: str — client slug
  customer_id: str — format XXX-XXX-XXXX
  --industry: str — industry key
  --budget: int — monthly budget SEK
Flow:
  1. Validate name (kebab-case, unique)
  2. Validate customer_id format
  3. Verify account accessible under MCC via Google Ads API
  4. Create clients/{name}/ directory tree
  5. Write account.yaml with config
  6. Initialize workflow_state.json
Output:
  Success: "✓ Added client '{name}' (Customer ID: {customer_id})"
  Error: Various (see error taxonomy)
Maps to: accounts_commands.add() → accounts.manager.create_account()
```

#### `sem pipeline run [client]`
```
Purpose: Execute full pipeline for a client
Auth: Required (unless --dry-run)
Input:
  client: str — defaults to active client
  --dry-run: bool — skip API calls
  --from: str — start stage (default: first incomplete)
  --to: str — stop stage (default: report)
Flow:
  1. Resolve client (explicit or active)
  2. Load pipeline state
  3. Determine start/end stages
  4. For each stage in order:
     a. Check prerequisites
     b. Print "Running {stage}..."
     c. Execute stage
     d. Update pipeline state
     e. Print "✓ {stage} complete"
  5. Print summary
Output:
  Progress: Stage-by-stage status updates with timing
  Success: "✓ Pipeline complete. Export at clients/{name}/exports/"
  Error: Stops at failed stage with error message
Maps to: pipeline_commands.run() → each stage command in sequence
```

#### `sem audit [client]`
```
Purpose: Compare live campaign data against generated recommendations
Auth: Required
Input:
  client: str — defaults to active client
  --campaign-id: str — specific campaign (default: all)
Flow:
  1. Verify campaign stage completed (has generated plan)
  2. Fetch live campaign data via Google Ads API
  3. Load generated campaign plan from clients/{name}/campaigns/
  4. Run comparator.compare()
  5. Print diff table to terminal
  6. Write audit report to clients/{name}/audits/
Output:
  Rich table showing: added/removed campaigns, keyword gaps, copy diffs, budget diffs
Maps to: audit_commands.audit() → fetcher.fetch_live_campaigns() → comparator.compare()
```

### 8.3 Internal Module Contracts

#### Auth → Google Ads API
```
Input: credentials.load_tokens() → Credentials
Output: google_ads_auth.get_google_ads_client() → GoogleAdsClient
Contract: All Google Ads API calls go through google_ads_auth.get_google_ads_client()
         Token refresh is transparent — callers never handle refresh manually
```

#### CLI → Accounts
```
Input: client name (str) or None (defaults to active)
Output: ManagedAccount model with all config
Contract: accounts.manager.get_account() resolves name → full account data
          accounts.manager.get_active_client() provides default when name is None
```

#### CLI → Pipeline Stage → Output
```
Input: ManagedAccount + dry_run flag
Output: JSON/files in clients/{name}/{stage}/
Contract: Each stage reads previous stage output, writes its own output
          Pipeline state updated atomically after stage completion
          Dry-run mode substitutes DryRunGoogleAdsService for real API calls
```

---

## 9. Data Flow Diagrams

### 9.1 Authentication Flow

```
User                    CLI                     OAuth Module              Google                    Credentials Store
  |                      |                          |                       |                            |
  |-- sem auth login --->|                          |                       |                            |
  |                      |-- check client_secret -->|                       |                            |
  |                      |                          |-- start localhost:8080 |                            |
  |                      |                          |-- open browser ------->|                            |
  |<----- browser opens -|                          |                       |                            |
  |-- grants consent --->|                          |                       |                            |
  |                      |                          |<-- auth code ---------|                            |
  |                      |                          |-- exchange code ------>|                            |
  |                      |                          |<-- tokens ------------|                            |
  |                      |                          |-- store_tokens() ---->|                            |
  |                      |<-- success --------------|                       |                     stored |
  |<-- "Authenticated" --|                          |                       |                            |
```

### 9.2 New Client Onboarding Flow

```
User                    CLI                    Accounts Manager          Google Ads API          File System
  |                      |                          |                       |                       |
  |-- sem accounts add ->|                          |                       |                       |
  |   "acme" "123-456-7890"                         |                       |                       |
  |                      |-- validate format ------>|                       |                       |
  |                      |-- verify access -------->|-- get_account_info -->|                       |
  |                      |                          |<-- account info ------|                       |
  |                      |-- create_account() ----->|                       |                       |
  |                      |                          |-- mkdir clients/acme/ |                       |
  |                      |                          |   ├── intake/         |                       |
  |                      |                          |   ├── research/       |                    written |
  |                      |                          |   └── ...             |                       |
  |                      |                          |-- write account.yaml  |                       |
  |                      |                          |-- init workflow_state |                       |
  |<-- "Added client" ---|                          |                       |                       |
```

### 9.3 Full Pipeline Flow (Happy Path)

```
sem pipeline run acme
  │
  ├─ [1] INTAKE
  │   ├─ Interactive prompts → ClientProfile
  │   └─ Write clients/acme/intake/intake.json
  │
  ├─ [2] RESEARCH
  │   ├─ crawl_site(url) → SiteCrawl
  │   ├─ scrape_gbp(name, city) → GoogleBusinessProfile
  │   ├─ scrape_reviews(name, domain) → list[Review]
  │   ├─ scrape_social(name, domain) → list[SocialProfile]
  │   ├─ analyze_brand(client, site_crawl) → brand insights
  │   ├─ analyze_site(site_crawl) → site quality
  │   └─ Write clients/acme/research/*.json
  │
  ├─ [3] COMPETITORS
  │   ├─ scrape_transparency(competitor) → list[TransparencyAd]  (per competitor)
  │   ├─ SpyFuClient.get_competitor_keywords(domain)
  │   ├─ SpyFuClient.get_ad_history(domain)
  │   ├─ ValueSerpClient.get_ads(query)
  │   ├─ analyze_competitors(profiles) → competitive insights
  │   └─ Write clients/acme/competitors/*.json
  │
  ├─ [4] KEYWORDS
  │   ├─ generate_seed_keywords(client, site, competitors)
  │   ├─ expand_keywords_swedish(seeds) → expanded list
  │   ├─ GoogleAdsService.get_keyword_ideas(seeds) → volume data
  │   ├─ GoogleAdsService.get_search_volumes(keywords)
  │   ├─ group_keywords(keywords) → themed groups
  │   ├─ assign_match_types(groups, budget) → with match types
  │   ├─ generate_negative_keywords(targets, industry)
  │   └─ Write clients/acme/keywords/*.json
  │
  ├─ [5] CAMPAIGN
  │   ├─ build_campaigns(client, keyword_groups, presence)
  │   │   ├─ structure_by_service() or structure_by_geo()
  │   │   ├─ generate_rsa() per ad group
  │   │   ├─ allocate_budget()
  │   │   ├─ select_bid_strategy()
  │   │   └─ generate_extensions()
  │   └─ Write clients/acme/campaigns/campaign_plan.json
  │
  ├─ [6] VALIDATE
  │   ├─ Run 11 validation checks
  │   └─ Print pass/fail report to terminal
  │
  ├─ [7] EXPORT
  │   ├─ export_campaign_plan() → 7 CSV files
  │   ├─ export_keyword_xlsx() → keyword spreadsheet
  │   └─ Write clients/acme/exports/
  │
  └─ [8] REPORT
      ├─ generate_strategy_report() → Markdown
      ├─ export_pdf_report() → PDF
      └─ Write clients/acme/reports/
```

### 9.4 Dry-Run Flow (Divergences)

```
sem pipeline run acme --dry-run
  │
  ├─ Stages 1-3: IDENTICAL (scrapers don't require auth)
  │              Exception: transparency scraper uses Playwright (runs normally)
  │              SpyFu/ValueSERP: Return empty results if no API keys
  │
  ├─ Stage 4 (KEYWORDS):
  │   ├─ DryRunGoogleAdsService replaces GoogleAdsService
  │   ├─ get_keyword_ideas() → returns seeds with synthetic volume data
  │   ├─ get_search_volumes() → returns realistic but fake metrics
  │   └─ All downstream logic runs normally on synthetic data
  │
  ├─ Stages 5-8: IDENTICAL (operate on whatever data stages 1-4 produced)
  │
  └─ Report header: "⚠ DRY RUN — synthetic data, not production metrics"
```

### 9.5 Audit Flow

```
sem audit acme
  │
  ├─ Load generated plan: clients/acme/campaigns/campaign_plan.json
  │
  ├─ Fetch live data:
  │   ├─ GoogleAdsService.get_campaigns() → live campaigns
  │   ├─ GoogleAdsService.get_ad_groups() → per campaign
  │   ├─ GoogleAdsService.get_keywords() → per ad group
  │   └─ GoogleAdsService.get_ads() → per ad group
  │
  ├─ Compare:
  │   ├─ comparator.compare(live, recommended)
  │   ├─ Diff: campaigns, keywords, ad copy, budgets, bid strategies
  │   └─ Generate audit dict
  │
  ├─ Output:
  │   ├─ Print rich table to terminal
  │   └─ Write clients/acme/audits/audit_{date}.md
  │
  └─ Exit
```

---

## 10. Dependency Map

### 10.1 Internal Dependencies (module → module)

```
src/cli/app.py
  → cli/auth_commands.py
  → cli/accounts_commands.py
  → cli/pipeline_commands.py
  → cli/intake_commands.py
  → cli/research_commands.py
  → cli/competitors_commands.py
  → cli/keywords_commands.py
  → cli/campaign_commands.py
  → cli/validate_commands.py
  → cli/export_commands.py
  → cli/report_commands.py
  → cli/audit_commands.py
  → cli/template_commands.py
  → cli/config_commands.py

cli/auth_commands.py → auth/oauth.py, auth/credentials.py, auth/token_refresh.py
cli/accounts_commands.py → accounts/manager.py, auth/google_ads_auth.py
cli/pipeline_commands.py → accounts/state.py, (all stage commands)
cli/keywords_commands.py → generators/keyword_generator.py, apis/google_ads.py
cli/campaign_commands.py → generators/campaign_builder.py, generators/ad_copy_generator.py
cli/export_commands.py → generators/csv_exporter.py, generators/report_generator.py
cli/audit_commands.py → audit/fetcher.py, audit/comparator.py
cli/template_commands.py → templates/manager.py, templates/adapter.py
cli/config_commands.py → utils/config_manager.py

auth/oauth.py → google_auth_oauthlib
auth/credentials.py → keyring, cryptography
auth/google_ads_auth.py → auth/credentials.py, auth/token_refresh.py, google-ads SDK
auth/token_refresh.py → auth/credentials.py

accounts/manager.py → accounts/config.py, accounts/state.py, utils/config_manager.py
accounts/config.py → models/account.py
accounts/state.py → (filesystem only)

apis/google_ads.py → auth/google_ads_auth.py
apis/spyfu_client.py → utils/config.py (API key)
apis/valueserp_client.py → utils/config.py (API key)

templates/adapter.py → generators/ad_copy_generator.py
audit/fetcher.py → auth/google_ads_auth.py, apis/google_ads.py
audit/comparator.py → models/campaign.py

# UNCHANGED internal deps (existing codebase):
generators/keyword_generator.py → utils/swedish_nlp.py, data/swedish/*
generators/ad_copy_generator.py → models/campaign.py, data/swedish/*
generators/campaign_builder.py → models/campaign.py, generators/ad_copy_generator.py
generators/csv_exporter.py → models/campaign.py
generators/report_generator.py → generators/pdf_generator.py
scrapers/* → models/research.py
analysis/* → models/client.py, models/research.py, models/competitor.py
```

### 10.2 External Dependencies (packages/services)

```
google-ads SDK
  ├─ google-auth
  ├─ google-auth-oauthlib
  ├─ grpcio
  └─ proto-plus

typer
  └─ rich (transitive, also used directly)

keyring
  └─ (OS-specific backends: Windows Credential Locker)

cryptography
  └─ (Fernet symmetric encryption)

pyyaml (config files)

# Existing (unchanged):
pydantic ≥2.5
playwright ≥1.40
httpx ≥0.25
beautifulsoup4 ≥4.12
lxml ≥4.9
openpyxl ≥3.1
pandas ≥2.1
markdown-pdf ≥1.13
pypdf ≥3.17
python-dotenv ≥1.0
simplemma ≥1.1
```

---

## 11. Cross-Cutting Concerns

### 11.1 Error Taxonomy

```
SemMasterError (base)
├── AuthError
│   ├─ NotAuthenticatedError — no tokens found, "Run 'sem auth login'"
│   ├─ TokenExpiredError — refresh failed, "Re-authenticate with 'sem auth login'"
│   ├─ InsufficientScopeError — OAuth scope missing
│   └─ AccountAccessDeniedError — customer ID not under MCC
├── ValidationError
│   ├─ InvalidClientNameError — not kebab-case or already exists
│   ├─ InvalidCustomerIdError — wrong format
│   ├─ PrerequisiteNotMetError — pipeline stage dependency missing
│   ├─ CharacterLimitError — headline/description exceeds limit
│   └─ ConfigError — invalid config value
├── NotFoundError
│   ├─ ClientNotFoundError — client slug doesn't exist
│   ├─ TemplateNotFoundError — template name doesn't exist
│   └─ StageDataNotFoundError — expected output file missing
├── ApiError
│   ├─ GoogleAdsApiError — Google Ads API returned error
│   ├─ SpyFuApiError — SpyFu API error
│   ├─ ValueSerpApiError — ValueSERP API error
│   └─ QuotaExceededError — API rate limit hit
├── StorageError
│   ├─ CredentialStorageError — cannot store/retrieve tokens
│   └─ FileWriteError — cannot write output file
└── ScraperError
    ├─ BrowserLaunchError — Playwright cannot start
    ├─ PageLoadError — target URL timeout or error
    └─ ParseError — unexpected page structure
```

All errors include:
- `message: str` — human-readable description
- `hint: str` — suggested action (e.g., "Run 'sem auth login' to authenticate")
- Error display in CLI uses `rich.console.Console.print()` with `[red]` styling

### 11.2 Environment & Configuration

#### Environment Variables (`.env` file)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| SPYFU_API_KEY | No | SpyFu competitor intelligence | `abc123...` |
| VALUESERP_API_KEY | No | ValueSERP SERP data | `def456...` |
| ANTHROPIC_API_KEY | No | AI ad copy generation | `sk-ant-...` |

**Removed from .env** (moved to OAuth):
- ~~GOOGLE_ADS_DEVELOPER_TOKEN~~ → `~/.sem-master/config.yaml`
- ~~GOOGLE_ADS_CLIENT_ID~~ → `~/.sem-master/credentials/client_secret.json`
- ~~GOOGLE_ADS_CLIENT_SECRET~~ → `~/.sem-master/credentials/client_secret.json`
- ~~GOOGLE_ADS_REFRESH_TOKEN~~ → keyring / encrypted file
- ~~GOOGLE_ADS_LOGIN_CUSTOMER_ID~~ → `~/.sem-master/config.yaml`

#### Global Config (`~/.sem-master/config.yaml`)

```yaml
version: "2.0"
active_client: null                    # Currently active client slug
mcc_customer_id: "123-456-7890"       # MCC Manager Account ID
developer_token: "AbCdEf..."          # Google Ads API developer token

defaults:
  dry_run: false                       # Default to dry-run mode
  industry: null                       # Default industry for new clients
  geo_targets:
    - name: "Sverige"
      id: 2752
  language_id: 1053                    # Swedish
  ad_schedule: "07:00-21:00"           # Default ad schedule

api_keys:
  spyfu: null                          # Override for SpyFu (if not in .env)
  valueserp: null                      # Override for ValueSERP (if not in .env)
  anthropic: null                      # Override for Anthropic (if not in .env)
```

#### Per-Client Config (`clients/{name}/account.yaml`)

```yaml
name: "acme"
customer_id: "123-456-7890"
display_name: "Acme Renovering AB"
industry: "bygg_renovering"
monthly_budget_sek: 25000
brand_voice: "Professionell men varm, fokus på kvalitet och lokalt hantverk"
website_url: "https://acmerenovering.se"
contact_name: "Erik Svensson"
contact_email: "erik@acmerenovering.se"
notes: "ROT-avdrag applicable. Focus on Stockholm inner city."
created_at: "2026-04-01T10:00:00"
updated_at: "2026-04-01T10:00:00"
```

### 11.3 Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Python files | snake_case | `google_ads_auth.py` |
| Python classes | PascalCase | `ManagedAccount`, `GoogleAdsService` |
| Python functions | snake_case, verb-first | `get_account()`, `create_account()`, `run_oauth_flow()` |
| Python constants | UPPER_SNAKE_CASE | `PIPELINE_STAGES`, `SWEDEN_GEO_ID` |
| CLI commands | kebab-case | `sem accounts add`, `sem pipeline run` |
| Client slugs | kebab-case | `acme-renovering`, `stockholm-tandvard` |
| Template names | kebab-case | `standard-service-campaign` |
| Config keys | snake_case | `active_client`, `mcc_customer_id` |
| Data files | snake_case | `industry_keywords.json`, `workflow_state.json` |
| Output directories | snake_case | `clients/acme/keywords/` |
| Test files | `test_` prefix | `test_auth.py`, `test_accounts.py` |
| Git branches | `feature/`, `fix/`, `refactor/` prefix | `feature/oauth-auth` |

---

## 12. Extensibility Guide

### Adding a New Pipeline Stage

1. **Create the command file**: `src/cli/{stage}_commands.py` — follow the pattern from existing stage commands
2. **Register the command group**: Add to `src/cli/app.py` with `app.add_typer()`
3. **Add stage to PIPELINE_STAGES**: In `src/accounts/state.py`
4. **Define prerequisites**: Add prerequisite mapping in `check_prerequisites()`
5. **Create output directory**: Add to `accounts.manager.create_account()` directory creation

No existing code needs modification beyond these registration points.

### Adding a New API Integration

1. **Create client**: `src/apis/{service}_client.py` — follow pattern of `spyfu_client.py`
2. **Add API key**: Add to `.env.example` and `Settings` model
3. **Create dry-run mock**: Add mock class or method that returns synthetic data
4. **Wire into stage command**: Call from the relevant CLI command

### Adding a New Scraper

1. **Create scraper**: `src/scrapers/{target}_scraper.py` — follow pattern of existing scrapers
2. **Add model**: If new data shape, add to `src/models/research.py`
3. **Wire into research stage**: Call from `cli/research_commands.py`

### Adding a New Report Section

1. **Add generation function**: In `src/generators/report_generator.py`
2. **Add to report template**: Extend the markdown generation in `generate_strategy_report()`
3. **No other changes needed** — report command reads whatever the generator produces

### Adding a New Export Format

1. **Create exporter**: `src/generators/{format}_exporter.py`
2. **Add CLI flag**: `--format` option on `sem export` command
3. **No model changes** — all exporters consume `CampaignPlan`

---

## 13. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Google Ads API developer token approval delayed | High | Critical — blocks live API calls | Dry-run mode enables full pipeline without token; apply early |
| OAuth token refresh fails silently | Medium | High — pipeline fails mid-run | Explicit token check before pipeline start; clear error messages |
| `google-ads` SDK version incompatibility | Medium | Medium — API changes break client | Pin major version; test with new releases before updating |
| Keyring unavailable on some Windows configs | Medium | Low — falls back to Fernet | Fernet fallback is automatic and tested |
| MCC account setup complexity | Low | Medium — delays first use | `sem auth setup` provides step-by-step guide |
| Playwright browser not installed | Medium | Medium — scrapers fail | Check on first scraper run; `playwright install chromium` |
| Swedish character encoding issues in CSV | Low | Medium — corrupted Excel import | UTF-8 BOM encoding already handles this |
| Rate limiting on Google Ads API | Medium | Low — temporary delay | Exponential backoff with retry; warn user |
| Client_secret.json accidentally committed | Medium | Critical — security breach | .gitignore entry; store in ~/.sem-master/ not project dir |
| Concurrent pipeline runs for same client | Low | Medium — data corruption | File lock on workflow_state.json during stage execution |

---

## 14. Implementation Roadmap

### Phase 1: Foundation — Config & Account Management
**Goal:** `sem config`, `sem accounts` commands work. Client directories created with proper structure.

**Modules to build:**
- `src/utils/config_manager.py`
- `src/models/account.py`
- `src/accounts/manager.py`
- `src/accounts/config.py`
- `src/accounts/state.py`
- `src/cli/app.py` (root app)
- `src/cli/config_commands.py`
- `src/cli/accounts_commands.py`
- Update `pyproject.toml` (entry point, new deps)
- Update `requirements.txt`

**Dependencies:** None (first phase)

**Definition of done:**
- [ ] `sem --version` prints version
- [ ] `sem config show` displays default config
- [ ] `sem config set defaults.industry tandvård` updates config.yaml
- [ ] `sem accounts add acme 123-456-7890 --industry bygg_renovering --budget 25000` creates client directory
- [ ] `sem accounts list` shows registered clients
- [ ] `sem accounts switch acme` sets active client
- [ ] `sem accounts info` shows active client details
- [ ] `sem accounts remove acme` archives client directory
- [ ] All existing tests still pass

### Phase 2: Authentication — OAuth & Token Management
**Goal:** `sem auth login` authenticates with Google Ads API. Tokens stored securely.

**Modules to build:**
- `src/auth/oauth.py`
- `src/auth/credentials.py`
- `src/auth/token_refresh.py`
- `src/auth/google_ads_auth.py`
- `src/cli/auth_commands.py`
- `scripts/setup_google_cloud.py`
- Update `src/utils/config.py` (remove Google Ads fields from Settings)

**Dependencies:** Phase 1 (config_manager for storing MCC ID)

**Definition of done:**
- [ ] `sem auth setup` prints complete Google Cloud setup guide
- [ ] `sem auth login` opens browser, completes OAuth flow, stores tokens
- [ ] `sem auth status` shows token validity and MCC info
- [ ] `sem auth logout` clears all stored tokens
- [ ] Tokens stored in OS keyring (verified on Windows)
- [ ] Fernet fallback works when keyring unavailable
- [ ] Token auto-refresh works (test with expired token)
- [ ] `sem accounts add` verifies account access via API
- [ ] All existing tests still pass

### Phase 3: Google Ads API Client — Rewrite
**Goal:** Replace the stub `google_ads.py` with a working OAuth-authenticated client.

**Modules to build:**
- `src/apis/google_ads.py` (rewrite)
- `DryRunGoogleAdsService` class

**Dependencies:** Phase 2 (auth for authenticated client)

**Definition of done:**
- [ ] `GoogleAdsService.get_keyword_ideas()` returns real Keyword Planner data
- [ ] `GoogleAdsService.get_search_volumes()` returns real volume data
- [ ] `GoogleAdsService.get_campaigns()` returns live campaign data
- [ ] `GoogleAdsService.get_account_info()` returns account metadata
- [ ] `DryRunGoogleAdsService` returns realistic synthetic data for all methods
- [ ] API errors wrapped in `GoogleAdsApiError` with clear messages
- [ ] Rate limiting handled with exponential backoff
- [ ] All existing tests still pass

### Phase 4: CLI Pipeline Commands — Wire Existing Generators
**Goal:** All pipeline stages callable via `sem <stage> <client>`. Full pipeline works end-to-end.

**Modules to build:**
- `src/cli/pipeline_commands.py`
- `src/cli/intake_commands.py`
- `src/cli/research_commands.py`
- `src/cli/competitors_commands.py`
- `src/cli/keywords_commands.py`
- `src/cli/campaign_commands.py`
- `src/cli/validate_commands.py`
- `src/cli/export_commands.py`
- `src/cli/report_commands.py`

**Dependencies:** Phase 1 (accounts), Phase 3 (Google Ads client for keywords stage)

**Definition of done:**
- [ ] `sem intake acme` runs interactive onboarding, writes intake.json
- [ ] `sem research acme` runs all scrapers, writes research output
- [ ] `sem competitors acme` runs competitor analysis, writes output
- [ ] `sem keywords acme` generates keywords with live volume data
- [ ] `sem campaign acme` builds campaign plan
- [ ] `sem validate acme` runs 11 checks, prints report
- [ ] `sem export acme` generates 7 CSV files + XLSX
- [ ] `sem report acme` generates markdown + PDF report
- [ ] `sem pipeline run acme` executes all stages in sequence
- [ ] `sem pipeline run acme --dry-run` works without API credentials
- [ ] `sem pipeline status acme` shows stage completion
- [ ] Pipeline state tracks correctly across stages
- [ ] Prerequisites enforced (can't run keywords before intake)

### Phase 5: Templates & Audit — New Features
**Goal:** Template system and audit mode fully functional.

**Modules to build:**
- `src/models/template.py`
- `src/templates/manager.py`
- `src/templates/adapter.py`
- `src/audit/fetcher.py`
- `src/audit/comparator.py`
- `src/cli/template_commands.py`
- `src/cli/audit_commands.py`

**Dependencies:** Phase 3 (Google Ads client for audit), Phase 4 (pipeline for templates)

**Definition of done:**
- [ ] `sem templates save standard-service acme` saves template
- [ ] `sem templates list` shows saved templates
- [ ] `sem templates load standard-service new-client` applies template with adaptations
- [ ] `sem templates delete standard-service` removes template
- [ ] `sem audit acme` fetches live data and shows diff
- [ ] Audit report written to clients/{name}/audits/
- [ ] Template correctly strips client-specific data on save
- [ ] Template correctly inserts new client data on load

### Phase 6: Testing & Polish
**Goal:** Comprehensive test coverage, updated docs, skill updates.

**Modules to build:**
- `tests/test_auth.py`
- `tests/test_accounts.py`
- `tests/test_cli.py`
- `tests/test_audit.py`
- `tests/test_templates.py`
- `tests/test_pipeline_dry_run.py`
- Update `CLAUDE.md`
- Update `.env.example`
- Update Claude Code skills (sem-*)

**Dependencies:** All previous phases

**Definition of done:**
- [ ] All new modules have unit tests
- [ ] OAuth flow tested with mocked responses
- [ ] CLI commands tested via Typer's CliRunner
- [ ] End-to-end dry-run pipeline test passes
- [ ] All 37 existing tests still pass
- [ ] Total test count ≥ 70
- [ ] CLAUDE.md reflects v2.0 architecture
- [ ] .env.example updated (Google Ads fields removed)
- [ ] README.md updated with installation and setup instructions
- [ ] All 7 sem-* skills updated for new CLI workflow

### Parallelization

```
Phase 1 ──────────┐
                   ├──→ Phase 2 ──→ Phase 3 ──┐
                   │                            ├──→ Phase 5
                   └──→ Phase 4 ───────────────┘
                                                      │
                                                      ↓
                                                   Phase 6
```

- **Phase 1** must complete first (everything depends on config/accounts)
- **Phase 2** and **Phase 4** (partially) can run in parallel — Phase 4 stage commands that don't need Google Ads (intake, research, competitors, export, report) can be built alongside Phase 2
- **Phase 3** requires Phase 2 (needs auth)
- **Phase 4 keywords stage** requires Phase 3 (needs Google Ads client)
- **Phase 5** requires Phase 3 (audit) and Phase 4 (templates need pipeline)
- **Phase 6** is last (tests all features)

---

## 15. Build Verification Checklist

### Module: `src/cli/app.py`
- [ ] `create_app()` — returns configured Typer app with all command groups registered
- [ ] `main()` — entry point works when called via `sem` command
- [ ] `--version` flag prints correct version
- [ ] `--help` shows all available command groups

### Module: `src/cli/auth_commands.py`
- [ ] `login()` — completes OAuth flow and stores tokens
- [ ] `login(force=True)` — re-authenticates even with valid tokens
- [ ] `login()` handles missing client_secret.json gracefully
- [ ] `login()` handles user cancellation gracefully
- [ ] `status()` — shows token validity when authenticated
- [ ] `status()` — shows "Not authenticated" when no tokens
- [ ] `logout()` — clears tokens from all storage backends
- [ ] `setup()` — prints complete Google Cloud setup guide

### Module: `src/cli/accounts_commands.py`
- [ ] `add()` — creates client with valid inputs
- [ ] `add()` — rejects duplicate client names
- [ ] `add()` — rejects invalid customer ID format
- [ ] `add()` — verifies account accessible under MCC
- [ ] `list()` — displays all clients with status
- [ ] `remove()` — archives client by default
- [ ] `remove(archive=False)` — deletes client permanently
- [ ] `switch()` — updates active client in config
- [ ] `info()` — shows details for specified client
- [ ] `info()` — defaults to active client when no name given

### Module: `src/cli/pipeline_commands.py`
- [ ] `run()` — executes all stages in sequence
- [ ] `run(dry_run=True)` — completes without API credentials
- [ ] `run(from_stage="keywords")` — starts from specified stage
- [ ] `run(to_stage="campaign")` — stops after specified stage
- [ ] `run()` — defaults to active client
- [ ] `run()` — fails with clear message if no auth (non-dry-run)
- [ ] `status()` — shows stage completion checklist

### Module: CLI Stage Commands (intake through report)
- [ ] Each stage defaults to active client
- [ ] Each stage accepts explicit client name
- [ ] Each stage checks prerequisites before running
- [ ] Each stage updates pipeline state on completion
- [ ] Each stage writes output to correct client subdirectory
- [ ] Each stage supports --dry-run flag
- [ ] `validate` prints colored pass/fail report
- [ ] `export --keywords-only` exports only keyword XLSX

### Module: `src/cli/audit_commands.py`
- [ ] `audit()` — fetches live data and shows diff
- [ ] `audit()` — writes report to audits/ directory
- [ ] `audit(campaign_id=X)` — filters to specific campaign
- [ ] `audit()` — fails clearly when no generated plan exists

### Module: `src/cli/template_commands.py`
- [ ] `list()` — shows all saved templates
- [ ] `save()` — saves campaign as template
- [ ] `load()` — applies template to client
- [ ] `delete()` — removes template
- [ ] Templates strip client-specific data on save
- [ ] Templates adapt to new client context on load

### Module: `src/cli/config_commands.py`
- [ ] `show()` — displays config with secrets redacted
- [ ] `set()` — updates config value via dot notation
- [ ] `edit()` — opens config in $EDITOR

### Module: `src/auth/oauth.py`
- [ ] `run_oauth_flow()` — completes full OAuth 2.0 desktop flow
- [ ] `run_oauth_flow()` — handles port conflict (retries port+1)
- [ ] `run_oauth_flow()` — raises AuthError on user cancellation
- [ ] `run_oauth_flow()` — raises FileNotFoundError for missing client_secret.json
- [ ] `get_oauth_scopes()` — returns correct Google Ads scope

### Module: `src/auth/credentials.py`
- [ ] `store_tokens()` — stores in keyring on Windows
- [ ] `store_tokens()` — falls back to Fernet when keyring unavailable
- [ ] `load_tokens()` — retrieves from keyring
- [ ] `load_tokens()` — retrieves from Fernet file
- [ ] `load_tokens()` — returns None when no tokens stored
- [ ] `load_tokens()` — returns None for corrupted data (doesn't crash)
- [ ] `clear_tokens()` — removes from all backends
- [ ] `_get_or_create_key()` — generates consistent Fernet key

### Module: `src/auth/google_ads_auth.py`
- [ ] `get_google_ads_client()` — returns authenticated client
- [ ] `get_google_ads_client()` — triggers token refresh if expired
- [ ] `get_google_ads_client()` — raises AuthError when not authenticated
- [ ] `build_google_ads_config()` — produces valid config dict

### Module: `src/auth/token_refresh.py`
- [ ] `ensure_valid_token()` — returns valid token without refresh when not expired
- [ ] `ensure_valid_token()` — refreshes expired token
- [ ] `ensure_valid_token()` — raises AuthError when refresh fails
- [ ] `ensure_valid_token()` — stores refreshed tokens
- [ ] `check_expiry()` — returns correct validity and time remaining

### Module: `src/accounts/manager.py`
- [ ] `create_account()` — creates directory structure with all subdirs
- [ ] `create_account()` — writes account.yaml
- [ ] `create_account()` — initializes workflow_state.json
- [ ] `create_account()` — rejects duplicate names (ConflictError)
- [ ] `list_accounts()` — returns all registered accounts
- [ ] `get_account()` — returns single account by name
- [ ] `get_account()` — raises NotFoundError for unknown name
- [ ] `remove_account(archive=True)` — moves to _archived/
- [ ] `remove_account(archive=False)` — deletes directory
- [ ] `set_active_client()` — updates config.yaml
- [ ] `get_active_client()` — returns current active client

### Module: `src/accounts/config.py`
- [ ] `write_account_config()` — writes valid YAML
- [ ] `read_account_config()` — returns ManagedAccount model
- [ ] `update_account_config()` — merges updates correctly

### Module: `src/accounts/state.py`
- [ ] `initialize_state()` — creates state with all stages pending
- [ ] `get_pipeline_state()` — reads current state
- [ ] `update_state()` — updates specific stage status
- [ ] `check_prerequisites()` — returns True when prerequisites met
- [ ] `check_prerequisites()` — returns False with missing stages when not met
- [ ] `get_next_stage()` — returns first incomplete stage
- [ ] `get_next_stage()` — returns None when all complete

### Module: `src/apis/google_ads.py` (rewritten)
- [ ] `GoogleAdsService.__init__()` — creates authenticated client
- [ ] `get_keyword_ideas()` — returns keyword suggestions with volume data
- [ ] `get_search_volumes()` — returns volumes for specific keywords
- [ ] `get_campaigns()` — returns live campaigns
- [ ] `get_ad_groups()` — returns ad groups for campaign
- [ ] `get_keywords()` — returns keywords for ad group
- [ ] `get_ads()` — returns RSAs for ad group
- [ ] `get_account_info()` — returns account metadata
- [ ] `DryRunGoogleAdsService` — all methods return synthetic data
- [ ] API errors wrapped in GoogleAdsApiError

### Module: `src/templates/manager.py`
- [ ] `save_template()` — strips client specifics, saves to file
- [ ] `load_template()` — loads and returns CampaignTemplate
- [ ] `list_templates()` — returns all template summaries
- [ ] `delete_template()` — removes file

### Module: `src/templates/adapter.py`
- [ ] `apply_template()` — replaces brand names, URLs, keywords, geo targets
- [ ] `apply_template()` — generates new ad copy for target client
- [ ] `apply_template()` — validates result against character limits

### Module: `src/audit/fetcher.py`
- [ ] `fetch_live_campaigns()` — returns structured campaign data
- [ ] `fetch_keyword_performance()` — returns keyword metrics
- [ ] Both handle auth errors gracefully

### Module: `src/audit/comparator.py`
- [ ] `compare()` — identifies missing/extra campaigns
- [ ] `compare()` — identifies keyword gaps and waste
- [ ] `compare()` — identifies ad copy differences
- [ ] `compare()` — identifies budget/bid strategy diffs
- [ ] `format_audit_report()` — produces readable markdown

### Module: `src/utils/config_manager.py`
- [ ] `ensure_config_dir()` — creates directory structure
- [ ] `load_config()` — loads config, creates default if missing
- [ ] `save_config()` — writes valid YAML
- [ ] `get_value()` — retrieves by dot-notation key
- [ ] `set_value()` — sets by dot-notation key

### Data Models
- [ ] `ManagedAccount` — all fields validate correctly
- [ ] `ManagedAccount.customer_id` — validates XXX-XXX-XXXX format
- [ ] `ManagedAccount.name` — validates kebab-case
- [ ] `CampaignTemplate` — serializes/deserializes correctly
- [ ] `ClientProfile.google_ads_customer_id` — new field works, optional

### Data Flows
- [ ] Authentication flow — complete end-to-end (login → store → use → refresh)
- [ ] New client onboarding — add account → directory created → intake works
- [ ] Full pipeline (dry-run) — all 8 stages complete sequentially
- [ ] Full pipeline (live) — all 8 stages with real API data
- [ ] Template save/load cycle — save from client A, load to client B
- [ ] Audit flow — fetch live → compare → report generated

### Integration
- [ ] Existing 37 tests pass unchanged
- [ ] New test count ≥ 33 (covering all new modules)
- [ ] `sem` command installable via `pip install -e .`
- [ ] `.env.example` updated (no Google Ads fields)
- [ ] `CLAUDE.md` reflects v2.0 architecture
- [ ] All sem-* skills reference new CLI commands

---

*End of Architecture Blueprint*
