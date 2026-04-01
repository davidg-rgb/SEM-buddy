# SEM Master

Google Ads campaign automation tool for Swedish/Nordic clients. Generates complete campaigns from client inputs and outputs strategic reports + Google Ads Editor CSV files.

## Project Structure

```
src/
  auth/         - OAuth 2.0 flow, credential storage (keyring + Fernet), token refresh
  accounts/     - Multi-client CRUD, account config, pipeline state machine
  cli/          - Typer CLI app, command modules (14 command groups)
  templates/    - Campaign template save/load/adapt system
  audit/        - Live campaign fetch, structured diff comparator
  apis/         - Google Ads SDK client (official google-ads), DryRunGoogleAdsService
  models/       - Pydantic v2 data models (client, campaign, competitor, research, account)
  scrapers/     - Playwright + httpx scrapers (site crawler, GBP, reviews, social, transparency)
  analysis/     - Brand, site, and competitor analysis
  generators/   - Keyword expansion, ad copy, campaign builder, CSV exporter, reports
  utils/        - Config manager, Swedish NLP, PDF reader
data/
  swedish/      - Stopwords, negative keywords, CTAs, ad patterns, industry seeds
  templates/    - Google Ads Editor CSV schemas, report templates
clients/        - Per-client working directories (runtime, gitignored)
scripts/        - Validation scripts
tests/          - pytest suite
```

## Installation

```bash
pip install -e ".[dev]"
```

Makes the `sem` command available globally.

## CLI Commands

```
sem --version                                     Show version
sem config show|set|edit                          View and modify global config
sem accounts add|list|info|switch|remove          Manage client accounts
sem auth setup|login|status|logout                OAuth authentication
sem intake run <client>                           Client onboarding
sem research run <client>                         Data collection
sem competitors run <client>                      Competitor analysis
sem keywords run <client>                         Keyword research
sem campaign run <client>                         Campaign building
sem validate run <client>                         Pre-export validation
sem export run <client>                           CSV export
sem report run <client>                           Strategy report
sem pipeline run <client> [--from X --to Y] [--dry-run]  Full pipeline
sem templates save|list|load|delete               Campaign templates
sem audit run <client>                            Compare live vs recommended
```

## Authentication

OAuth 2.0 flow for Google Ads API access:

1. `sem auth setup` — prints Google Cloud project setup guide
2. Place `client_secret.json` in `~/.sem-master/credentials/`
3. `sem auth login` — opens browser for OAuth consent
4. Tokens stored in OS keyring (Fernet-encrypted file fallback)
5. Auto-refresh on expiry

## Skills

7 skills installed at `~/.claude/skills/sem-*`:
- `sem-master` - Orchestrator, main entry point
- `sem-intake` - Client onboarding
- `sem-research` - Data collection / scraping
- `sem-competitor-ads` - Competitor intelligence
- `sem-keywords` - Keyword research & grouping
- `sem-campaign-builder` - Campaign structure & ad copy & CSV export
- `sem-report` - Report generation

## Key Conventions

- **Language**: All ad copy and client-facing output in Swedish
- **Character limits**: Headlines max 30 chars, descriptions max 90 chars (enforced by Pydantic validators in `src/models/campaign.py`)
- **Review model**: Uses `review_date` field (not `date`) to avoid shadowing the type
- **CSV export**: UTF-8 BOM encoding for Excel compatibility
- **Swedish market constants**: Sweden geo ID 2752, Swedish language ID 1053
- **Match type strategy**: <10K SEK exact+phrase, 10-30K phrase primary, >30K broad+smart bidding
- **Client data**: Stored in `clients/{name}/` with subdirs for intake, research, competitors, keywords, campaigns, reports
- **Workflow state**: `clients/{name}/account.yaml` tracks pipeline state per client
- **Config**: Global config at `~/.sem-master/config.yaml`, per-client at `clients/{name}/account.yaml`
- **Dry-run mode**: `--dry-run` flag on all pipeline/stage commands uses synthetic data; no API credentials needed
- **Templates**: Stored at `~/.sem-master/templates/`, client-specific data replaced with `{Foretag}/{website}` placeholders
- **Audit**: Live data fetched via Google Ads SDK, compared case-insensitively against campaign plan

## API Keys

Google Ads now uses OAuth 2.0 — no direct API key fields in `.env`:

- **Google Ads OAuth**: Managed via `sem auth login` (credentials stored in OS keyring)
- **Developer token**: Set via `sem config set developer_token YOUR_TOKEN` (or `GOOGLE_ADS_DEVELOPER_TOKEN` in `.env`)
- **ANTHROPIC_API_KEY**: Required for ad copy generation (set in `.env`)
- **SPYFU_API_KEY**: Optional, for competitor intelligence (set in `.env`)
- **VALUESERP_API_KEY**: Optional, for SERP data (set in `.env`)

## Running Tests

```bash
python -m pytest tests/ -v
```
