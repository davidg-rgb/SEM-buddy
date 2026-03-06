# SEM Master

Google Ads campaign automation tool for Swedish/Nordic clients. Generates complete campaigns from client inputs and outputs strategic reports + Google Ads Editor CSV files.

## Project Structure

```
src/
  models/       - Pydantic v2 data models (client, campaign, competitor, research)
  scrapers/     - Playwright + httpx scrapers (site crawler, GBP, reviews, social, transparency)
  apis/         - API clients (Google Ads Keyword Planner, SpyFu, ValueSERP)
  analysis/     - Brand, site, and competitor analysis
  generators/   - Keyword expansion, ad copy, campaign builder, CSV exporter, reports
  utils/        - Config, Swedish NLP, PDF reader
data/
  swedish/      - Stopwords, negative keywords, CTAs, ad patterns, industry seeds
  templates/    - Google Ads Editor CSV schemas, report templates
clients/        - Per-client working directories (runtime, gitignored)
scripts/        - Validation scripts
```

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
- **Workflow state**: `clients/{name}/workflow_state.json` tracks progress through the pipeline

## Running

```bash
# Validate a campaign before export
python scripts/validate_campaign.py clients/{name}/campaigns/campaign.json

# Scrapers use async - run via python -m
python -m src.scrapers.site_crawler
```

## API Keys

Configure in `.env` (see `.env.example`):
- `GOOGLE_ADS_*` - Keyword Planner API
- `SPYFU_API_KEY` - Competitor intelligence
- `VALUESERP_API_KEY` - SERP data
- `ANTHROPIC_API_KEY` - Ad copy generation
