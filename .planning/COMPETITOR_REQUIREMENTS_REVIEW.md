# Review of COMPETITOR_ANALYSIS_REQUIREMENTS.md

## Verdict

**Needs revision before architecture.** The doc is well-organized and the scope is roughly right, but it rests on three load-bearing claims about the existing codebase that are wrong or misleading: (a) ANTHROPIC_API_KEY is "already required for ad copy generation" — no Anthropic SDK is imported anywhere in the repo; (b) `site_crawler.py` has a "single-page mode" — it does not, only a `max_pages` parameter; (c) the GBP scraper can be "reused for nearby search" — it cannot, it is profile-by-name only. Plus an internal contradiction (§6 forces binary classification while §8 question 6 proposes uncertain states), an LLM cost cap that is roughly 2× too low, and material gaps (no error-handling spec, no idempotency story, no test strategy, no migration plan). P1 is reasonably executable; P2 needs an explicit "GBP scraper is going to need new code" footnote before a junior dev can start.

## Verified claims

| # | Claim | Evidence |
|---|---|---|
| 1 | `src/scrapers/transparency_scraper.py` exists, ~134 lines, uses Playwright | `wc -l` = 134; imports `playwright.async_api` at line 8 |
| 2 | Speculative selectors `.creative-card, [data-creative], .ad-card, [role='listitem']` | `transparency_scraper.py:88-90` (verbatim) |
| 3 | Pagination capped at 5 pages | `transparency_scraper.py:59` — `while has_more and page_count < 5` |
| 4 | `competitors_commands.py` builds empty `transparency_ads: []` stubs in non-dry-run | `competitors_commands.py:121` — `"transparency_ads": []` inside the non-dry-run branch |
| 5 | Comment "Real scraper integration is handled by sem-competitor-ads skill in a later phase" | `competitors_commands.py:111` (verbatim) |
| 6 | `simplemma` is in the stack | `pyproject.toml:21` — `"simplemma>=1.1"`; used at `src/utils/swedish_nlp.py:8` |
| 7 | `markdown-pdf` is in the stack and used today for PDF generation | `pyproject.toml:18` — `"markdown-pdf>=1.13"`; `src/generators/pdf_generator.py:27` imports `MarkdownPdf` |
| 8 | Pipeline order `intake → research → competitors → keywords → campaign → validate → export → report` | `src/accounts/state.py:10-19` — `PIPELINE_STAGES` matches verbatim |
| 9 | `clients/{name}/competitors/competitors.json` is today's output path | `competitors_commands.py:131` |
| 10 | `scripts/generate_visual_seo_pdf.py` exists and produces visual PDFs | File exists; `clients/novapsykiatri/seo/seo_visual_report.pdf` is its output |
| 11 | `gbp_scraper.py` exists | `src/scrapers/gbp_scraper.py` (123 lines) |
| 12 | `site_crawler.py` exists | `src/scrapers/site_crawler.py` (126 lines) |

## Failed claims

| # | Claim | Reality | Evidence |
|---|---|---|---|
| F1 | "`ANTHROPIC_API_KEY` is already required in `.env` for ad copy generation. We piggyback on that — no new credentials needed. ✓" (§8 q3) | The env var is **read into config but never used**. There is no `import anthropic` anywhere in `src/`, no `anthropic` package in `pyproject.toml`, and `src/generators/ad_copy_generator.py` is a pure-Python rule-based generator that loads JSON data files — it never calls Claude. The "✓" checkmark is wrong. | `pyproject.toml:10-30` (no anthropic dep), grep for `import anthropic` returns zero matches, `ad_copy_generator.py:1-60` is rule-based |
| F2 | "Scrape the candidate's homepage (reuse `site_crawler.py` — single-page mode)" (§5.2 step 1) | `site_crawler.py` exposes `crawl_site(url, max_pages=50)`. There is no "single-page mode" entry point. You can pass `max_pages=1` but the function still launches Playwright, navigates, follows internal links into a queue (which is then ignored once the cap hits), and the BFS loop only checks `len(pages) < max_pages` after popping. For competitor homepage scraping at scale (≥10 candidates × Playwright launch each) this is heavyweight — likely want a thin httpx+BS4 helper instead. | `site_crawler.py:76-126`; the only "single page" reference is a docstring on the internal `_extract_page` helper |
| F3 | GBP nearby search "reuse existing `gbp_scraper.py`. For local-service clients, query Google Business Profile for businesses in the client's geo with matching industry/category" (§5.1 source 1) | `scrape_gbp(business_name, location)` takes a **known business name** and looks up its profile. It does *not* support category-based discovery ("find dentists near Stockholm"). The function returns a single `GoogleBusinessProfile` or `None`; there is no list-of-results path. | `gbp_scraper.py:22-61` — signature is `(business_name: str, location: str = "")`, returns `GoogleBusinessProfile \| None`. Internally it does one Google Maps search and parses the title tag. This **resolves §8 question 1: NO**. |
| F4 | Implicit: §6 schema diff against "today's" model. The doc shows `top_keywords: list[str] = []` removed without comment. | The current `CompetitorProfile` has `top_keywords: list[str] = []` (line 23 of `competitor.py`). The doc's "extended" schema silently drops it in favor of `inferred_keyword_themes`. §7 says "additive, never removed" — this is a removal. | `src/models/competitor.py:19-25` |
| F5 | Implicit: TransparencyAd schema. Today's model has `date_range: ""` and `geo_targeting: ""` semantics in the **scraper** but the **model** has neither — instead `first_seen`, `last_seen`, `regions`. The scraper at `transparency_scraper.py:122-128` instantiates `TransparencyAd(advertiser_name="", ad_text=..., ad_format=..., date_range=..., geo_targeting=...)` which would currently **fail Pydantic validation** because `date_range` and `geo_targeting` are not fields on the model. | `competitor.py:10-16` defines fields `advertiser_name, ad_text, ad_format, first_seen, last_seen, regions`; `transparency_scraper.py:122-128` passes `date_range=, geo_targeting=` kwargs that don't exist on the model. **The scraper has never run successfully** — Pydantic v2 with default config rejects unknown fields. Doc says "verify still works"; reality is "currently broken". |

## Internal contradictions

1. **Binary vs uncertain classification.** §6 declares `CompetitorProfile.classification: Literal["direct", "indirect"]` (required, two values). §8 question 6 then proposes `direct_uncertain` / `indirect_uncertain`. Either the Literal is `Literal["direct", "indirect", "direct_uncertain", "indirect_uncertain"]` and §8 q6 is already answered yes, or §8 q6 is genuinely open and §6 should not have committed. Pick one before P3 starts.

2. **Backwards compatibility vs schema removal.** §7 says "Continue producing `competitors.json` at the existing path with backwards-compatible fields (additive, never removed)". §6 silently removes `top_keywords` from `CompetitorProfile`. Either keep `top_keywords` (deprecated, populated from `inferred_keyword_themes` for one release), or amend §7 to say "we will rewrite the schema; existing competitors.json files become invalid".

3. **Discovery defaults.** §4 says default is `--max-candidates 15`. §10 success criterion says "≥10 candidates". §9 P2 acceptance says "≥10 candidates". The default ceiling of 15 leaves only 5 slots of headroom against the success criterion — fine, but worth noting that any candidate filtered out by classification (rejection rate not specified) directly threatens the success criterion. Suggest raising default to 20 or making the criterion ≥10 *confirmed*, not ≥10 candidates.

4. **§4 outputs vs §9 P5.** §4 lists `competitor_report.md` as an output of every `run`. §9 P5 ("Report & integration") is the last phase. Phases P1–P4 therefore do *not* produce the report. The §4 outputs section needs a "(produced by P5)" annotation per file or §9 needs a clearer "what runs after each phase" statement.

5. **§8 q4 cache location.** "Suggest `~/.sem-master/cache/competitor_lp/` with content-addressed filenames." The rest of the project uses `~/.sem-master/` for global config/credentials/templates and `clients/{name}/` for per-client artifacts. Putting *competitor LP cache* in the global dir means caches leak across clients (probably fine, that's the goal — many clients may share LP fetches) but it also means `sem accounts remove` does not clean up the cache. Decide whether per-client or global, document it.

## Gaps

The following must be in the doc before a junior dev can implement v1 without ambiguity:

1. **Error handling.** What does `sem competitors ads <client>` do when:
   - Transparency Center returns zero results (legitimate — competitor is not advertising)?
   - Transparency Center returns CAPTCHA / blocks the bot?
   - Playwright crashes on launch?
   - LP fetch returns 404 / 403 / 5xx?
   - LLM call returns malformed JSON?
   - LLM call exceeds the 5 SEK cost cap mid-run?
   §11 says "no silent fallback to dry-run" — good — but does it `raise typer.Exit(1)`, write a partial result, mark the stage `failed`, or what? Today's `competitors_commands.py:151-154` marks the stage failed and re-raises. The new flow needs explicit per-step error policy.

2. **Idempotency / re-run behavior.** If I run `sem competitors discover` twice, does it:
   - Re-discover from scratch (LLM cost re-incurred)?
   - Skip and reuse `candidates.json` if present?
   - Merge new candidates into existing `competitors.json`, preserving manual review decisions?
   This is a real concern because §5.2 stores the LLM rationale and the user can manually override in `sem competitors review` — those overrides must survive a re-run.

3. **Privacy / compliance.** Transparency Center ads are public, but storing competitor landing-page content (full body text, headers) is a content-cache that may contain GDPR-relevant data (e.g., a competitor LP listing a doctor's name). Decide:
   - How long is `~/.sem-master/cache/competitor_lp/` retained? (§5.4 says 24h TTL — but is that purged automatically?)
   - Is the raw HTML snapshot from §5.3 ("Persist raw HTML snapshot per scrape for debugging") gitignored *and* in `.sem-master`, or in `clients/{name}/`?
   - When the user runs `sem accounts remove`, are competitor caches purged?

4. **Test strategy.** The project has 26 test files in `tests/`. The doc mentions tests zero times. At minimum specify:
   - Unit tests for `CompetitorCandidate`/extended `CompetitorProfile` Pydantic validation (mirror `tests/test_models.py`)
   - A dry-run integration test (`tests/test_competitor_pipeline_dry_run.py`) using fixture HTML for Transparency Center
   - That existing `tests/test_pipeline_dry_run.py` continues to pass
   - That `tests/test_models.py` is updated for any model changes (failed claim F4 means it currently would not catch the schema drift)

5. **Migration plan for existing clients.** Both existing clients (`benalexis`, `novapsykiatri`) currently have **no `competitors/` directory** at all (verified via Glob — only `seo/` artifacts exist). So strictly speaking there is nothing to migrate. The doc should state this explicitly: "No live deployments exist; existing clients can be re-run from intake without data loss." That kills the migration concern in one sentence.

6. **Anthropic SDK adoption.** Failed claim F1 is the biggest gap. If §5.2/§5.4 require LLM calls, **someone has to add the `anthropic` package to `pyproject.toml`, write the client wrapper, set up cost accounting, and document the credential flow.** The doc treats this as already done. Add a P0 / P1.5 task: "Build `src/apis/anthropic_client.py` (wrapper + cost tracking + retry) before any LLM-dependent phase starts."

7. **Cost-tracking implementation.** §5.4 says "warn if total estimated LLM cost exceeds 5 SEK". Where does the running cost counter live? Per-stage? Per-client? In-memory only or persisted in `clients/{name}/competitors/cost_log.json`? Decide.

8. **Concurrency.** §5.3 specifies "max 1 request per 2 seconds" for Transparency Center. Are LP fetches and LLM calls also serialized, or run concurrently? With ≥5 confirmed competitors × ≥30 ads × LP fetch + LLM call per unique ad, serial execution at 1 req/2s blows the 5-minute budget on its own (see Sanity checks below).

9. **`competitor_report.md` schema.** §5.5 describes content but no template / section ordering / Swedish-vs-English language choice. Project convention (per `CLAUDE.md`) is "All ad copy and client-facing output in Swedish" — does that apply to the competitor report too? If yes, prompts in §5.4 need a Swedish-output instruction.

## Vagueness flags

- **§5.3 "First task: verify the existing scraper still works".** Acceptance criteria are missing. What does "still works" mean — pulls ≥1 ad? Pulls all 5 paginated pages? Maps every TransparencyAd field correctly? A junior dev would write a smoke test that returns `len(ads) > 0` and call it done. Specify: "Run `scrape_transparency('Klarna')` against the live site; assert ≥10 ads returned with non-empty `ad_text`, non-null `landing_page_url`, and `advertiser_id` populated. If any are null, fix the selectors before declaring P1 done." Also note that **the scraper is currently broken** (failed claim F5) — `date_range` and `geo_targeting` kwargs do not exist on the model. P1 must fix this before testing selectors.

- **§5.1 "Outbound link mining".** "Scan client's own site for external links to industry peers, association directories, 'see also' mentions." How is "industry peer" detected from a list of outbound links? The site likely has hundreds of outbound links (CDN, social, analytics, news mentions, suppliers). Without a filter rule, this source is noise. Specify: domain blacklist (google, facebook, instagram, linkedin, ..., social/CDN/analytics), then LLM prompt to filter the rest. Or drop it — it's listed as "low yield".

- **§5.4 "Repeated noun phrases (via `simplemma` for Swedish lemmatization)".** simplemma is a lemmatizer, not a noun-phrase extractor. It can lemmatize words but can't identify NPs. Either spell out the implementation ("tokenize on whitespace, lemmatize each token, count repeated tokens excluding stopwords from `data/swedish/stopwords.json`") or import a real NP-chunker. As written, this step would not pass code review.

- **§7 "`inferred_keyword_themes` from competitors becomes seed input for the client's own keyword research".** How? `sem keywords run` reads from where today, and what new field/file does it now also read? Specify the integration point in code, not just intent.

- **§9 P2 acceptance "≥10 candidates for any onboarded client without intake_competitors being filled".** "Any onboarded client" is too strong — for an extremely niche B2B client (e.g., subsea cable maintenance for windfarms) the GBP nearby search will return zero and LLM ideation may struggle. Soften to: "for the test fixtures `benalexis` and `novapsykiatri`, ≥10 candidates each".

## Sanity checks

### LLM cost estimate (§5.4 cap of 5 SEK per client run)

Assumptions from §10 and §5.3/§5.4:
- 10 confirmed competitors (success criterion lower bound is 5; using upper bound for cost)
- 30 ads per competitor (default cap is 50; using a realistic average)
- 1 LLM call per *unique* (ad_text, landing_page_url) pair
- LP cache deduplication factor: assume ~60% of ads on a competitor share LPs (typical for funnel landing pages) → 0.4 unique pairs

Unique LLM calls: `10 × 30 × 0.4 = 120 calls`

Plus classification calls: 1 per candidate, default `--max-candidates 15` → 15 calls
Plus LLM ideation in §5.1 source 4: ~1 call → 1 call
Total: **~136 LLM calls**.

At Claude Haiku 4.5 pricing (USD 1 / MTok input, USD 5 / MTok output as of model release):
- Per call: ~2,000 input tokens (ad copy + LP extract + client context) + ~500 output tokens
- Per call cost: `(2000/1e6 × 1) + (500/1e6 × 5)` = 0.002 + 0.0025 = **$0.0045**
- Total: `136 × $0.0045` = **$0.61 ≈ 6.40 SEK** at 10.5 SEK/USD

**Verdict: 5 SEK cap is ~25% too low.** Either:
- (a) Raise the cap to 10 SEK (still cheap relative to manual analyst work).
- (b) Tighten dedup (combine multiple ads with the same LP into a single LLM call asking for keywords across the ad set, not per-ad — saves ~50% of calls).
- (c) Lower default `--max-ads-per-competitor` from 50 to 20.

Also: if the user picks the "upgrade to Sonnet via flag" option in §5.4, costs go ~5× higher — to ~30 SEK. The doc should note: "Sonnet flag implies cost cap is automatically scaled".

### Run-time estimate (§10 "< 5 minutes per client")

| Step | Time |
|---|---|
| Playwright launch (cold) | 3–5s |
| Discovery: GBP query (per candidate) × 15 candidates | ~30s if serial |
| Discovery: LLM ideation call | ~3s |
| Classification: LP fetch × 15 + LLM call × 15 | LP fetch with httpx 1–3s each = 30s; LLM ~3s × 15 = 45s = **~75s** |
| Transparency Center: 10 competitors × pagination (rate-limited 1 req / 2s, ad list scroll typically 5–10 fetches per advertiser) | 10 × 8 × 2s = **160s** |
| LP fetches for keyword inference: 120 unique LPs at 1–3s each (httpx, parallel) | 30–60s |
| LLM keyword inference: 120 calls × 3s each, sequential | **360s = 6 minutes** |
| PDF generation | 5s |
| **Total (sequential)** | **~11 minutes** |

**Verdict: 5 minutes is achievable only with concurrent LLM calls.** Anthropic SDK supports async, and typical concurrency of 5–10 in-flight requests is fine. With concurrency 8: LLM phase becomes ~45s, total drops to ~5 min. This is fine, but the doc must commit to "LLM calls run concurrently with `asyncio.gather` at concurrency N" — see Gap 8 above.

### Scope realism

- **"≥10 candidates":** GBP alone won't deliver 10 for niche industries (verified F3 — GBP scraper can't even do nearby search yet). LLM ideation will be the workhorse. Realistic only if the LLM ideation prompt is tuned (§8 q5 acknowledges this).
- **"≥3 indirect":** Indirect competitors are by definition *not* in the same Google Business category as the client. GBP will never find them. Site-link mining is "low yield" by §5.1's own admission. So **all 3 indirect must come from LLM ideation**. Achievable but contingent on prompt quality. Not blocking, but flag for P2.
- **Time + cost combined:** if you want concurrency for time but pay full LLM cost, you need both the cost cap raise *and* the concurrency commitment. Don't pick one.

## Resolved open questions

| §8 # | Question | Answer (from code inspection) |
|---|---|---|
| 1 | GBP scraper coverage: nearby search by category? | **No.** `gbp_scraper.py:22` signature is `scrape_gbp(business_name: str, location: str = "")` — it takes a known business name. To support "find businesses near X with category Y" you must write a new function (likely `find_local_businesses(category: str, location: str, geo_radius_km: int)`) that hits Google Maps search and parses multiple result cards, not the current single-profile path. **Estimate: 1–2 days to build + test.** Add this as a new task in P2. |
| 3 | LLM provider: piggyback on existing ANTHROPIC_API_KEY? | **Partially.** The env var is loaded into config (`config.py:33`) and listed in `.env.example`. But there is **no Anthropic SDK in the codebase** — `pyproject.toml` does not include `anthropic`, no file imports it, and `ad_copy_generator.py` is rule-based. So you do "piggyback on the env-var convention" but you must still: (a) add `anthropic` to `pyproject.toml`, (b) build `src/apis/anthropic_client.py` with retry + cost tracking, (c) wire it into `config.py`. Add as new P0/P1.5 task. |
| 4 | Cache layer location? | **Recommend `clients/{name}/cache/competitor_lp/` (per-client), not `~/.sem-master/cache/competitor_lp/` (global).** Reasons: (1) `sem accounts remove` already cleans the client dir; (2) competitor LPs are tightly coupled to the client's competitor set; (3) cross-client cache sharing has minimal hit rate in practice (each client's competitors are different). Use SHA-256 of URL as filename. |
| 6 | Allow `direct_uncertain` / `indirect_uncertain`? | **Yes, but only if you accept the §6 contradiction.** Suggest `Literal["direct", "indirect", "uncertain"]` (single uncertain bucket — you don't need two flavors of "I'm not sure", you just need to flag it for human review). Surface in `sem competitors review`. |

## Recommended changes

In priority order — apply before architecture work begins:

### P0 (blocking — fix before any code is written)

1. **Fix §8 question 3 / Anthropic claim.** Rewrite as: "ANTHROPIC_API_KEY is conventionally referenced in `.env.example` for future ad-copy LLM use, but the codebase has no Anthropic SDK integration today. P1 must include adding `anthropic` to `pyproject.toml` and building `src/apis/anthropic_client.py` (async client wrapper + per-call cost tracking + 429 retry). Estimate: 0.5 day."

2. **Fix §5.1 source 1 / GBP nearby search claim.** Rewrite as: "GBP nearby search is **not** supported by the current `gbp_scraper.py` (which is profile-by-name only). P2 must include a new function `find_local_businesses(category, location)` in `src/scrapers/gbp_scraper.py` that scrapes Google Maps category search results. Estimate: 1–2 days. Acceptance: returns ≥5 results for `find_local_businesses('tandläkare', 'Stockholm')`."

3. **Fix §5.3 scraper-broken claim.** Add to "verify the existing scraper still works": "Note: the scraper currently constructs `TransparencyAd(advertiser_name='', date_range=..., geo_targeting=...)` (`transparency_scraper.py:122-128`) but those kwargs do not exist on the model (`competitor.py:10-16`). The scraper has never run successfully. P1 step 1: fix the scraper-model mismatch by extending the model per §6 *and* updating the scraper to populate the new fields. Step 2 (verification) only happens after step 1."

4. **Fix §5.2 `site_crawler.py` claim.** Replace "reuse `site_crawler.py` — single-page mode" with: "For competitor homepage scraping, write a thin httpx+BS4 helper `fetch_homepage_summary(domain) -> dict` in `src/scrapers/competitor_homepage.py`. Do NOT reuse `crawl_site()` — it launches Playwright and runs BFS, both of which are overkill for single-page extraction at the ≥10-candidate scale."

5. **Resolve §6 / §8 q6 contradiction.** Pick: `Literal["direct", "indirect", "uncertain"]` and remove §8 q6. Update §10 success criterion accordingly (likely "≥3 classified as indirect or uncertain — surfaced for human confirmation").

### P1 (should-fix — catch before P1 implementation)

6. **Adjust LLM cost cap.** Change "5 SEK" to "10 SEK" with explanation in §5.4: "Estimate based on 10 competitors × 30 ads × 0.4 LP-dedup factor + 15 classification calls + 1 ideation call ≈ 136 Haiku calls @ ~$0.0045 = ~$0.61 ≈ 6.40 SEK; cap at 10 SEK gives margin." Also add: "Sonnet flag automatically scales the cap by 5×."

7. **Add concurrency commitment.** §5.4 add: "LLM keyword-inference calls run concurrently with `asyncio.Semaphore(N=8)` to keep total run-time within the §10 budget. LP fetches use the same pattern."

8. **Add error-handling section (new §5.6).** Spec one paragraph per failure mode: zero ads, CAPTCHA, Playwright crash, LP 4xx/5xx, malformed LLM JSON, cost-cap exceeded mid-run. Default policy: log warning, persist what we have, mark stage `completed_with_warnings` (new state) or `failed`, never silent fallback to synthetic data (per §11).

9. **Add idempotency rules (new §5.7).** "Re-running `sem competitors discover` reuses `candidates.json` unless `--force` is passed. `sem competitors review` decisions are stored in `competitors.json` under a `_user_overrides` key that survives subsequent re-discovery. `--force-rediscover` is the explicit re-classify-everything escape hatch."

10. **Add test strategy (new §5.8).** Mirror `tests/test_pipeline_dry_run.py`: `tests/test_competitor_pipeline_dry_run.py` with fixture HTML for Transparency Center + monkeypatched LLM calls. Update `tests/test_models.py` for the new fields. Required pre-merge: `python -m pytest tests/ -v` passes.

11. **Add migration / backwards-compat statement.** "Both existing clients (`benalexis`, `novapsykiatri`) have no `competitors/` directory today (only `seo/`). Migration is N/A — re-run from intake when the new flow ships."

### P2 (nice-to-have — polish)

12. **Tighten outbound-link mining (§5.1 source 3).** Spec the domain blacklist + LLM filter, or drop the source.

13. **Tighten "repeated noun phrases" (§5.4).** Replace with: "tokenize on whitespace + punctuation, lemmatize via `simplemma.lemmatize(..., lang='sv')`, exclude tokens in `data/swedish/stopwords.json`, count occurrences, return top 20." simplemma is not a NP chunker — be explicit.

14. **Tighten §5.3 verification acceptance.** "Run `scrape_transparency('Klarna')`; assert ≥10 ads, every ad has non-empty `ad_text` and non-null `landing_page_url`. If any null, the selectors are broken — fix before P1 done."

15. **Resolve §8 q4 cache location.** Use `clients/{name}/cache/competitor_lp/` (per-client) with SHA-256-of-URL filenames, 24h TTL enforced on read.

16. **Annotate §4 outputs.** Mark each output file with `(produced by P1 / P2 / P3 / P4 / P5)` so phase boundaries are visible.

17. **Add Swedish-output language requirement to §5.4 prompt and §5.5 report.** Per `CLAUDE.md` convention, all client-facing output is Swedish.

### P3 (housekeeping)

18. **§7 schema-removal note.** Either keep `top_keywords` deprecated for one release, or amend §7 to admit the schema rewrite (drop "additive, never removed").

19. **§4 default candidate count.** Raise `--max-candidates` default from 15 to 20 to leave headroom against the §10 ≥10 success criterion after rejection filter.

---

**Bottom line:** the doc has the right shape and the right scope. The five P0 items above are blocking — they invalidate plan-level claims that a reader would otherwise rely on. Fix those, address the cost-cap and concurrency commitments in P1, and this is implementable. As-is, a junior dev starting on P1 would hit the broken-scraper trap (F5) within the first hour and the missing-Anthropic-SDK trap (F1) within the first day.
