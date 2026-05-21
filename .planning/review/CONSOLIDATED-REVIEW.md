# Consolidated Ad-Copy Review — Flightnetwork SEM (v0.3.2)

**Reviewers:** 4 parallel `sem-ad-copy`-aligned agents
**Scope reviewed:**
- 10 PUBLISHED RSAs on live campaign `23860402014` (campaign is PAUSED but the ads exist on the account)
- 85 NEW RSAs from `04_responsive_search_ads.csv`, stratified-sampled across 18 ad groups spanning all discount bands + edge cases
- Total: 95 RSAs across 28 ad groups
**Date:** 2026-05-20

---

## Executive verdict

| Set | PASS | FLAG | BLOCK | Notes |
|---|---:|---:|---:|---|
| Published (old generator) | 0 | 0 | **10** | Wrong vertical (home services), false claims ("100 Years Experience"), truncation artifacts. Must not serve. |
| New chunk 1 (PRN/RBA/PKC/CHQ/CHS/OOL) | 4 | 21 | 5 | PKC name-length pattern collapse is the big block; 2 banned phrases in every social_proof. |
| New chunk 2 (KYA/VIE/NAT/BBI/GRV/CJB) | 4 | 18 | 8 | Same banned phrases + low-discount variants below useful threshold. |
| New chunk 3 (LEA/DLC/SHE/NY/LHR/SDF) | 1 | 11 | 13 | `from_price=null` ships naked `$`; Louisville data inversion broken at 3 layers. |
| **Total** | **9** | **50** | **36** | **38% block rate, 53% flag rate, 9% pass rate.** Not ship-ready. |

**Headline number: of 95 RSAs reviewed, 9 pass — and every one passes only "with edits". Zero are unconditionally clean.**

The new generator is structurally better than the old one (correct vertical, correct lever stacks, real proof points are reachable), but it ships 4 hard bugs that prevent any clean serving:

1. **A code bug** — `from_price=null` produces naked `$` in headlines/descriptions
2. **A data bug** — Louisville has `sku` and `name` inverted; URL targets `?to=Louisville` instead of `?to=SDF`
3. **A pattern bug** — long destination names (PKC 42 chars, Bhubaneswar 11 chars) overflow the char budget and headlines/descriptions truncate mid-word
4. **A compliance bug** — "ATOL-style protection" + "Top-rated travel agent" + "Was full price, now -X%" ship to every ad group with banned/misleading claims

These are all FIXABLE in the pattern library + a small generator change — not architecturally wrong. But the next push must NOT happen until they're closed.

---

## Cross-cutting findings (unanimous across reviewers)

### Severity 0 — STOP-SHIP (must fix before any push)

| # | Finding | Affected | Cited by |
|---|---|---|---|
| S0-1 | `from_price=null` produces visible `$ ` and "from in" fragments | All NY/LHR/SDF ads (12+ RSAs); any catalog row with missing price | D |
| S0-2 | `Louisville` data inversion (`sku=Louisville, name=SDF`) — URL targets wrong code | All 4 Louisville/SDF variants | D |
| S0-3 | **"100 Years Experience" / "Over 100 Happy Customers"** in every published ad — **false claim** (FN founded 1997, has 1.5M+ travelers) | All 10 published | A |
| S0-4 | **"ATOL-style protection"** — fabricates UK CAA-equivalent protection FN does not have. ASA-actionable in UK; FTC misleading-claims risk in US | Every social_proof variant in chunks 1, 2, 3 (15+ RSAs) | B, C, D |
| S0-5 | PKC long-name pattern collapse — headlines reduced to one-word fragments ("Flights", "Compare", "Limited", "Lowest"); V5 even ships **"Avoid Petropavlovsk-Kamchats"** (telling the searcher to avoid the destination they're searching) | All 5 PKC variants | B |
| S0-6 | Description truncation mid-word — "save the difference on every" (missing "leg"), "free 24h" (missing "cancellation"), "Last-minute Bhubaneswar" (missing "flights") | CHS-v5, OOL-v5, BBI-v3/v4/v5, CJB-v5, NY-all, LHR-all (~12 RSAs) | B, C, D |

### Severity 1 — Pattern-level slop (every RSA in catalog inherits these)

| # | Finding | Recommended fix |
|---|---|---|
| S1-1 | **"Top-rated travel agent"** in every social_proof variant — banned per skill | Replace with `"4.5★ Trustpilot ({review_count} reviews)"` |
| S1-2 | **"Was full price, now -X%"** — FTC/ASA false-anchor risk; no reference price ever shown | Replace with `"Was $Y, now $Z"` using calculated `Y = from_price / (1 - discount_pct)` |
| S1-3 | **"Today only: X% off"** — fake scarcity with no real deadline | Either pipe `promotion.end_date` for `"X% off ends {Day Mon DD}"`, or drop |
| S1-4 | **"Cheap {name} flights"** — low-status OTA cliché in every price_led | Replace with `"{name} from ${price}"` (price already says cheap) |
| S1-5 | **"Final seats: {name} ${price}"** / **"Last-minute"** without real low-inventory data | Replace urgency angle with **"Fares update every hour"** — the actual OTA differentiator |
| S1-6 | **"Compare fares today"** as pinned H3 across every v1 — generic, no friction-remover | Replace with **"Lock $X in 60 seconds"** (price + speed) or **"Compare 800+ airlines"** |
| S1-7 | **IATA codes in customer-facing copy** — "Skip the markup on KYA", "Price guarantee on VIE", "Flightnetwork - book BBI" — customers don't know airport codes | Maintain household-codes allowlist (LAX/JFK/LHR/CDG/etc.); for other SKUs, use destination name only |
| S1-8 | **"Member, IATA accredited"** — awkward word order | Replace with `"IATA-accredited agent"` |
| S1-9 | **"Price Drop Alerts Free"** — Title Case button label reads like UI element | Replace with `"Free price drop alerts"` |
| S1-10 | **Hyphen-as-em-dash substitution** — `"No hidden fees - ever"`, `"Konya - 800+ airlines"`, `"Flightnetwork - local..."` — stop-slop hard ban | Replace ` - ` with `, ` or use real em-dash |
| S1-11 | **Low-discount `discount_led` variants** — Vienna 8%, Natal 5%, Coimbatore 11% ship a variant where the % is too small to be a hook | Add `min_discount_pct >= 0.15` floor; below floor, emit a `risk_reversal` variant instead |
| S1-12 | **"Was full price, now -X%"** with mismatched destinations — every variant ships this even when no anchor is given | Either compute and show real anchor or drop (see S1-2) |
| S1-13 | **Discount % repeated in 9–11 of 15 headlines** — Google's semantic-similarity penalty kicks in | Cap at 5–6 discount-mention headlines; fill rest with proof/friction-removal |
| S1-14 | **H1/H2/H14/H15 identical across all 5 variants** within an ad group — 27% of every variant is the same string | Vary H14/H15 per variant role (price → "Lowest fare today"; discount → "{disc}% off this week"; social → "4.5★ Trustpilot"; urgency → "Fares updated hourly"; loss → "Skip the OTA markup") |

### Severity 2 — Tier-2 angle parity (the deepest problem)

> "22 of 25 variants could be run unchanged by Expedia, Kayak, Kiwi, or any other OTA." — Reviewer D

The new generator produces **competent template-driven copy**, but it doesn't pick a fight. The same line could ship on a competitor's account and no one would notice. The single biggest pattern-level improvement: **lead with the one Flightnetwork-specific moat** across every variant. Two strong candidates:

- **"Pay the airline price, not the markup"** (loss_aversion's current angle — promote to a default)
- **"Free 24h cancellation"** (genuine USP vs most OTAs — but bury-rate is high; needs to come forward to H4)

### Severity 3 — Brand-safety items (operator review needed)

- **GRV (Groznyj, Chechnya)** — Reviewer C flagged: confirm destination is on FN's allowed list before launching. Not a copy bug, but a launch blocker if FN has any sanctions or brand-safety overlay.
- **Localization** — Polish destinations (WMI), Brazilian (SJP), Spanish (XRY, SCQ), French (SJP) currently all get English ads. Per the skill: "If the client operates in multiple markets, write separate RSAs per market — never one bilingual ad." Right now Polish queries to "loty do Warszawy" get an English ad. Deferred for now (out of scope for this push) but flagged.

---

## Per-ad-group winners — the actual picks

### Published ads (campaign 23860402014) — all BLOCK, all need replacement

| # | Destination | Current verdict | Replacement variant (after pattern fixes) |
|---|---|---|---|
| 1 | Petropavlovsk-Kamchatsky (PKC) | BLOCK | price_led + social_proof (after long-name policy fix) |
| 2 | San Andres Island (ADZ) | BLOCK | price_led + urgency/seasonal (dry season) |
| 3 | West Palm Beach (PBI) | BLOCK | price_led + social_proof |
| 4 | Réunion (RUN) | BLOCK | price_led (disambiguate from "reunion" event) + loss_aversion |
| 5 | San Carlos De Bariloche (BRC) | BLOCK | price_led + urgency (ski season) + social_proof |
| 6 | Santiago De Compostela (SCQ) | BLOCK | price_led + identity (Camino pilgrim) |
| 7 | Santa Cruz De La Palma (SPC) | BLOCK | price_led + urgency (winter sun) |
| 8 | São José Do Rio Preto (SJP) | BLOCK | price_led (restore "São" + ideally Portuguese) + social_proof |
| 9 | Nowy Dwór Mazowiecki (WMI) | BLOCK | price_led (reframe as "Warsaw-Modlin") + social_proof |
| 10 | Jerez De La Frontera (XRY) | BLOCK | price_led + identity/seasonal (sherry, Feria) |

**Bottom line on published:** all 10 must be paused immediately and replaced wholesale.

### New variants — winner per ad group (after pattern fixes)

| Ad group | Discount | Price | Winner | Why |
|---|---:|---:|---|---|
| Pristina (PRN) | 22% | $580 | **V3 social_proof** | Earned proof stack — fix banned phrases first |
| Rabat (RBA) | 25% | $88 | **V3 social_proof** | $88 + 800+ airlines = strong combo; same banned-phrase fix |
| Petropavlovsk-Kamchatsky (PKC) | 22% | $224 | **None shippable** | Long-name pattern bug blocks all 5 variants — fix the templater |
| Chania (CHQ) | 42% | $589 | **V2 discount_led** | 42% off is loud enough to lead — fix the false anchor + fake scarcity |
| Charleston (CHS) | 41% | $254 | **V3 social_proof** | 41% loud, but social_proof reads more credible at US-domestic price |
| Gold Coast (OOL) | 34% | $317 | **V3 social_proof** | Same logic — competitor parity is the killer, proof breaks it |
| Konya (KYA) | 38% | $145 | **V5 loss_aversion** | Only differentiated angle ("skip the markup") |
| Vienna (VIE) | 8% | $347 | **V5 loss_aversion** | Discount too small to lead; loss-aversion wins by elimination |
| Natal (NAT) | 5% | $533 | **V5 loss_aversion** | $533 fare is exactly where "stop overpaying" lands |
| Bhubaneswar (BBI) | 60% | $116 | **V2 discount_led** | The rare case where 60% off + $116 from-price = headline magnet |
| Groznyj (GRV) | 56% | $141 | **V5 loss_aversion** | 56% is loud (V2 is also viable) — V5 picks the pattern interrupt |
| Coimbatore (CJB) | 11% | $162 | **V1 price_led** | $162 is category-leading price for India route; V5 is currently truncated |
| Learmonth (LEA) | 17% | $576 | **V2 discount_led** | Only **PASS** verdict in the entire chunk — H3 "Claim 17% off now" is Tier-1 |
| Dalian (DLC) | 0% | $260 | **V4 loss_aversion** | No discount → "skip the markup" angle differentiates |
| Shenyang (SHE) | 0% | $237 | **V4 loss_aversion** | Same. Also suppress SHE-the-IATA-code in customer copy (reads as pronoun) |
| NY → NYC | 0% | NULL | **None — BLOCK** | Remap SKU to NYC + supply price |
| LON-Heathrow → LHR | 0% | NULL | **None — BLOCK** | Remap SKU to LHR + supply price |
| Louisville → SDF | 0% | NULL | **None — BLOCK** | Fix data inversion + supply price |

### Winners by variant role (the actual signal)

| Variant role | Wins | When it wins |
|---|---:|---|
| **loss_aversion** | 6 | Mid-discount or no-discount destinations where competitor parity is the threat |
| **social_proof** | 4 | When the proof points carry weight (mid-price, well-known destinations) |
| **discount_led** | 3 | Only when discount ≥ 17% (LEA at 17%, CHQ at 42%, BBI at 60%) |
| **price_led** | 1 | When the price is genuinely category-leading (CJB at $162 for India) |
| **urgency** | 0 | Never wins as-is because "fake scarcity" execution undermines real urgency lever |

**Pattern:** the variant that wins is almost always the one that **isn't on parity** with competitors. The current generator produces 5 variants but 4 of them sound like every other OTA. The job for the next iteration is to make every variant the differentiated one.

---

## Fix manifest (ranked by ROI)

### Ship-blockers — close before any new push

1. **Null-safe `from_price` interpolation** (S0-1). Conditional in templates: if `from_price` is null, suppress the entire price token *and* surrounding scaffolding. Regression test: no headline/description contains a bare `$` followed by whitespace/period/EOS.
2. **Louisville data inversion** (S0-2). Fix the catalog row: `sku="SDF"`, `name="Louisville, KY"`.
3. **Remap non-IATA SKUs** (S0-2). NY→NYC, LON-Heathrow→LHR. Add IATA-validator to catalog loader that fails on unknown 3-letter codes unless `iata_override: true` is set.
4. **Pull the 10 published ads** (S0-3). Either delete campaign `23860402014` entirely or replace its RSAs. "100 Years Experience" is a false-claims liability.
5. **Banned-phrase scrub** (S1-1, S0-4). Strip these from patterns.json:
   - `"Top-rated travel agent"` → `"4.5★ on Trustpilot"`
   - `"ATOL-style protection"` → `"Free 24h cancellation"` or `"IATA-accredited agent"`
   - `"Was full price, now -X%"` → `"Was $Y, now $Z"` (computed)
   - `"Today only: X% off"` → `"X% off ends {date}"` (real date) or drop
   - `"Cheap {name} flights"` → `"{name} from ${price}"`
   - `"Member, IATA accredited"` → `"IATA-accredited agent"`
   - `"Price Drop Alerts Free"` → `"Free price drop alerts"`
6. **Long-name fallback policy** (S0-5, S0-6). When `len(name) >= 18`:
   - For descriptions: pull a `short_name` field (e.g., "PKC" for "Petropavlovsk-Kamchatsky", "NYC" for "New York City")
   - For path1: use IATA code, not truncated name
   - For headlines: substitute IATA code when full name overflows
   - Add a "no mid-word truncation" guard in `_fit_to_limit`
7. **`min_discount_pct` floor** (S1-11). `discount_led` only emits when `discount_pct >= 0.15`. Below floor, the slot falls back to `risk_reversal` (lead with "Free 24h cancellation").

### Strong wins — close before re-push if budget allows

8. **Pinned H3 by variant role** (S1-6). Replace generic `"Compare fares today"` with role-specific:
   - price_led: `"Lock ${price} in 60 seconds"`
   - discount_led: `"Claim {disc}% off now"` (already there)
   - social_proof: `"Compare 800+ airlines"` (already there)
   - urgency: `"Fares update every hour"` (currently buried at H11)
   - loss_aversion: `"Pay the airline price"` (currently `"See real flight prices"` which is OK)
9. **H14/H15 variant differentiation** (S1-14). Five different role-specific H14s instead of universal `"Flightnetwork - book {sku}"`.
10. **Discount-repetition cap** (S1-13). Maximum 5 `{disc}%` headlines per RSA; fill freed slots with proof + friction-removal.
11. **IATA-code suppression in customer-facing copy** (S1-7). Allowlist household codes (LAX, JFK, LHR, CDG, NRT, DXB, FCO, BCN, AMS, FRA, MAD, IST, SIN, HKG, NRT, SYD, GRU, MEX, YYZ, ~30 total); for other SKUs, default to destination name only.

### Quality lifts — schedule for next iteration

12. **Pin position swap** — H1 keyword/price, H2 brand. Currently H1 brand wastes the eye-landing position.
13. **Stop-slop post-pass** — em-dash detection, ASCII-å/ä/ö flattening (São → Sao), naked-punctuation detection. Catches the hyphen-as-em-dash issue and the truncation residue.
14. **Real urgency angle** — promote `"Fares update every hour"` from H11 to H3 in urgency variants; drop `"Final seats"`, `"Today only"`, `"Limited inventory"` unless backed by real data.
15. **De-templatisation pool** — rotate H3 phrasings across destinations to avoid semantic-similarity penalty at scale (1k destinations sharing identical copy is a Google Ads Ad Strength risk).
16. **Localization** — separate Polish, Portuguese, Spanish RSAs for those destinations.
17. **Pattern-interrupt H4** — every variant leads H4 with the same Flightnetwork-specific moat ("Pay the airline price, not the markup" or "Free 24h cancellation"). Solves angle parity at the pattern level.

---

## Recommended next steps (operator decision)

**Path A — "Pause and fix"** (recommended): hold off on `sem case push` until items 1–7 ship. Then re-push to a new campaign, smoke-test 10 ad groups, verify with reviewers on a fresh sample of 20-30 RSAs, then push the full 964.

**Path B — "Selective push"**: ship only the 9 PASS-with-edits RSAs (winners listed above) by manually editing the CSV, push to live as a controlled rollout, observe CTR for 2 weeks before deciding on full rollout. Higher operational cost; faster signal.

**Path C — "Ship and iterate"**: NOT recommended given the false-claim risk on the published ads and the broken-`$` bug on the new ones. Don't do this.

**My pick:** Path A. Items 1–7 are <1 day of focused work. Path B's manual-CSV-edit approach is fragile and skips the 1k-destination scale benefit of the new generator.

---

## Source files

- `D:\Second Brain\03 Projects\SEM Master\.planning\review\REVIEW-A-published.md` (Reviewer A — 10 published)
- `D:\Second Brain\03 Projects\SEM Master\.planning\review\REVIEW-B-chunk1.md` (Reviewer B — PRN/RBA/PKC/CHQ/CHS/OOL)
- `D:\Second Brain\03 Projects\SEM Master\.planning\review\REVIEW-C-chunk2.md` (Reviewer C — KYA/VIE/NAT/BBI/GRV/CJB)
- `D:\Second Brain\03 Projects\SEM Master\.planning\review\REVIEW-D-chunk3.md` (Reviewer D — LEA/DLC/SHE/NY/LHR/SDF)
- `D:\Second Brain\03 Projects\SEM Master\.planning\review\published_rsas.json` (live data dump)
- `D:\Second Brain\03 Projects\SEM Master\.planning\review\sample_chunk_{1,2,3}.json` (sampled new RSAs)
