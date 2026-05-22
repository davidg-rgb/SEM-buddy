# Next-Session Handoff — v0.3.4 finish line

> **Created:** 2026-05-20 (end of v0.3.4 implementation session)
> **Supersedes:** the v0.3.3 handoff (now archived at `.planning/v0.3.4-IN-PROGRESS-HANDOFF.md` — it's the brief I worked from this session and all 4 contracts inside it are now green).
>
> **Tomorrow's plan, in order:**
> 1. Verify (read this doc, run the smoke commands in §6, see all green).
> 2. Fix the 6 open issues in §3 (~1–2 hr of pattern + cleaner work).
> 3. Re-run the audit + spell-check + tests; spawn a fresh reviewer pass on the v0.3.4 sample to confirm the long-name path now reads clean.
> 4. Write the `v0.3.4-NO-SKU-PER-VARIANT-URLS.md` doc.
> 5. Commit the v0.3.x bundle (staged but uncommitted at end of this session).
> 6. (Optional) push a smoke-test campaign to `469-180-7001` via `sem case push etraveli --limit 10 --auto-suffix --skip-lead-forms --yes`.

---

## 1. What got done this session

The whole v0.3.4 mission set landed:

| Mission | Status | Audit result on full etraveli catalog |
|---|---|---|
| **3** — Per-variant `text=N` URLs (variant slot → N, no rotation across ad groups) | DONE | 0 ad groups with duplicate text=N across 963 ad groups |
| **4a** — No SKU/IATA in customer copy (operator's hard rule mid-session) | DONE | 0 SKU leaks across 4,580 RSAs |
| **4b** — `from_price` surfaced in ≥1 variant per priced destination | DONE | 0 priced destinations missing the price token |
| **2** — Mandatory `Save up to {pct}% to {name}` headline for `discount_pct >= 0.15` | DONE | 0 discounted destinations missing the canonical headline |
| **1a** — Automated spell-check pass | DONE | 0 flagged tokens across 4,580 RSAs (whitelist covers all real proper-noun edge cases) |
| **1b** — Stratified-sample reviewer agent QA | PARTIAL | Found 6 real issues — see §3 |

**Numbers at handoff:**
- 963 destinations × 4–5 variants = **4,580 RSAs**
- All 4 contract audits pass: `python -m scripts.audit_v034` → 0 failures
- Spell-check pass: `python -m scripts.spell_check_rsas` → 0 flagged tokens
- 40/40 variant tests pass, 193/193 catalog tests pass
- Pipeline runs in ~13s end-to-end

---

## 2. What changed (uncommitted state at handoff)

### Modified

- `src/generators/ad_copy_generator.py`
  - Killed `IATA_HOUSEHOLD_CODES` (now an empty frozenset shim) + `_should_use_iata_in_customer_copy` (returns False unconditionally)
  - Added `_resolve_customer_display_name(product, max_chars)` — paren-strip → comma-segment → particle-strip → full name → never SKU
  - Added `_strip_parens` and `_shrink_name_with_particles` helpers
  - Rewrote `_fill_pattern` to empty `{sku}` substitutions in all customer copy (even `long_name_fallback: true` patterns)
  - Added price-token preservation in `_fit_to_limit` (`_PRICE_TOKEN_RE`) — refuses truncation that drops `$<digits>`
  - Added meaning-bearing-tail refusal in `_fit_to_limit` — refuses truncation that would drop fees/today/now/flights/etc.
  - Added Romance-language particles (`de`, `do`, `da`, `du`, `del`, `della`, `di`, `la`, `le`, `los`, `las`, `el`) to `_TRAILING_INCOMPLETE_FRAGMENTS_EN`
  - Rewrote `generate_headlines_for_variant`'s discount-mention block — mandatory `Save up to {pct}% to {name}` injection with fit-aware fallback chain (6 candidate shapes, picks first that fits 30 chars), never substitutes SKU
  - Refactored `generate_rsa_variants` — now accepts `final_url_template` + `text_n_range`, renders per-variant URLs (variant slot 0 → text=`low_n`, slot 1 → `low_n+1`, …, wrap on overflow)
  - Added `from_price` guarantee enforcer — after generating all variants, if product has known from_price but no variant surfaces it, force-inject operator's example description ("Get a great deal on flights to {name} with prices from $X") + a headline into the price_led variant

- `src/generators/campaign_builder.py`
  - Dropped the per-ad-group `NCycler` in `_structure_by_sku` (each variant now owns its `text=N`)
  - `_build_ad_group_for_product` passes `primary_url_template` + `text_n_range` to `generate_rsa_variants` instead of a pre-rendered URL
  - Ad-group fallback URL (used by keyword final_url + Path1/Path2 derivation) uses `text=N_low` (= text=1), aligning with variant 1

- `data/en/ad_copy_patterns.json` → **v4** pattern pack
  - Added `Save up to {discount_pct}% to {name}` as the FIRST discount_led headline pattern (with `mandatory: true` flag)
  - Added operator's example description `Get a great deal on flights to {name} with prices from ${from_price}` as the FIRST price_led description pattern (with `mandatory_when_priced: true` flag)
  - Added Save-up-to + from_price description for discount_led (`Save up to {discount_pct}% on flights to {name} from ${from_price}. Compare 800+ airlines.`)
  - Replaced ALL `{sku}` substitutions in `long_name_fallback_patterns` with `{name}` (resolver shortens automatically)
  - Updated top-level `notes` to v4 contract

- `clients/etraveli/catalog/accepted_proposal.json`
  - WMI: `Nowy Dwór Mazow`iecki` → `Nowy Dwór Mazowiecki` (removed errant apostrophe)
  - VAA: `Martha's Vinyard` → `Martha's Vineyard` (spelling fix)

- `tests/test_rsa_variants.py`
  - Added 8 new acceptance tests: `test_variants_have_distinct_text_n_urls`, `test_variants_text_n_starts_at_one_and_increments`, `test_keyword_url_inherits_first_variant_text`, `test_every_discounted_destination_surfaces_save_up_to_pct_to_name`, `test_no_sku_token_in_headlines_or_descriptions`, `test_every_priced_destination_surfaces_from_price`, `test_resolver_never_returns_sku`, `test_long_name_fallback_uses_name_not_sku`

### Added

- `scripts/audit_v034.py` — gates Missions 2/3/4 against the live exported CSV. Exit code 0/1.
- `scripts/spell_check_rsas.py` — pyspellchecker against every RSA token. Whitelisted: destination tokens, OTA brand vocab, real proper nouns (Martha's, Mazowiecki, Nuku'alofa, Heathrow).
- `scripts/stratified_rsa_sample.py` — picks 32 ad groups across 5 strata (long-name / short-name / high-disc / low-disc / no-price) and writes a markdown sample for reviewer consumption.
- `clients/etraveli/exports/catalog/SPELLCHECK-v034.md` — fresh spell-check report (0 flags).
- `clients/etraveli/exports/catalog/QA-SAMPLE-v034.md` — stratified reviewer sample.

### New dependency

- `pyspellchecker` (installed via pip; should be added to `pyproject.toml` dev deps before commit).

---

## 3. Open issues — fix these tomorrow

The reviewer agent (general-purpose, given the full QA sample) found these. Listed in priority order with locations + fix sketches.

### CRITICAL (ship-blockers)

#### Issue 3.1 — Orphan first-name truncations on long-name destinations

**What:** Patterns like `"{name} flights -{pct}%"`, `"Book before {name}"`, `"Stop overpaying for {name}"`, `"Lock today's {name}"`, `"Price-match {name}"`, `"Compare {name}"`, `"$X flights to {name}"` get truncated to the FIRST word of the destination, producing "Fernando", "San Carlos", "Bandar Seri", "Grand Cayman". Reads as a person's name in some patterns (e.g. "Book before Fernando").

**Reviewer quotes:**
- `Lock today's Fernando` in **`Fernando De Noronha (FEN)`** variant text=4
- `Stop overpaying Fernando` / `Don't pay full Fernando` / `Book before Fernando` (FEN variant 5)
- `Save up to 46% to Fernando` (FEN variant 2 — this satisfies Mission 2 but reads wrong)
- `Today's lowest Fernando De Noronha fare` (FEN variant 4 description — name placement parses as a person's name)
- Same pathology: San Andres, Bandar Seri, Grand Cayman, San Carlos, Mineralnye

**Why it's broken:** `_resolve_customer_display_name` returns the full name "Fernando De Noronha" when budget allows it; for patterns like `"Save up to {pct}% to {name}"` with budget 30 - len("Save up to 99% to ") = 12, it shortens to "Fernando" (first word fitting 12 chars). The shortening is correct mathematically but produces an orphan first name.

**Fix sketch:**
1. In `_resolve_customer_display_name`, add a step between "full name" and "particle-strip": prefer dropping LAST-word particles ("De", "De La", etc.) before falling back to first-word truncation. The current `_shrink_name_with_particles` only drops particle-pairs from the middle; we need to also try `name.rsplit(" ", 1)[0]` if the last word is a known particle/suffix.
2. For names where the only way to fit the budget is to truncate to a single first name (e.g., "Fernando" from "Fernando De Noronha"), REJECT the shortening — return the FULL name unchanged. The pattern caller's `_fit_to_limit` will then reject the whole pattern (better to skip than ship an orphan).
3. Tightening test: add `test_no_orphan_first_name_in_long_destinations` — for every product with name length ≥ 18, no headline may be a strict prefix of the name that loses ≥2 trailing words.

### Issue 3.2 — Petropavlovsk-**Kamchats** is a transcription typo in the source catalog

**What:** Real name is "Petropavlovsk-Kamchatsky" (Russian: Петропавловск-Камчатский). The source XLSX has "Petropavlovsk-Kamchats" — missing the "-ky" suffix. We ship this misspelled name across all 5 PKC variants.

**Why it slipped past spell-check:** The whitelist adds destination-list tokens to the dictionary, so "Kamchats" is technically whitelisted via the source data.

**Fix sketch:**
- Add a cleaner diff in `clients/etraveli/catalog/accepted_proposal.json`:
  ```json
  {"row_key": "PKC", "field": "name", "before": "Petropavlovsk-Kamchats, Russian Federation", "after": "Petropavlovsk-Kamchatsky", "reason": "Fix source transcription error: real name is Petropavlovsk-Kamchatsky; source XLSX dropped the '-ky' suffix and the trailing ', Russian Federation' adds noise."}
  ```
- Verify spell-check still passes after the rename (Kamchatsky won't be in the dictionary either — add to OTA_WHITELIST).

### Issue 3.3 — "Cheap Flights to {name}" banned phrase slipped in via title-cased keyword path

**What:** `Cheap Flights to Karpathos` (AOK variant 2 line 2204) and `Cheap Flights to Chania` (CHQ variant 2 line 2720). The sem-ad-copy skill explicitly bans `Cheap {name} flights`.

**Why it slipped:** The keyword-fallback path in `generate_headlines_for_variant` (around line 1137-1140 of ad_copy_generator.py) calls `_title_case_keyword(kw)` on raw keywords. The keyword templates in case.yaml include `cheap flights to {name}`, which title-cases to "Cheap Flights To Karpathos" — close enough to the banned phrase to count.

**Fix sketch:**
- Add a banned-phrase filter to the keyword-fallback path. After title-casing, if the result starts with `Cheap ` AND a destination token follows, skip.
- Or, drop the `cheap flights to {name}` template from case.yaml — keep the keyword in the keyword pool (it's a real search term) but don't elevate it to a headline.
- Add a test: no headline in any variant starts with "Cheap ".

### MEDIUM (read awkwardly but won't visibly fail)

#### Issue 3.4 — Triple-Trustpilot collision in social_proof (text=3)

**What:** Three headlines say essentially the same thing:
- `4.5★ on Trustpilot`
- `Trustpilot rated 4.5★`
- `4.5★ Trustpilot reviews`

All three appear in text=3 of nearly every ad group. Google's RSA optimizer dampens ad strength on semantic-similarity collisions.

**Fix sketch:** In `data/en/ad_copy_patterns.json`, social_proof variant: pick ONE of these three, drop the other two from `headline_patterns` AND `tail_headlines`. Recommend keeping `4.5★ on Trustpilot` (shortest, cleanest visual).

#### Issue 3.5 — PKC pinned D1 lost from_price

**What:** PKC variant 1 pinned D1 is `Save 22% on Petropavlovsk-Kamchats, Russian Federation` — no from_price, no airline-compare, no cancellation. Other long-name destinations have richer pinned D1s.

**Why:** The long_name_fallback description pattern `"Save {discount_pct}% on {name} flights. Real prices, 1.5M+ travelers/year"` fired but truncated to ditch the trailing claim. The previous-style pin (price-bearing) got rejected because the long name overflowed.

**Fix sketch:** After Issue 3.1 lands, PKC's resolver might surface a shorter form ("Petropavlovsk-Kamchatsky" without ", Russian Federation"), which fits the richer pin pattern. Verify post-fix by re-running and checking PKC D1.

#### Issue 3.6 — Fares-update triplet in urgency (text=4)

**What:** `Fares update every hour`, `Fares updated hourly`, `{name} fares update hourly` all appear in text=4. Same semantic-similarity issue as 3.4.

**Fix sketch:** Drop two of the three from urgency's pattern lists; keep `{name} fares update hourly` (it's destination-anchored).

---

## 4. Operator confirmation needed (NOT blocking the 6 fixes above)

**"IATA-accredited agent" / "IATA-accredited since 2007"** — appears in 100% of text=3 variants across all 963 ad groups. Whether this claim is defensible depends on Flightnetwork's actual IATA accreditation status per market. If it's NOT defensible (e.g., the brand has a TIDS code but isn't a full IATA ticketing agent in all markets we're targeting), this is an FTC/ASA risk across the entire catalog.

Action: confirm with the FN account team before publishing for review.

---

## 5. Definition of done for tomorrow

1. All 6 issues in §3 closed (or explicitly deferred with rationale).
2. `python -m scripts.audit_v034` → 0 failures.
3. `python -m scripts.spell_check_rsas` → 0 flagged tokens.
4. `python -m pytest tests/test_rsa_variants.py tests/test_catalog_campaign_builder.py -q` → all green.
5. `python -m scripts.stratified_rsa_sample` regenerated; a fresh reviewer agent pass on the new sample finds 0 critical issues.
6. `.planning/v0.3.4-NO-SKU-PER-VARIANT-URLS.md` written, mirroring the style of `v0.3.3-REVIEW-DRIVEN-FIXES.md`.
7. Commit the bundle: `feat: v0.3.4 no-SKU customer copy + per-variant text=N + mandatory discount headline + from_price guarantee`.
8. Operator-confirmed go/no-go on the IATA-accreditation claim (§4).
9. (Optional but recommended) `sem case push etraveli --limit 10 --auto-suffix --skip-lead-forms --yes` smoke-test push to live test account.

---

## 6. Smoke commands to re-enter the project tomorrow

```bash
# 1. Read this doc + the v0.3.3 archived handoff for context
.planning/NEXT-SESSION-HANDOFF.md
.planning/v0.3.4-IN-PROGRESS-HANDOFF.md  # the brief I worked from this session

# 2. Verify the state is the same (all should print 0 failures + 0 flags)
SEM_DISABLE_LLM=1 python -c "import os; os.environ['SEM_DISABLE_LLM']='1'; \
  from src.cli.app import create_app; import sys; \
  sys.argv = ['sem', 'case', 'run', 'etraveli']; create_app()()"
python -m scripts.audit_v034
python -m scripts.spell_check_rsas
python -m pytest tests/test_rsa_variants.py -q

# 3. Re-generate the reviewer sample if any patterns change
python -m scripts.stratified_rsa_sample
# → clients/etraveli/exports/catalog/QA-SAMPLE-v034.md

# 4. Inspect a known problem ad group after fixes land
python -c "
import csv, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('clients/etraveli/exports/catalog/04_responsive_search_ads.csv', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        if r['Ad Group'].endswith('(FEN)') and 'text=2' in r['Final URL']:
            for i in range(1, 16):
                h = r.get(f'Headline {i}', '')
                if h: print(f'H{i}: {h}')
            break
"
```

---

## 7. Files / locations cheat sheet

| Topic | Path |
|---|---|
| Pattern pack (v4) | `data/en/ad_copy_patterns.json` |
| Customer name resolver | `src/generators/ad_copy_generator.py::_resolve_customer_display_name` |
| Mandatory save-up-to injection | `src/generators/ad_copy_generator.py::generate_headlines_for_variant` (search for "Mandatory 'Save up to X% to NAME'") |
| from_price guarantee | `src/generators/ad_copy_generator.py::generate_rsa_variants` (search for "From-price guarantee") |
| Per-variant URL rendering | `src/generators/ad_copy_generator.py::generate_rsa_variants::_variant_final_url` |
| Truncation guards | `src/generators/ad_copy_generator.py::_fit_to_limit` (search for "Price-token preservation") |
| Catalog name overrides | `clients/etraveli/catalog/accepted_proposal.json` |
| Destination source-of-truth | `clients/etraveli/Client Case Info/Destination list (Template) - Destinations.csv` |
| Reviewer sample (regenerate after fixes) | `clients/etraveli/exports/catalog/QA-SAMPLE-v034.md` |
| Spell-check report | `clients/etraveli/exports/catalog/SPELLCHECK-v034.md` |
| v0.3.3 archived handoff (today's brief) | `.planning/v0.3.4-IN-PROGRESS-HANDOFF.md` |

---

## 8. Memory anchors to update tomorrow

After tomorrow's session closes, write `v034-no-sku-per-variant-urls.md` memory entry. Reference the v0.3.3 entry for style.

---

## 9. Definition of "good enough to publish for review"

After fixing the 6 issues:
- The v0.3.4 pattern pack ships with truthful, FTC-safe copy
- Long-name destinations read as cleanly as short-name ones
- Operator can pull up any ad group in any bucket and see a coherent, lever-anchored set of 4–5 RSAs
- The audit script + the spell-check + the variant tests all hit zero
- A fresh reviewer pass on a new stratified sample finds zero critical issues

Then it's ready to publish for review and (separately) a smoke-test push to `469-180-7001`.

---

*Reading this doc + the v0.3.4-IN-PROGRESS-HANDOFF should take ~8 minutes. The state is well-documented and the path is short — most of tomorrow is mechanical fixes against an already-passing baseline.*
