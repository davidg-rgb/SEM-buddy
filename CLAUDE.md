# SEM Master

Google Ads campaign automation tool for Swedish/Nordic clients. Generates complete campaigns from client inputs and outputs strategic reports + Google Ads Editor CSV files.

## Project Structure

```
src/
  auth/         - OAuth 2.0 flow, credential storage (keyring + Fernet), token refresh
  accounts/     - Multi-client CRUD, account config, pipeline state machine
  cli/          - Typer CLI app, command modules (15 command groups)
  templates/    - Campaign template save/load/adapt system
  audit/        - Live campaign fetch, structured diff comparator
  apis/         - Google Ads SDK client (official google-ads), DryRunGoogleAdsService
  catalog/      - v0.3 catalog primitives (loader, validators, cleaners, URL templating, bid rules)
  cases/        - v0.3 per-client orchestrator (case.yaml schema + runner)
  models/       - Pydantic v2 data models (client, campaign, competitor, research, account, catalog)
  scrapers/     - Playwright + httpx scrapers (site crawler, GBP, reviews, social, transparency)
  analysis/     - Brand, site, and competitor analysis
  generators/   - Keyword expansion, ad copy, campaign builder, CSV exporter, reports
  utils/        - Config manager, Swedish NLP, PDF reader
data/
  swedish/      - Stopwords, negative keywords, CTAs, ad patterns, industry seeds
  en/           - English equivalents — ad patterns, CTAs, industry keywords, negatives
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
sem seo run <url> [--mode single|site] [--competitors url1,url2] [--client name] [--output markdown|pdf|xlsx] [--skip-lighthouse] [--dry-run]  SEO analysis
sem catalog clean|accept-fixes|validate <client>  Inspect / clean catalog data
sem case run <client> [--max-products N] [--no-validate]  Catalog → CSV pipeline (v0.3)
sem case push <client> [--limit N] [--dry-run] [--auto-suffix] [--skip-lead-forms] [--yes]  Catalog → LIVE Google Ads API push
sem case apply-bids <client> [--dry-run] [--name-suffix S] [--base-cpc-sek X] [--yes]   Re-apply today's bid plan to an EXISTING live campaign (cron-pattern)
```

## Catalog engine (v0.3)

The catalog engine turns an arbitrary product/destination catalog into a complete Google Ads campaign with per-row extensions, dynamic URLs, and rules-driven bidding.

**Setup per client:**

1. Drop source data (XLSX / CSV / JSON) into `clients/<slug>/`.
2. Write `clients/<slug>/catalog.yaml` describing the sources, primary key, joins, and defaults.
3. Write `clients/<slug>/case.yaml` describing structuring, URL templates, keyword templates, ad copy, extensions, and bid rules.
4. (Optional) `sem catalog clean <slug>` → review `cleaning_diff.md` → `sem catalog accept-fixes <slug>`.
5. `sem case run <slug>` produces ready-to-import Google Ads Editor CSVs in `clients/<slug>/exports/catalog/`.

**Generated CSVs:** 01–07 (campaigns/ad groups/keywords/RSAs/negatives/sitelinks/callouts) plus 08_promotions, 09_lead_forms, and a documentation-only 10_bid_schedules.

**Catalog primitives** live in `src/catalog/`:
- `loader.py` — multi-source XLSX/CSV/JSON loader with join key support
- `validators.py` — schema + IATA + required-column checks
- `cleaners.py` — deterministic + optional LLM-assisted name normalization
- `url_templating.py` — `{sku}`, `{name}`, `{attribute}`, `{N}` rotation
- `bid_rules.py` — declarative first-match-wins rules with optional `during:` clause

**Models:** `Product`, `CampaignBuildConfig`, `PromotionExtension`, `LeadFormExtension`, `BidSchedule`, plus `bid_modifier` / `max_cpc_sek` / `target_cpa_micros` fields on `AdGroup`.

**Builder:** `src.generators.campaign_builder.build_campaigns_from_catalog(client, products, build_config, ...)` orchestrates the SKU build, applies bid rules, generates promotions + lead forms, and returns a complete `CampaignPlan`.

**Scale:** 1,000-row catalog completes the full pipeline (load → validate → build → export) in ~2 seconds on a developer laptop. Test with `SEM_RUN_SCALE_TESTS=1 pytest tests/test_catalog_scale.py`.

## Live API push (v0.3.1)

`sem case push <slug>` mutates the campaign plan directly through the Google Ads API instead of exporting to CSV. Used for: account provisioning workflows, automated re-pushes, or skipping the manual "import via Editor" step.

**Flags:**
- `--limit N` — push only first N ad groups (smoke test)
- `--dry-run` — walk the plan, report counts, make no API calls
- `--auto-suffix` — append a timestamp to every entity name (re-runs without collisions)
- `--skip-lead-forms` — Google requires a one-time manual ToS click in the Ads UI before lead-form assets can be created via API; this flag bypasses them
- `--yes` — skip the confirmation prompt

**What gets pushed:** CampaignBudget → Campaign (PAUSED) → CampaignCriteria (lang+geo) → AdGroups → Keywords → RSAs → Sitelinks → Callouts → LeadForms (best-effort) → PromotionAssets (linked to ad groups).

**Gotchas baked into the code** (each is a regression test):
- Campaign requires `contains_eu_political_advertising` (default DOES_NOT_CONTAIN)
- Keyword text must be sanitized: commas, parens, slashes, etc. are illegal — `sanitize_keyword_text` strips them
- Lead-form fields must follow Google's combinations (use FULL_NAME, not FIRST_NAME alone)
- Lead-form `call_to_action_description` is required (defaults to `headline` if not set)
- `PromotionAsset.percent_off` empirically uses `10,000 = 1%` scale (Google's docs say 1,000,000, which is wrong as of v23)
- `promotion_target` is required, max 20 chars — defaults to the product/destination name trimmed
- Campaigns are always created PAUSED on first push; the operator reviews and flips to ENABLED in the UI
- Re-runs need `--auto-suffix` (or a manual `--name-suffix`) — Google rejects duplicate campaign names

**Verification of the live push** (executed 2026-05-20 against `469-180-7001`):
```
sem case push etraveli --limit 3 --auto-suffix --skip-lead-forms --yes
→ 1 budget + 1 campaign + 1 criterion + 3 ad groups + 30 keywords + 3 RSAs
  + 11 assets (4 sitelinks + 4 callouts + 3 promotions) + 11 asset links
```

## Multi-variant RSAs + discount-driven bidding (v0.3.2)

Each catalog ad group now ships 3–5 RSA variants instead of one. The variants
are deterministically tagged by lever stack so Google's RSA optimizer has a
real spread to test:

| Variant | Lever stack | When |
|---|---|---|
| `price_led` | specificity + friction removal | Always |
| `discount_led` | loss aversion + scarcity + specificity | Only if `discount_pct > 0` |
| `social_proof` | authority + risk reversal | Always |
| `urgency` | scarcity + friction removal | Always |
| `loss_aversion` | pain + friction removal | Always |

**Variant contract** (enforced by `tests/test_rsa_variants.py`):
- Every product with `discount_pct >= 0.15` gets a `discount_led` RSA that mentions
  the literal percent (e.g. "38%") in ≥1 headline and ≥1 description.
- No two variants share the same headline list or pinned H3 CTA.
- Each variant fills 15 headlines and 4 descriptions whenever the catalog
  data supports it ("Excellent" Ad Strength target).
- Banned phrases ("Top-rated travel agent", "ATOL-style protection",
  "Was full price, now -X%", "Today only: X% off", "Final seats",
  "Last-minute", "Cheap {name} flights") are stripped at the pattern layer.
- `from_price=null` rows skip price-anchored patterns (`requires_from_price`
  flag); no naked `$` ever ships.
- Long-name (>= 18 char) destinations fall back to `long_name_fallback_patterns`
  that use the IATA SKU instead of truncating mid-word.
- IATA codes appear in customer-facing copy only when the SKU is in the
  household-codes allowlist (~54 codes).
- The `discount_led` variant caps `{discount_pct}` mentions at 5 of 15
  headlines to avoid Google's semantic-similarity penalty.

## Catalog v0.3.3 fixes (review-driven)

The first end-to-end production run on the 964-destination etraveli catalog
surfaced four ship-blocker bugs that have all been closed (see
`.planning/review/CONSOLIDATED-REVIEW.md` for the full reviewer audit):

1. **Null-safe price interpolation** — `_fill_pattern` no longer renders bare
   `$` when `from_price` is missing; patterns flagged `requires_from_price`
   are skipped instead.
2. **Catalog SKU canonicalization** — `NY` → `NYC`, `LON-Heathrow` → `LHR`,
   `Louisville`/`SDF` inversion fixed. The cleaning-proposal model gained a
   `__sku__` diff type that renames primary keys with collision detection
   (drops the source row when the target already exists).
3. **IATA validator** — `validate_iata_skus()` in `src/catalog/validators.py`
   warns on any non-IATA SKU at load time.
4. **Banned-phrase patterns scrubbed** — v3 patterns.json removes 9 banned
   phrases enumerated by the sem-ad-copy skill plus 3 FTC/ASA-risk anchors
   ("Was full price", "Today only", "Final seats"). Long-name destinations
   no longer ship "Avoid Petropavlovsk-Kamchats" — the new
   `"Avoid fare hikes today"` is name-independent.

**Where it lives:**
- `src/generators/ad_copy_generator.py` — `generate_rsa_variants(product)`
  + per-variant helpers `generate_headlines_for_variant` /
  `generate_descriptions_for_variant`.
- `src/generators/llm_ad_copy.py` — `generate_llm_ad_copy(..., variant_role=...)`
  switches the LLM prompt to lead with the role's primary lever.
- `data/en/ad_copy_patterns.json` — `variants` block with per-role pattern
  pools plus a `universal` pool that any variant can draw from.

**Discount-driven bid ladder** (drives ad-group-level `bid_modifier`):

| Discount band | Modifier | etraveli destinations hit |
|---|---|---|
| 50%+ | 2.25× | 170 |
| 40–49% | 2.00× | 173 |
| 30–39% | 1.80× | 143 |
| 25–29% | 1.60× | 86 |
| 20–24% | 1.45× | 68 |
| 15–19% | 1.30× | 88 |
| 10–14% | 1.15× | 86 |
| 5–9% | 1.05× | 77 |
| sub-$100 fares (any discount) | 1.10× | 4 |
| else | 1.00× (base) | 69 |

Rules live in `clients/<slug>/case.yaml` `bid_rules:` and are first-match-wins,
so they MUST be ordered largest-threshold first. The full 964-destination
etraveli catalog is covered.

**Smart bid strategy:** `case.yaml` now has a `campaign_goals:` block. With
`goal_type: revenue` + `target_roas: 4.0` the campaign builder selects
`TARGET_ROAS` / `MAXIMIZE_CONVERSION_VALUE` instead of the default
`MAXIMIZE_CLICKS`. The live push creates the campaign PAUSED so the operator
sets the ROAS target in the Ads UI before going ENABLED.

**Scale verification (2026-05-20):**
```
SEM_DISABLE_LLM=1 sem case run etraveli
→ 964 ad groups, 4,799 RSAs, 943 promotions, 1 lead form (in ~9 seconds)
```

## Catalog v0.3.4 — no-SKU customer copy + per-variant URLs

Mid-session operator constraint plus three new contracts plus a reviewer-driven
pattern pass. See `.planning/v0.3.4-NO-SKU-PER-VARIANT-URLS.md` for the full
write-up and `scripts/audit_v034.py` for the live gate.

**Hard rule:** customer-facing copy NEVER shows the IATA/SKU code. The
resolver hierarchy is now `short_name` → paren-strip → comma-segment → both →
particle-strip → head-token (new) → full name. `_should_use_iata_in_customer_copy`
hard-codes to False; `IATA_HOUSEHOLD_CODES` is an empty shim.

**Per-variant `text=N` URL rotation.** `generate_rsa_variants(...,
final_url_template, text_n_range=(low, high))` renders the URL inside the
variant loop — variant slot 0 → `text=low`, slot 1 → `low+1`, …, wrap on
overflow. No two variants in the same ad group share the same `text=` value.

**Mandatory canonical discount headline.** Every product with
`discount_pct >= 0.15` gets a `Save up to {pct}% to {name}` headline,
force-injected with a 7-step fit-aware fallback chain that walks down to
`Save up to {pct}% today` when no name-bearing shape fits 30 chars. Multi-word
names must survive `_fit_to_limit` intact — every word of the resolved name
appears in the final headline (no orphans like `Save up to 46% to Fernando`).

**`from_price` guarantee.** Every priced ad group surfaces the literal
`$<price>` token in at least one headline or description. Enforced by a
post-pass in `generate_rsa_variants` that force-injects the operator's example
shape (`Get a great deal on flights to {name} with prices from $X`) into the
`price_led` variant when no variant naturally surfaced it.

**v0.3.4 fixes (review-driven, 2026-05-21):**

1. **Orphan first-name truncations** — `_try_destination_head_token` surfaces
   the destination's primary token from 3+ word names: `Fernando De Noronha`
   → `Noronha`, `San Carlos De Bariloche` → `Bariloche`,
   `Bandar Seri Begawan` → `Begawan` (via internal Romance-particle slicing
   or last-word fallback). Plus `_fill_pattern` now computes pattern-aware
   name budget (rendering all other tokens first, measuring residual) instead
   of the chronic `max_chars - 4` under-allocation.
2. **PKC source-transcription typo** — `Petropavlovsk-Kamchats, Russian
   Federation` → `Petropavlovsk-Kamchatsky` via cleaner diff.
3. **`Cheap Flights to {name}` banned phrase** — `_BANNED_HEADLINE_PREFIX_RE`
   filters any line starting with `Cheap …` from both keyword-fallback paths
   AND the `_fill_pattern` post-render guard. Keyword pool unchanged.
4. **Trustpilot-collision triple** in `social_proof` text=3 — kept the pinned
   `4.5★ on Trustpilot`, dropped `Trustpilot rated 4.5★` and `4.5★ Trustpilot
   reviews` (replaced with `Real prices, no markup` and `Trusted by 1.5M
   travelers`).
5. **PKC pinned D1 lost from_price** — resolved transitively by 3.2 + the
   new name budget; D1 now ships `Petropavlovsk-Kamchatsky fares from $224.
   Compare 800+ airlines, free 24h cancellation`.
6. **Fares-update collision triple** in `urgency` text=4 — kept
   destination-anchored `{name} fares update hourly`, dropped `Fares update
   every hour` and `Fares updated hourly` (replaced with `Search live
   inventory` and `Inventory refreshes hourly`).

**Pattern pack version:** `data/en/ad_copy_patterns.json` is now v4.1.

**Audit + spell-check gates** (all return 0 failures on the 963-destination
etraveli catalog):
```
python -m scripts.audit_v034         # Missions 2/3/4a/4b
python -m scripts.spell_check_rsas   # 0 flagged tokens, 0 occurrences
python -m scripts.stratified_rsa_sample  # writes QA-SAMPLE-v034.md
```

**Scale verification (2026-05-21):**
```
SEM_DISABLE_LLM=1 sem case run etraveli
→ 963 ad groups, 4,580 RSAs, 943 promotions, 1 lead form (in ~13 seconds)
```

## Alias harvesting — match-broadening for duplicate source rows (v0.3.6)

The etraveli source has 33 IATA codes listed under multiple names (`Bali`
/ `Denpasar Bali` / `Bali Denpasar` all at DPS; `Saigon` / `Ho Chi Minh
City` both at SGN; `Rio` / `Rio De Janeiro` at RIO; `Dallas` / `Fort
Worth` / `Ft Worth` at DFW; etc.). The loader's primary-key dedup
collapses them to 964 unique ad groups — which is correct for ad-group
structure (one IATA = one URL = one campaign entity).

But the alternate names ARE valuable as **keyword variants**: someone
searching `"Denpasar flights"` should still hit DPS, even though the
ad-group's canonical name is `"Bali"`. The loader now harvests every
prior name into `CatalogRow.aliases` (case-insensitively deduplicated
against the canonical name + each other, preserving source order).
`Product.aliases` carries this through. `generate_keywords_for_product`
expands each `{name}`-templated keyword across every alias variant —
templates without `{name}` (e.g. `{sku} flights`) render once per product.

**Reconciliation of the 999 → 963 row count** (operator-facing):
```
999  source XLSX rows (excl. header — brief rounds to 1,000)
-35  duplicate IATA codes collapsed (same destination, alt name = alias)
  → 964 unique IATA codes
 -1  NY → NYC collision merge in accepted_proposal.json
  → 963 ad groups
```
Zero destinations are lost; every alternate name becomes a keyword
variant on the right ad group.

**Etraveli delta after enabling aliases**: 9,622 → 9,894 keywords (+272
match-broadening variants). 33 ad groups gain expanded coverage: 30 with
+8 keywords each (one alias), 2 with +6 (alias + SKU/name dedup
collision), 1 (DFW) with +16 keywords (two aliases — "Fort Worth" +
"Ft Worth" beyond the canonical "Dallas").

**Tests** (`tests/test_catalog_loader.py` + `tests/test_keyword_templating.py`):
- Duplicate primary keys collect prior names into aliases (in order).
- Aliases that case-match the canonical name dedupe at both load AND
  keyword-generation time.
- Templates without `{name}` don't multiply across aliases.
- Products without aliases behave identically to the pre-v0.3.6 contract.

## Seasonality bidding — temporary discount-pct overlays (v0.3.5)

The operator brief asks for *"temporarily steer bidding based on the
discount percentages, but also have overall target guidance and control."*
The bid-rules engine answers with a two-layer system:

**Layer 1 — Base ladder (always-on)**: 10-band discount-driven
`bid_modifier` (50%+ → 2.25×, …, sub-$100 → 1.10×). First-match-wins.

**Layer 2 — Seasonality overlays (time-windowed)**: rules with a `during:
{start, end}` clause act as overrides while `today ∈ [start, end]`. Outside
the window they're skipped for the immediate decision and Layer 1 fires
underneath. Either way they emit a `BidSchedule` row in
`10_bid_schedules.csv` so the operator can audit the full year's plan.

Place overlays FIRST in `case.yaml::bid_rules:` — the engine evaluates in
order, locks the first matching overlay (per window) for the immediate
decision when active, then continues until a base rule wins for fallthrough
cases.

Example (matches etraveli's case.yaml — SUMMER_SALE window matches the
promotion-extension `start_date` → `end_date`):

```yaml
bid_rules:
  # Active 2026-05-20 → 2026-08-31. Overlays for 30%+/40%+/50%+ tiers.
  - if: "discount_pct >= 0.50"
    during: { start: 2026-05-20, end: 2026-08-31 }
    then: { modifier: 3.00, reason: "SUMMER_SALE overlay — 50%+ tier" }
  - if: "discount_pct >= 0.40"
    during: { start: 2026-05-20, end: 2026-08-31 }
    then: { modifier: 2.75, reason: "SUMMER_SALE overlay — 40-49% tier" }
  - if: "discount_pct >= 0.30"
    during: { start: 2026-05-20, end: 2026-08-31 }
    then: { modifier: 2.50, reason: "SUMMER_SALE overlay — 30-39% tier" }
  # Base ladder beneath.
  - if: "discount_pct >= 0.50"
    then: { modifier: 2.25 }
  - if: "discount_pct >= 0.40"
    then: { modifier: 2.00 }
  # ... etc.
```

**Semantics covered by tests** (`tests/test_catalog_bid_rules.py`):
- During-rule fires immediately when `today ∈ window`.
- During-rule falls through to base when `today` is outside.
- Same-window cascading rules (50%+ → 40%+ → 30%+) emit only the FIRST
  matching schedule (so `10_bid_schedules.csv` shows one row per
  product/window, not duplicates for cascading bands).
- DIFFERENT windows (summer + winter) each emit their own schedule.

**Live application via `sem case apply-bids <slug>`**: re-applies today's
plan to an EXISTING campaign's ad groups via `AdGroupService.mutate` with
a `cpc_bid_micros`-only FieldMask. Use as a daily cron after the initial
push so window flips propagate without re-creating the campaign.

```bash
# Initial push (PAUSED, today's modifiers baked in)
sem case push etraveli --auto-suffix --skip-lead-forms --yes

# Daily refresh — adjusts cpc_bid_micros = base × today's_modifier
sem case apply-bids etraveli --name-suffix "[<same suffix>]" --yes
```

Verification (today is 2026-05-21, inside SUMMER_SALE window):
```
Bid schedules:  486 (170 × 50%+ tier, 173 × 40-49%, 143 × 30-39%)
Ad-group bid_modifier distribution in the live build:
  3.00×: 170 (50%+ band — SUMMER overlay active)
  2.75×: 173 (40-49% band — SUMMER overlay active)
  2.50×: 143 (30-39% band — SUMMER overlay active)
  1.60×:  86 (25-29% band — base ladder)
  1.45×:  68 (20-24% band — base ladder)
  1.30×:  88 (15-19% band — base ladder)
  ... etc.
```

On 2026-09-01 the same `case.yaml` regenerates with the overlays dropped:
50%+ → 2.25×, 40-49% → 2.00×, 30-39% → 1.80× (base ladder).

## Multi-day resume push (v0.3.7) — completed + hardened

`sem case push <slug> --resume <campaign_id> --name-suffix " [<orig suffix>]"`
snapshots the live campaign once and pushes only the missing entities. The
etraveli campaign `23867614686` (469-180-7001) was completed this way across
2026-05-22 → 05-24. Final authoritative state: 963 ad groups, 9,880 keywords,
3,589 RSAs (3–5/ad group), 8 campaign assets (4 sitelinks + 4 callouts), 943
ad-group promotions, PAUSED. See `.planning/v0.3.7-LIVE-PUSH.md`.

**Resume gotchas (each now a regression test in `tests/test_campaign_pusher.py`):**
- **GAQL SELECT must include every cross-resource WHERE field.** Snapshot queries
  filter `WHERE campaign.id = X` from `ad_group`/`ad_group_ad`/etc., so they MUST
  also `SELECT campaign.id` — else v23 raises
  `EXPECTED_REFERENCED_FIELD_IN_SELECT_CLAUSE`. Same-resource filters
  (`ad_group_ad.ad.type` on `FROM ad_group_ad`) don't need selecting. The test
  fake now validates this rule.
- **Asset-type detection uses `field_type.name`, not `str(field_type)`.** The
  latter is the numeric enum value (`"13"`), so the old `"SITELINK" in str(...)`
  check never matched and resume re-created all assets (951 duplicate links per
  run). Promotions live on `ad_group_asset` (not `campaign_asset`) and are skipped
  **per ad group** via `existing_promotion_ag_rns`.
- **GAQL `search` reporting lags the mutate layer by many minutes** for asset
  links — a successful removal still shows the link present. Never confirm an
  asset mutation with `search`; use a `validate_only` remove
  (`RESOURCE_NOT_FOUND` = gone). `scripts/dedupe_campaign_assets.py` cleans
  duplicate links and tallies `response.results` (not the requested count).
- **`partial_failure` errors don't carry `policy_finding_details`.**
  `_extract_policy_topics` decodes the specific PROHIBITED topic, but only a full
  (non-partial) mutate's `GoogleAdsException` populates it — use a `validate_only`
  create to name the topic for the ~991 RSA variants Google rejected.

## Authentication

OAuth 2.0 flow for Google Ads API access:

1. `sem auth setup` — prints Google Cloud project setup guide
2. Place `client_secret.json` in `~/.sem-master/credentials/`
3. `sem auth login` — opens browser for OAuth consent
4. Tokens stored in OS keyring (Fernet-encrypted file fallback)
5. Auto-refresh on expiry

## Skills

8 skills installed at `~/.claude/skills/sem-*`:
- `sem-master` - Orchestrator, main entry point
- `sem-intake` - Client onboarding
- `sem-research` - Data collection / scraping
- `sem-competitor-ads` - Competitor intelligence
- `sem-keywords` - Keyword research & grouping
- `sem-campaign-builder` - Campaign structure & ad copy & CSV export
- `sem-report` - Report generation
- `sem-seo` - SEO analysis (on-page + technical)

## Key Conventions

- **Language**: All ad copy and client-facing output in Swedish
- **Character limits**: Headlines max 30 chars, descriptions max 90 chars (enforced by Pydantic validators in `src/models/campaign.py`)
- **Review model**: Uses `review_date` field (not `date`) to avoid shadowing the type
- **CSV export**: UTF-8 BOM encoding for Excel compatibility
- **Swedish market constants**: Sweden geo ID 2752, Swedish language ID 1053
- **Match type strategy**: <10K SEK exact+phrase, 10-30K phrase primary, >30K broad+smart bidding
- **Client data**: Stored in `clients/{name}/` with subdirs for intake, research, competitors, keywords, campaigns, reports, seo
- **Workflow state**: `clients/{name}/account.yaml` tracks pipeline state per client
- **Config**: Global config at `~/.sem-master/config.yaml`, per-client at `clients/{name}/account.yaml`
- **Dry-run mode**: `--dry-run` flag on all pipeline/stage commands uses synthetic data; no API credentials needed
- **Templates**: Stored at `~/.sem-master/templates/`, client-specific data replaced with `{Foretag}/{website}` placeholders
- **Audit**: Live data fetched via Google Ads SDK, compared case-insensitively against campaign plan

## API Keys

Google Ads now uses OAuth 2.0 — no direct API key fields in `.env`:

- **Google Ads OAuth**: Managed via `sem auth login` (credentials stored in OS keyring)
- **Developer token**: Set via `sem config set developer_token YOUR_TOKEN` (or `GOOGLE_ADS_DEVELOPER_TOKEN` in `.env`)
- **Ad copy generation**: Routes through the local `claude` CLI (Claude Code OAuth session) via subprocess — no Anthropic API key required. Falls back to deterministic Swedish templates if `claude` is not on PATH. Set `SEM_DISABLE_LLM=1` in `.env` to force template-only behavior.
- **SPYFU_API_KEY**: Optional, for competitor intelligence (set in `.env`)
- **VALUESERP_API_KEY**: Optional, for SERP data (set in `.env`)

## Running Tests

```bash
python -m pytest tests/ -v
```
