# Competitor Analysis — Requirements & Goals

**Status:** Draft v2 — post-review, pre-architecture
**Date:** 2026-04-30
**Owner:** davidg-rgb
**Review:** `.planning/COMPETITOR_REQUIREMENTS_REVIEW.md` (19 findings; v2 incorporates all P0 + P1 items)

---

## 1. Goal

Give SEM Master a **competitor intelligence module** that, for any onboarded client, can:

1. **Suggest** likely competitors (direct and indirect) without requiring the user to know them in advance.
2. **Pull every Google Ads creative** each competitor is currently running, via the public Google Ads Transparency Center.
3. **Infer the most likely target keywords** behind each ad, using ad copy + landing page content.

The output is a structured competitor profile per client that feeds the rest of the SEM pipeline (keyword research, ad copy generation, strategy report) and stands on its own as a strategic deliverable.

---

## 2. Non-goals (explicitly out of scope for v1)

- Paid third-party data sources (SpyFu, SEMrush, Ahrefs).
- SERP-position verification of inferred keywords (deferred to v2 when budget allows ValueSerp / SerpAPI).
- Ad spend estimation.
- Backlink / domain authority comparison.
- Social media presence comparison.
- Historical ad-change tracking ("what changed at competitor X this month").
- Competitor pricing scraping.

These are valid future features but kept out to keep v1 shippable and useful on its own.

---

## 3. Definitions

| Term | Definition |
|---|---|
| **Direct competitor** | Offers the same or similar services to the same target audience as the client. *Example for an ADHD clinic: another private ADHD clinic.* |
| **Indirect competitor** | Targets the same audience but with different services that satisfy a similar underlying need. *Example for an ADHD clinic: regional public mental health services, generalist psychologists, online mental health apps.* |
| **Uncertain** | The LLM classifier could not confidently place the candidate as direct or indirect. Surfaced for human confirmation in `sem competitors review`. |
| **Candidate** | A discovered business that has not yet been classified. |
| **Confirmed competitor** | A candidate that has passed classification (or human review of `uncertain`) and been retained in the client's competitor set. |

---

## 4. User flow

### CLI surface (proposed)

```bash
sem competitors discover <client>           # Auto-suggest candidates, classify direct/indirect/uncertain, save shortlist
sem competitors review <client>             # Interactive review: confirm / reject / re-classify (resolves uncertain)
sem competitors ads <client>                # Pull all Transparency Center ads for confirmed competitors
sem competitors keywords <client>           # Run LP+LLM inference on each ad, produce keyword candidates
sem competitors run <client>                # Full flow: discover → review → ads → keywords (today's command, expanded)
```

`sem competitors run <client>` becomes the single-command "do everything" entry point. Sub-commands let advanced users re-run individual stages without redoing the rest.

### Inputs

- `clients/{name}/intake/client_profile.json` — must exist (services, target audience, geo, industry, known_competitors as seed)
- `clients/{name}/research/digital_presence.json` — client's site data (used as anchor for "similar to this")
- Optional: `--max-candidates N` (default 20), `--max-ads-per-competitor N` (default 50)

### Outputs

```
clients/{name}/competitors/
├── candidates.json              # Discovery raw output (all suggested businesses + sources)         [P2]
├── competitors.json             # Confirmed competitors with classification (extended schema)        [P3]
├── ads/
│   ├── {competitor_slug}.json   # All Transparency Center ads per competitor                         [P1]
│   └── ...
├── keywords/
│   ├── {competitor_slug}.json   # Inferred keyword candidates per ad                                 [P4]
│   └── ...
├── cost_log.json                # Per-run LLM cost accounting                                        [P3]
└── competitor_report.md         # Human-readable strategic summary                                    [P5]
```

---

## 5. Functional requirements

### 5.1 Competitor discovery

The module must propose candidate competitors **without** the user pre-listing them. Sources for v1, in priority order:

1. **GBP nearby search** — **NEW CODE REQUIRED.** The existing `gbp_scraper.py` is profile-by-name only (signature: `scrape_gbp(business_name, location)` returning a single profile). It does **not** support category-based discovery. P2 must add `find_local_businesses(category: str, location: str, radius_km: int = 25)` that scrapes Google Maps category-search results and returns a list. *Estimate: 1–2 days. Acceptance: `find_local_businesses('tandläkare', 'Stockholm')` returns ≥5 results with name + domain + GBP URL.* High signal for direct competitors in regulated/local industries (clinics, law firms, restoration services).
2. **Client intake `known_competitors` seed** — always included as confirmed direct candidates.
3. **Outbound link mining** — scan client's own site for external links to industry peers, association directories, "see also" mentions. **Filter rule:** drop links to a hardcoded blacklist (google.*, facebook.*, instagram.*, linkedin.*, youtube.*, twitter.*, x.com, cdn.*, jsdelivr, googleapis, gstatic, fonts.*, analytics.*); LLM-classify the remainder for "is this an industry peer?" before promoting to candidate. Low yield expected — drop the source if filter cost outweighs hit rate.
4. **LLM-assisted ideation** — given client profile (industry, services, geo, target audience), Claude proposes likely competitor types and named examples. Especially useful for **indirect** competitors which GBP cannot find.

**Required output per candidate:**
- name, domain, source (gbp/intake/site-link/llm), discovery_confidence (high/medium/low), brief description

**Deduplication:** by domain (canonicalized). When the same business appears from multiple sources, merge and boost confidence.

### 5.2 Direct vs indirect classification

For each candidate that passes the discovery filter:

1. **Scrape the candidate's homepage.** **NEW CODE REQUIRED.** Do *not* reuse `site_crawler.py` — it launches Playwright and runs BFS, both overkill for single-page extraction at the ≥20-candidate scale. Build a thin httpx + BS4 helper `fetch_homepage_summary(domain) -> dict` in `src/scrapers/competitor_homepage.py` that returns `{title, h1, meta_description, headings, body_text_first_500_words, outbound_link_count}`.
2. Extract: services offered, target audience signals, industry, geographic footprint.
3. LLM classification call (Claude):
   - **Inputs:** client profile + candidate homepage extract
   - **Output:** `direct` | `indirect` | `uncertain` | `not_a_competitor` + one-sentence rationale
4. Apply the rule:
   - **Direct** = same/similar services AND same target audience
   - **Indirect** = same target audience AND different services that satisfy a similar need
   - **Uncertain** = ambiguous service/audience overlap; surface to human review
   - **not_a_competitor** = different audience OR no audience overlap (excluded from competitors.json)

**Classifications must be inspectable.** Each saved competitor record stores the rationale so the user can audit decisions during `sem competitors review`.

### 5.3 Transparency Center ad scraping

**Current state — read carefully.** The existing `src/scrapers/transparency_scraper.py` is **not just unverified, it is broken.** At lines 122–128 it constructs `TransparencyAd(advertiser_name='', ad_text=..., ad_format=..., date_range=..., geo_targeting=...)` but the Pydantic model in `src/models/competitor.py:10–16` does not declare `date_range` or `geo_targeting` — the model has `first_seen`, `last_seen`, `regions` instead. Pydantic v2 rejects unknown fields by default, so the scraper has never run successfully. The selectors are also speculative and have never been validated against the live DOM.

**P1 ordering — strict:**

1. **Fix the model–scraper mismatch first.** Extend `TransparencyAd` per §6, then update the scraper to populate the new fields (`landing_page_url`, `image_url`, `advertiser_id`, `ad_headlines`, `ad_descriptions`, `first_seen`, `last_seen`, `regions`).
2. **Then verify selectors against the live DOM.** Acceptance: run `scrape_transparency('Klarna')` against the live site; assert `len(ads) ≥ 10`, every ad has non-empty `ad_text`, non-null `landing_page_url`, and populated `advertiser_id`. If any are null, fix the selectors before declaring P1 done.
3. **Then wire the scraper into CLI.** `competitors_commands.py` currently builds empty `transparency_ads: []` stubs in non-dry-run mode; replace this so `sem competitors ads <client>` actually invokes `transparency_scraper.scrape_transparency()` for each confirmed competitor.

**Required behavior (post-fix):**
- Search by competitor name + domain (existing scraper signature is correct)
- Paginate through *all* available ads (current scraper caps at 5 pages — make this configurable, default uncapped with hard ceiling at 200 ads per competitor)
- Extract per ad:
  - `ad_text` (headlines + descriptions if separable into `ad_headlines` / `ad_descriptions`)
  - `ad_format` (text / image / video / responsive)
  - `landing_page_url` ⚠️ **required for keyword inference**
  - `image_url` (if applicable)
  - `first_seen` / `last_seen` dates
  - `regions` / geo targeting (if Transparency Center exposes it)
  - `advertiser_id` (Transparency Center URL fragment)
- Handle missing fields gracefully (Transparency Center exposes different metadata per ad type)
- Rate limit: max 1 request per 2 seconds, retry on 429 with exponential backoff
- Persist raw HTML snapshot per scrape for debugging in `clients/{name}/cache/transparency_html/` (gitignored, 7-day TTL)

### 5.4 Keyword inference (Option A: LP + LLM)

For each ad pulled in 5.3, infer 5–10 most likely target keywords:

1. **Landing page mining** — fetch `landing_page_url` (cached, see below), extract:
   - Title, H1, H2s
   - First 200 words of body content
   - Repeated lemmatized tokens. **Concrete pipeline:** tokenize on whitespace + punctuation, lemmatize each token via `simplemma.lemmatize(token, lang='sv')`, drop tokens in `data/swedish/stopwords.json`, count occurrences, return top 20. *(Note: simplemma is a lemmatizer, not a noun-phrase chunker — this is token-frequency analysis, which is sufficient signal in combination with the LLM.)*
2. **LLM inference** — single Claude call per *unique* (ad_text, landing_page_url) pair with:
   - **Inputs:** ad copy + landing page extract + client industry + Swedish-market context
   - **Prompt task (in Swedish, since client-facing output is Swedish per CLAUDE.md):** "Givet följande annons och dess landningssida, lista 5–10 sökord som annonsören sannolikt budar på, rangordnade efter sannolikhet. För varje sökord, ange intent (transactional / informational / navigational) och confidence (high / medium / low). Svara på svenska."
3. **Output schema per ad:**
   ```json
   {
     "ad_id": "...",
     "ad_text": "...",
     "landing_page_url": "...",
     "inferred_keywords": [
       {"keyword": "ADHD utredning Stockholm", "intent": "transactional", "confidence": "high", "reasoning": "Both ad and LP target Stockholm geo + service term"}
     ]
   }
   ```

**Cost control:**
- LP cache location: **`clients/{name}/cache/competitor_lp/`** (per-client, not global). Filename = SHA-256 of canonical URL. 24h TTL enforced on read. `sem accounts remove` cleans the entire client dir, including this cache.
- One LLM call per *unique* (ad_text, landing_page_url) pair, not per ad.
- Default model: `claude-haiku-4-5-20251001` (cost-effective for this); `--llm-tier sonnet` flag upgrades to `claude-sonnet-4-6` and **automatically scales the cost cap by 5×**.
- **Hard cost cap: 10 SEK per client run on Haiku, 50 SEK on Sonnet.** Estimate basis: 10 competitors × 30 ads × 0.4 LP-dedup factor + 20 classification calls + 1 ideation call ≈ 140 Haiku calls @ ~$0.0045 = ~$0.63 ≈ 6.60 SEK. Cap at 10 SEK gives margin. Cost is tracked per-call, persisted to `clients/{name}/competitors/cost_log.json`, and checked before each call. If a call would exceed the cap, the run aborts with the partial results retained.

**Concurrency commitment:**
- LLM calls (classification, ideation, keyword inference) run concurrently with `asyncio.Semaphore(N=8)`. LP fetches (httpx) use the same pattern at `Semaphore(N=10)`. Without this, sequential execution blows the §10 5-minute runtime budget.
- Transparency Center scraping remains serialized at 1 req / 2s per competitor (rate-limit constraint, not concurrency-amenable).

**Honesty in output:** report wording must make it explicit that these are *inferred candidates*, not verified bids. v1 cannot confirm what a competitor actually bids on.

### 5.5 Report integration

Generate `competitor_report.md` (and PDF via existing `markdown-pdf` pipeline) **in Swedish** (per `CLAUDE.md`: "All ad copy and client-facing output in Swedish"). Sections:
- Executive summary (count of direct/indirect competitors, total ads pulled, keyword themes)
- Per-competitor section: classification + rationale, ad count, sample ads, top inferred keywords, LP themes
- Keyword overlap matrix: client keywords (from `keywords` stage if completed) vs competitor inferred keywords → gap and overlap analysis

The visual PDF style established in `scripts/generate_visual_seo_pdf.py` should be reused for consistency.

---

## 6. Data model changes

### Extended `TransparencyAd` (src/models/competitor.py)

```python
class TransparencyAd(BaseModel):
    advertiser_name: str
    advertiser_id: str | None = None        # NEW
    ad_text: str
    ad_headlines: list[str] = []            # NEW (when separable)
    ad_descriptions: list[str] = []         # NEW
    ad_format: str = ""                     # text|image|video|responsive
    landing_page_url: str | None = None     # NEW — required for kw inference
    image_url: str | None = None            # NEW
    first_seen: date | None = None
    last_seen: date | None = None
    regions: list[str] = []
    inferred_keywords: list[InferredKeyword] = []  # NEW
```

### New `InferredKeyword`

```python
class InferredKeyword(BaseModel):
    keyword: str
    intent: Literal["transactional", "informational", "navigational"]
    confidence: Literal["high", "medium", "low"]
    reasoning: str
```

### Extended `CompetitorProfile`

```python
class CompetitorProfile(BaseModel):
    name: str
    domain: str
    classification: Literal["direct", "indirect", "uncertain"]   # NEW (uncertain resolved via review)
    classification_rationale: str                                # NEW
    discovery_source: str                                        # NEW (gbp|intake|site-link|llm)
    discovery_confidence: Literal["high", "medium", "low"]       # NEW
    homepage_summary: str | None = None                          # NEW (services, audience extracted)
    transparency_ads: list[TransparencyAd] = []
    estimated_monthly_spend_sek: float | None = None             # kept, but unused in v1
    ad_copy_patterns: list[str] = []
    inferred_keyword_themes: list[str] = []                      # NEW (clustered from per-ad inference)
    top_keywords: list[str] = []                                 # DEPRECATED — populated from inferred_keyword_themes for one release, removed in v2
```

### New `CompetitorCandidate` (pre-classification)

```python
class CompetitorCandidate(BaseModel):
    name: str
    domain: str
    description: str = ""
    source: Literal["gbp", "intake", "site-link", "llm"]
    discovery_confidence: Literal["high", "medium", "low"]
    raw_data: dict = {}
```

---

## 7. Pipeline integration

### Where this sits

Currently the SEM pipeline is: `intake → research → competitors → keywords → campaign → validate → export → report` (verified against `src/accounts/state.py:10–19`).

The expanded competitors stage:
- Reads from `intake` (client profile) and `research` (client's own site data)
- Writes to `clients/{name}/competitors/`
- **Feeds keywords stage** — `inferred_keyword_themes` from competitors becomes seed input for the client's own keyword research, expanding the seed pool beyond intake-provided keywords. **Integration point:** `sem keywords run` reads `clients/{name}/competitors/competitors.json` if present and merges `inferred_keyword_themes` into its seed set before expansion.
- **Feeds campaign stage** — competitor ad copy patterns inform what *not* to copy and where positioning differentiation is needed
- **Feeds report stage** — competitor section becomes a chapter in the strategy report

### Backwards compatibility

`sem pipeline run <client>` already invokes `competitors` as stage 3. The expanded version must:
- Default to discovery + classification + ads + keywords in one call
- Accept `--skip-discovery` to use only `known_competitors` (matches today's behavior)
- Accept `--skip-keywords` to skip the LLM-cost phase
- Continue producing `competitors.json` at the existing path. Schema is **additive plus one deprecation**: `top_keywords` is kept as a deprecated field (populated from `inferred_keyword_themes`) for one release and removed in v2.

### Migration

Both existing clients (`benalexis`, `novapsykiatri`) currently have **no `competitors/` directory** at all (only `seo/` artifacts exist). Migration is N/A — existing clients can be re-run from intake without data loss when the new flow ships.

---

## 8. Open questions remaining after review

The original v1 had 6 open questions. Four were resolved by code inspection during review (§8 q1, q3, q4, q6 — see `.planning/COMPETITOR_REQUIREMENTS_REVIEW.md` "Resolved open questions"). Two remain:

1. **Transparency Center DOM stability.** Selectors are speculative *and* the scraper has a Pydantic mismatch (see §5.3). P1 step 1 fixes the mismatch; P1 step 2 verifies selectors against live DOM. If the DOM has fundamentally changed and the speculative selectors fail entirely, fallback options need investigation (manually inspecting current Transparency Center DOM structure, considering a rewrite from scratch). This is a known risk on P1.

2. **Indirect-competitor discovery quality.** GBP nearby search (even after building `find_local_businesses`) and site-link mining are weak for indirect competitors by definition — they share customer behavior, not industry codes. **All indirect competitors will come from LLM ideation.** Prompt design for LLM ideation is critical and likely needs iteration after P2 ships. Plan for prompt-tuning loop in P2 acceptance.

---

## 9. Build phases

| Phase | Scope | Acceptance |
|---|---|---|
| **P1 — Foundation** | (a) Add `anthropic` to `pyproject.toml` and build `src/apis/anthropic_client.py` (async wrapper, per-call cost tracking, 429 retry, configurable model). (b) Fix `TransparencyAd`–scraper Pydantic mismatch (see §5.3 step 1). (c) Verify Transparency Center selectors against live DOM (see §5.3 step 2). (d) Wire scraper into CLI for `known_competitors` only (no discovery yet). | `sem competitors ads <client>` pulls real ads from Transparency Center for any name in `known_competitors`. Smoke test: `scrape_transparency('Klarna')` returns ≥10 ads with non-null `landing_page_url` and `advertiser_id`. |
| **P2 — Discovery** | Build `find_local_businesses(category, location)` in `gbp_scraper.py`. Site-link mining with blacklist + LLM filter. LLM ideation. Build `fetch_homepage_summary` in new `competitor_homepage.py`. Produce `candidates.json`. Implement `sem competitors discover` and `sem competitors review`. | Module proposes ≥10 candidates for the test fixtures `benalexis` and `novapsykiatri` without their `known_competitors` being filled. |
| **P3 — Classification** | LLM-driven `direct`/`indirect`/`uncertain`/`not_a_competitor` classification with rationale. Extend `CompetitorProfile`. Cost tracking persisted to `cost_log.json`. | Every candidate has a classification + inspectable rationale; `uncertain` items are flagged for human review; `sem competitors review` allows manual override; cost cap enforced. |
| **P4 — Keyword inference** | LP scraping (cached, 24h TTL, per-client cache dir). LLM inference per unique (ad_text, LP) pair, output `InferredKeyword` per ad. Concurrency via `asyncio.Semaphore(8)`. | Every ad has 5–10 ranked candidate keywords with intent + confidence + reasoning. Total LLM cost on test fixtures ≤ 10 SEK on Haiku. Total runtime ≤ 5 min on test fixtures. |
| **P5 — Report & integration** | Visual PDF report in Swedish (style of `seo_visual_report.pdf`). Feed `inferred_keyword_themes` into keywords stage seed pool via `sem keywords run` integration point. | Single command `sem competitors run <client>` produces full Swedish PDF report; downstream `sem keywords run` shows expanded seed list including competitor themes. |

Each phase ends with a tested deliverable. P1 + P2 alone is already shippable as "competitor identification + ad pull" — keyword inference (P4) can ship later if needed.

---

## 10. Success criteria

The module is considered shipped (v1 complete) when, for the test fixtures `benalexis` and `novapsykiatri`:

- [ ] `sem competitors discover <client>` proposes ≥10 candidates with sources cited
- [ ] At least 3 candidates are classified as **indirect** or **uncertain → confirmed indirect via review** (e.g., for novapsykiatri: regional vårdcentraler, online psychology platforms)
- [ ] `sem competitors ads <client>` pulls real ads from Transparency Center for ≥5 confirmed competitors
- [ ] Every ad has ≥5 inferred keywords with reasoning
- [ ] Generated PDF report (Swedish) is presentable to a paying client without manual editing
- [ ] Total run time < 5 minutes per client (with concurrency); total LLM cost < 10 SEK per client run on Haiku
- [ ] Existing `sem pipeline run <client>` still works end-to-end with no regressions

---

## 11. Deferred to architecture stage

The following are required for v1 implementation but belong in the architecture document (`COMPETITOR_ANALYSIS_ARCHITECTURE.md`, to be written next), not in requirements. They are listed here so they are **not forgotten**:

1. **Error handling matrix.** Per-failure-mode policy for: Transparency Center returns zero results (legitimate), CAPTCHA / bot block, Playwright crash on launch, LP fetch 4xx/5xx, malformed LLM JSON, cost cap exceeded mid-run, network timeout. Default direction (per §11 anti-goals): never silent fallback to dry-run; mark stage `failed` or `completed_with_warnings`; persist partial results.

2. **Idempotency rules.** Re-run behavior of each sub-command. Default direction: `discover` reuses `candidates.json` unless `--force`; `review` decisions stored under `_user_overrides` key in `competitors.json` and survive re-discovery; `--force-rediscover` is the explicit re-classify-everything escape hatch.

3. **Test strategy.** Mirror `tests/test_pipeline_dry_run.py` with `tests/test_competitor_pipeline_dry_run.py` using fixture HTML for Transparency Center + monkeypatched LLM calls. Update `tests/test_models.py` for new fields. Required pre-merge: `python -m pytest tests/ -v` passes. Failed claim F5 in the review (Pydantic mismatch on TransparencyAd) is direct evidence that test coverage on competitor models is missing today — fix during P1.

4. **Anthropic SDK design.** Async client wrapper, retry policy, cost tracking, model selection logic, prompt template management. Sketched as P1(a) above; full design lives in architecture doc.

---

## 12. Anti-goals (things we will *not* do, even if tempting)

- **No SERP scraping of Google.** It's against ToS and IP-fragile. We wait for paid SERP API budget.
- **No claim that inferred keywords are confirmed targeting.** Output language must always say "likely" / "candidate" / "inferred".
- **No silent fallback to dry-run.** If Transparency Center scraping fails, we surface the error — we don't pretend we have data.
- **No competitor scraping outside the listed sources.** Each new source must be a deliberate, documented addition.
- **No Anthropic SDK use without cost tracking.** Every LLM call must increment `cost_log.json`. Cap is enforced before the call, not after.
