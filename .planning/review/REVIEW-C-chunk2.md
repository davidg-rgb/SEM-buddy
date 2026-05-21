# Reviewer C — Chunk 2 (KYA, VIE, NAT, BBI, GRV, CJB)

## Summary

- **Total variants reviewed:** 30 RSAs across 6 ad groups (5 variants each — all 6 ad groups had discount > 0 so the full 5-variant set fires).
- **Verdict counts:** PASS 4 · FLAG 18 · BLOCK 8
- **Winners locked:** 6 (one per ad group)

### Cross-cutting wins
- Specificity Tax is mostly paid: price ($X), 800+ airlines, 1.5M travelers, 4.5★ Trustpilot, IATA accreditation, 24h cancel, 60-second book — all named, all provable. That's the only reason this set isn't a total wipe.
- First-three-words on H4–H9 in most variants actually front-loads the destination, the price, or the discount — the algorithm will at least get a relevance signal.
- Loss-aversion lever (variant 5) is genuinely the strongest angle in the set when it survives: "Stop overpaying for Konya. Lock $145 before weekly hikes" reads like a person wrote it, not a template.

### Cross-cutting issues (these recur in every ad group — fix at the pattern level, not per-ad)

1. **"Top-rated travel agent"** — banned English phrase ("top-rated" without a named source). Appears verbatim in the **social_proof variant of all 6 ad groups**. Auto-reject by the skill.
2. **"ATOL-style protection"** — fabrication risk. ATOL is a UK CAA financial-protection scheme. "ATOL-style" is hand-wavy weasel-wording. Flightnetwork is Canadian; this either claims a regulator they're not under or invents a parallel. Appears in **all 6 social_proof variants**. Replace with the real proof point (IATA accreditation, which is already in H12).
3. **IATA-code-in-customer-headline** — "Price guarantee on KYA", "Skip the markup on VIE", "Book Bhubaneswar from BBI" — customers do not know or search by airport code. They're cargo-trade shorthand and read like a developer's debug string. Appears in **every variant of every ad group, multiple times**.
4. **"Flightnetwork - book KYA/VIE/NAT/BBI/GRV/CJB"** — appears as H14 of EVERY variant of EVERY ad group. Triple violation: (a) within-RSA repetition Google penalises in Ad Strength, (b) the ASCII hyphen with surrounding spaces is the stop-slop "em-dash → hyphen substitution" tell, (c) IATA code. Kill this headline pattern entirely.
5. **"No hidden fees - ever"** — same hyphen-substitution issue. Native US English copy uses an em-dash or a comma here. The hyphen-with-spaces is an AI tell.
6. **Discount-led variant on low-discount destinations is malpractice.** Vienna 8%, Natal 5%, Coimbatore 11%. The skill says discount_led "REQUIRES literal % in ≥1 headline AND ≥1 description" — that's fine in principle, but **8% off as the sole angle of a variant** is so weak it actively repels clicks. Vienna at 8% off is an embarrassment headline. The pattern needs a `min_discount_pct` floor (e.g., 15%) below which it falls back to a different lever — see Pattern-level fixes.
7. **Truncation on long destination names.** Bhubaneswar (11 chars) and Coimbatore (10 chars) cause descriptions and headlines to truncate mid-word. Examples:
   - BBI v3 desc 2: `"...4.5★ Trustpilot, 24/7 support, free 24h"` — should end "free 24h cancellation". 77 chars. The ★ glyph is being counted as 2+ chars in the budget logic.
   - BBI v3 desc 3: `"...Compare every Bhubaneswar fare from 800+ airlines in one"` — missing "search".
   - BBI v4 H7: `"Last-minute Bhubaneswar"` — missing "flights".
   - BBI v4 H8: `"Bhubaneswar sale ends this"` — missing "week".
   - BBI v5 desc 4 and CJB v5 desc 4: `"...save the difference on every"` — missing "leg".
8. **"Was full price, now -38%"** — implies a strikethrough anchor price that doesn't exist anywhere in the ad or on the landing page. Compliance flag for FTC/ASA "before-and-after" claim. Across all 5 discount variants.
9. **"Save the difference on every leg"** — desc 4 of loss_aversion. "Leg" in flight parlance is a single segment of a journey. Saving "on every leg" implies a per-segment markup, which is nonsense. Read-aloud fails — no human travel marketer would phrase it this way.
10. **H1/H2/H14/H15 are identical across all 5 variants within an ad group.** Google's RSA system is supposed to test variants against each other; if 4 of 15 headlines are constants, you're handing the algorithm degenerate input.
11. **First-three-words on H1/H2 is fine but H3 differs by variant, and the H3s of the urgency/loss_aversion variants ("Book before seats sell", "See real flight prices") are limp.** These get pinned-equivalent eye real estate and should pay specificity tax harder.
12. **"Price Drop Alerts Free"** — Title Case feature label dropped without context. Reads like a button label, not a headline. "Free price-drop alerts" or "Get price-drop alerts" would be a sentence.

---

## Per-Ad-Group Reviews

### Konya (KYA)
Discount 38% · From $145 · Name length 5 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7/10 | "No hidden fees - ever" (em-dash sub), IATA in H14 | Solid price anchor, but H14/H15 are dead weight |
| 2 | discount_led | FLAG | Good | 8/10 | "Was full price, now -38%" (false anchor), IATA in H14 | 38% is strong enough to lead with — saves it |
| 3 | social_proof | BLOCK | Avg | 6/10 | "Top-rated travel agent", "ATOL-style protection" | Two banned/fabricated phrases. Block until rewritten. |
| 4 | urgency | FLAG | Good | 7/10 | IATA in H14, mild fake-scarcity ("Final seats: Konya $145") | "Fares update every hour" is a real differentiator — keep that angle |
| 5 | loss_aversion | PASS | Good | 8/10 | IATA in H14, "save the difference on every leg" in desc 4 | Strongest read-aloud. "Skip the markup" is genuinely fresh angle for OTA. |

**Per-variant detail:**

#### KYA Variant 1 — price_led
- H1/H2/H3 first-3-words audit: "Flightnetwork" (brand), "Konya" (destination), "Compare fares today" — H3 is generic verb-led, no number, no friction-remover. Should be "Konya from $145" (or pin the price into pos 3).
- Banned phrases: "No hidden fees - ever" uses hyphen-as-em-dash substitution.
- Levers actually pulled: specificity (price, 800+, 60s), friction-removal (24/7), one weak risk-reversal (no hidden fees).
- Read-aloud: passable. Sounds like a budget OTA, which is the right voice. H11 "No hidden fees - ever" and H12 "Price Drop Alerts Free" are jarring Title Case button-labels.
- Differentiation: Any of Kayak/Skyscanner/Kiwi could run this verbatim. That's a fail on "angle parity".
- Rewrite suggestions:
  - H3 "Compare fares today" (19) → "Konya from $145 today" (21)
  - H11 "No hidden fees - ever" (21) → "No hidden Konya fees" (20) or "Zero hidden fees" (16)
  - H12 "Price Drop Alerts Free" (22) → "Free Konya price alerts" (23)
  - H14 (kill the IATA pattern): "Flightnetwork - book KYA" (24) → "Flightnetwork since 2007" (24)

#### KYA Variant 2 — discount_led
- Discount-mention contract: CONFIRMED. "38%" appears in 9 of 15 headlines and 4 of 4 descriptions.
- First-3-words on H3 "Claim 38% off now" — number-led, strong.
- Banned phrases: "Was full price, now -38%" (false anchor, no `was` price ever shown). "Today only: 38% off" without a real deadline = fake scarcity (skill rule #10 in Common Mistakes).
- Levers actually pulled: discount + scarcity (some real, some fake).
- Read-aloud: 9 headlines saying "38%" reads spammy in the SERP. Even AdStrength will flag semantic similarity.
- Rewrite suggestions:
  - H4–H7 cluster: pick TWO ways to say "-38%", not five. "38% off Konya" (15), "Konya -38%" (12) — done. Use the freed slots for non-discount specificity: "1.5M flyers/year" (16), "800+ airlines compared" (22), "Free 24h cancel" (15).
  - H12 "Today only: 38% off" (20) → "38% off — ends Sunday" (21, with a real day) OR delete.
  - H13 "Was full price, now -38%" (24) → delete; replace with "Konya: 38% off + free 24h" (25)

#### KYA Variant 3 — social_proof
- BLOCK reasons:
  - "Top-rated travel agent" (H7, 22) — banned English phrase.
  - "ATOL-style protection" (H9, 21) — ATOL is a UK regulatory scheme Flightnetwork is not under; "-style" is weasel-language. Compliance + truth-in-advertising risk.
- Levers: authority + social proof — correctly chosen for the role.
- Read-aloud: H8 "Trustpilot rated 4.5★" reads well. H4 "Konya - 800+ airlines" again uses hyphen substitution.
- Description-level: desc 2 and 4 are actually strong ("Price-match guarantee on Konya. 4.5★ Trustpilot, 24/7 support, free 24h cancellation").
- Rewrite suggestions:
  - H7 "Top-rated travel agent" (22) → "1.5M travelers since 2007" (25) or "Booking 1.5M flyers/year" (24)
  - H9 "ATOL-style protection" (21) → "IATA-accredited agent" (21) [it's already in H12, but it's the real proof, not invented "ATOL-style"]
  - H4 "Konya - 800+ airlines" (21) → "Konya, 800+ airlines" (20)

#### KYA Variant 4 — urgency
- H3 "Book before seats sell" — generic urgency. Could specify ("Book Konya before fares jump").
- Real differentiator buried at H11 "KYA deals updated hourly" (24) — should be promoted. (Also lose the IATA code.)
- "Final seats: Konya $145" risks fake-scarcity flag if there are not actually limited seats at $145. Document the data source.
- Rewrite: H7 "Last-minute Konya flights" (25) is fine; H10 "Final seats: Konya $145" (23) → "Konya $145 fares update hourly" (30 — too long; shorten to "Konya $145 — hourly updates" 27).

#### KYA Variant 5 — loss_aversion (WINNER)
- "Stop overpaying for Konya" (24), "Skip the markup on KYA" (22), "Pay airline price, not more" (27), "Don't pay full Konya fare" (25) — this is the only variant in the chunk that picks a distinctive angle vs. competitor parity.
- First-3-words: "Stop overpaying", "Skip the markup", "Don't pay" — all pain-led. Textbook loss aversion from the skill's asymmetry rule.
- Issues: H9 "Skip the markup on KYA" — drop IATA. desc 4 "save the difference on every leg" is nonsensical.
- Rewrite: H9 → "Skip the OTA markup" (19); desc 4 → "Don't pay full fare to Konya. Compare 800+ airlines, pay airline price not the agency upcharge." (within 90 — actually 99, trim to: "Don't pay full Konya fare. Compare 800+ airlines, pay airline price not the markup." 87)

**Winner: Variant 5 (loss_aversion).** Only variant that doesn't read like Kayak/Skyscanner could lift it verbatim. Specificity is paid, lever is distinct, copy survives the read-aloud test.

---

### Vienna (VIE)
Discount 8% · From $347 · Name length 6 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7/10 | Hyphen-sub, IATA H14 | $347 anchor is fine but unexciting for Vienna |
| 2 | discount_led | BLOCK | Poor | 4/10 | False anchor, fake-scarcity, **8% off is too weak to lead** | Block: re-route this discount band to a different variant role |
| 3 | social_proof | BLOCK | Avg | 6/10 | "Top-rated", "ATOL-style" | Same as KYA v3 |
| 4 | urgency | FLAG | Good | 6/10 | IATA, fake scarcity | "Limited inventory" claim for Vienna (8% disc, mid-band) is thin |
| 5 | loss_aversion | PASS | Good | 7/10 | IATA, desc 4 phrasing | Best of the bunch by default |

**Per-variant detail:**

#### VIE Variant 2 — discount_led (BLOCK)
This is the worst RSA in the chunk. The brief forced an 8%-off variant for a destination where 8% is essentially the airline's normal price variance.
- H3 "Claim 8% off now" — read-aloud: a Vienna traveler is paying $347 to fly to Vienna and is being told to "claim" $28 off. The cognitive cost of clicking exceeds the offer.
- 8 of 15 headlines say "8%" — semantic similarity penalty + spammy SERP read.
- "Today only: 8% off" — fake scarcity.
- "Was full price, now -8%" — false anchor.
- **Recommended action:** Pattern-level fix — `discount_led` variant should only emit when `discount_pct >= 15`. Below that floor, the slot falls back to a `friction_removal` or `risk_reversal` variant.

#### VIE Variant 5 — loss_aversion (WINNER by elimination)
- "Stop overpaying for Vienna" (26) is the only headline in this whole ad group with a real CTR hook.
- Same systemic issues: IATA H9, desc 4 phrasing.

**Winner: Variant 5 (loss_aversion)** — and barely. If this ad group were standalone I'd kill the discount_led variant entirely.

---

### Natal (NAT)
Discount 5% · From $533 · Name length 5 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 6/10 | Hyphen-sub, IATA | $533 is the second-highest from-price in chunk — the price isn't the hook here |
| 2 | discount_led | BLOCK | Poor | 3/10 | **5% off is laughable as a lead** | Strongest BLOCK in chunk. Brief shouldn't have emitted this. |
| 3 | social_proof | BLOCK | Avg | 6/10 | "Top-rated", "ATOL-style" | Same systemic issue |
| 4 | urgency | FLAG | Good | 6/10 | Fake-scarcity risk, IATA | "Sale ends this week" + 5% disc = not credible |
| 5 | loss_aversion | PASS | Good | 7/10 | IATA, desc 4 | Default winner |

**Per-variant detail:**

#### NAT Variant 2 — discount_led (BLOCK)
"Claim 5% off now" / "5% off Natal flights" / "Was full price, now -5%". $533 → $506. **Twenty-seven dollars off a flight to Brazil.** This is a CTR-killer. The headline literally has more characters than the dollar savings. Block until pattern fix is in. Same logic as VIE v2.

#### NAT Variant 5 — loss_aversion (WINNER)
- "Stop overpaying for Natal" (25), "Natal prices rise weekly" (24), "Pay airline price, not more" (27).
- Read-aloud passes. For a $533 fare to Brazil, "stop overpaying" is genuinely the right angle — the user is sensitive to a $50–100 markup at this price level.

**Winner: Variant 5 (loss_aversion).** Same caveats: IATA H9, desc 4 phrasing.

---

### Bhubaneswar (BBI)
Discount 60% · From $116 · Name length 11 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 8/10 | Hyphen-sub, IATA | $116 anchor is genuinely strong |
| 2 | discount_led | PASS | Good | 9/10 | False anchor at H13, fake-scarcity H12 | **60% off is real enough to lead with** — this is what the variant is for |
| 3 | social_proof | BLOCK | Avg | 5/10 | "Top-rated", "ATOL-style", **truncation in descs 2 & 3** | Char-budget bug truncates two of four descs |
| 4 | urgency | FLAG | Avg | 6/10 | **H7 and H8 truncated mid-word**, IATA, fake-scarcity | "Last-minute Bhubaneswar" and "Bhubaneswar sale ends this" are publishable but obviously broken |
| 5 | loss_aversion | FLAG | Good | 7/10 | **desc 4 truncated**, "Stop overpaying Bhubaneswar" missing "for" | Pattern broke on long name |

**Per-variant detail:**

#### BBI Variant 2 — discount_led (WINNER)
- This is the variant the role was designed for: 60% off is dramatic, credible-looking, and worth front-loading. "Claim 60% off now" (17), "Save 60% on Bhubaneswar" (23), "60% off, $116+" (15) — number-led, specific, strong.
- The discount contract is fully honored (% in 9 headlines and 4 descriptions).
- Still has "Was full price, now -60%" (24) false-anchor issue — drop or replace.
- "Today only: 60% off" — only OK if there's a literal deadline. Otherwise fake-scarcity.

#### BBI Variant 3 — social_proof (BLOCK)
Two banned phrases plus **two truncated descriptions**:
- desc 2 ends `"...free 24h"` — supposed to end "free 24h cancellation". 77 chars where 90 was available.
- desc 3 ends `"...in one"` — supposed to end "in one search". 83 chars where 90 was available.
Root cause: the ★ glyph + long destination name + the descriptor pattern is overflowing the budget calculator. Defense in depth: count using `len(str.encode('utf-8'))` divided by something? Or just visual-width count? Either way, the pattern needs to be rendered safely. Block until truncation is fixed.

#### BBI Variant 4 — urgency
- H7 `"Last-minute Bhubaneswar"` — missing "flights".
- H8 `"Bhubaneswar sale ends this"` — missing "week".
- These ship to Google as-is — Google will accept them (within char limit), but they read as obvious truncation to any human. They WILL serve and they WILL look broken.
- Rewrite:
  - H7 → "Bhubaneswar fares -60%" (22)
  - H8 → "BBI sale ends Friday" (20, only if true)

#### BBI Variant 5 — loss_aversion
- H4 "Stop overpaying Bhubaneswar" (28) — the pattern dropped "for" to fit 30; other ad groups have "Stop overpaying for X". Inconsistent fallback.
- H6 "Don't pay full Bhubaneswar" (26) — missing "fare". Same truncation issue.
- desc 4 ends "save the difference on every" — missing "leg". Same as KYA v5.

**Winner: Variant 2 (discount_led).** The one ad group in the chunk where discount_led is actually the right answer. 60% off + $116 from-price is a CTR magnet. Fix the false-anchor headline ("Was full price, now -60%") and ship.

---

### Groznyj (GRV)
Discount 56% · From $141 · Name length 7 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7/10 | Hyphen-sub, IATA | Decent baseline |
| 2 | discount_led | PASS | Good | 8/10 | False anchor, fake-scarcity | 56% is enough to lead with |
| 3 | social_proof | BLOCK | Avg | 6/10 | "Top-rated", "ATOL-style" | Standard systemic block |
| 4 | urgency | FLAG | Good | 6/10 | IATA, soft fake-scarcity | "Updated hourly" buried as usual |
| 5 | loss_aversion | PASS | Good | 8/10 | IATA, desc 4 | Strong contender |

**Note on the destination itself:** "Groznyj" is the capital of Chechnya, Russia. There may be a sanctions/compliance/brand-safety concern about actively promoting flights there, separate from the copy quality. Flag for the account team to confirm Groznyj is on Flightnetwork's allowed destination list. Not a copy review item but a "do not ship until verified" item.

#### GRV Variant 2 — discount_led (Strong contender for winner)
- "Claim 56% off now" (17), "Save 56% on Groznyj" (19), "56% off, $141+" (15).
- Same false-anchor issue at H13.
- The dollar savings is real here: 56% off $141 saves ~$179 (off implied $320 full fare). That's a meaningful number to lead with.

#### GRV Variant 5 — loss_aversion (WINNER)
- Marginally edges v2 because the loss-aversion angle differentiates from competitors who will all be running discount % copy. Pattern interrupt logic.
- "Stop overpaying for Groznyj" (26) + "Pay airline price, not more" (27) is the angle no Kayak/Skyscanner clone will copy.

**Winner: Variant 5 (loss_aversion).** With the same systemic fixes (IATA H9, desc 4 phrasing).

---

### Coimbatore (CJB)
Discount 11% · From $162 · Name length 10 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | PASS | Good | 7/10 | Hyphen-sub, IATA | $162 is a strong anchor for India route |
| 2 | discount_led | FLAG | Avg | 5/10 | False anchor, fake-scarcity, **11% is borderline** | 11% is just above the recommended floor — passes by inches |
| 3 | social_proof | BLOCK | Avg | 6/10 | "Top-rated", "ATOL-style" | Same systemic block |
| 4 | urgency | FLAG | Good | 6/10 | IATA, fake-scarcity | "Hourly updates" buried |
| 5 | loss_aversion | FLAG | Good | 7/10 | **desc 4 truncated**, "Stop overpaying Coimbatore" missing "for" | Same long-name truncation as BBI |

**Per-variant detail:**

#### CJB Variant 1 — price_led
- Genuinely solid. $162 to Coimbatore is a price worth leading with — Indian-route travelers are extremely price-sensitive.
- Same systemic issues (H11 hyphen-sub, H14 IATA pattern).
- Front-three-words on H4 "Coimbatore from $162" (20) — destination + price = exactly right.

#### CJB Variant 2 — discount_led
- 11% off $162 = $18 saved. Same problem as VIE/NAT but slightly less embarrassing. Still under the recommended 15% floor.
- 9 headlines say "11%". Spammy.

#### CJB Variant 5 — loss_aversion
- desc 1 starts "Stop overpaying Coimbatore" — missing "for" (same drop as BBI v5 H4).
- desc 4 ends "save the difference on every" — missing "leg" (same as KYA/BBI).
- "Lock $162 before weekly hikes" reads well — pain + price + scarcity stacked correctly.

**Winner: Variant 1 (price_led).** Only ad group in the chunk where price_led wins — and it's because $162 to Coimbatore is a category-leading price point, and loss_aversion variant 5 is bug-truncated. Once truncation is fixed, the winner re-evaluates to v5 (same reasoning as other ad groups).

---

## Pattern-level fixes (apply to ALL ad groups via patterns.json edits)

These are systemic — fixing them in the JSON pattern library fixes all six ad groups (and the rest of the catalog) at once.

### 1. Banned-phrase removals (highest priority)
- Remove `"Top-rated travel agent"` from social_proof pattern. Replace with `"Booking 1.5M flyers/year"` (24 chars) or `"IATA agent since 2007"` (22 chars, if year is correct).
- Remove `"ATOL-style protection"` entirely. Replace with `"IATA-accredited agent"` (21 chars) — which is the real proof point and matches existing H12.

### 2. Kill the IATA-code-in-customer-copy patterns
- `"Flightnetwork - book {iata}"` H14 across every variant — replace with non-IATA brand+proof headlines:
  - `"Flightnetwork since 2007"` (24)
  - `"Trusted by 1.5M flyers"` (22)
  - `"4.5★ on Trustpilot"` (18)
- `"{iata} flights from ${price}"` H7 in price_led — replace with `"{name} fares from ${price}"` (length depends on name).
- `"Price guarantee on {iata}"` H6 in social_proof — replace with `"Price-match {name} fares"` (length-dependent).
- `"Skip the markup on {iata}"` in loss_aversion — replace with `"Skip the OTA markup"` (19, name-independent).

### 3. Hyphen-substitution / em-dash bug
- Stop-slop rule (Part 1 hard ban): no ASCII hyphen with spaces around it as a sentence pause. Affected templates:
  - `"No hidden fees - ever"` → `"No hidden fees, ever"` (20)
  - `"Konya - 800+ airlines"` → `"Konya, 800+ airlines"` (length-1)
  - `"Stop overpaying for {name}. Lock ${price} before weekly hikes - 800+ airlines in one search"` → swap " - " for ". " or ", ".
  - `"{name} sale: -{disc}%, fares from ${price}. No hidden fees"` → `"{name} sale: -{disc}% — fares from ${price}. No hidden fees"` (use actual em-dash if rendering correctly).

### 4. Discount-led variant requires a `min_discount_pct` floor
- Below 15%, do NOT emit the discount_led variant. The brief's contract ("REQUIRES literal % in ≥1 headline AND ≥1 description") becomes a liability when the discount is small. 5%, 8%, 11% off variants are CTR-negative.
- Below 15%, substitute a `friction_removal` variant (lead with "Free 24h cancel", "Compare in 60 seconds", "Pay in your currency").
- Above 15%, keep current discount_led pattern but cap "% mentions" at 4 headlines (currently 9 — semantic-similarity penalty).

### 5. False-anchor headline
- `"Was full price, now -{disc}%"` is a before/after price claim with no anchor price ever shown on the ad or LP. FTC §255 / ASA guidance prohibits this without a substantiated reference price. Remove globally. Replace with a non-anchor headline: `"{disc}% off {name} fares"` or `"Lowest {name} fare today"`.

### 6. Fake-scarcity claims
- `"Today only: {disc}% off"` (H12, discount_led) — only emit if a real deadline exists. Otherwise replace with `"{disc}% off — limited inventory"` (which is verifiably true for any flight) or simply `"Save {disc}% — fares from ${price}"`.
- `"{name} sale ends this week"` (H8, urgency) — same. Only emit with a real Saturday/Sunday end.
- `"Final seats: {name} ${price}"` (H10, urgency) — needs real low-inventory data. Otherwise replace with `"{name} ${price} — hourly updates"`.

### 7. Long-name truncation bug
The character-budget calculator is silently chopping descriptions/headlines for destinations >= 10 chars. Observed truncations:
- `"...4.5★ Trustpilot, 24/7 support, free 24h"` (BBI v3 d2) — should reach 90 with "cancellation"
- `"...Compare every Bhubaneswar fare from 800+ airlines in one"` (BBI v3 d3) — should reach 90 with "search"
- `"...save the difference on every"` (BBI/CJB v5 d4) — should reach 90 with "leg"
- `"Last-minute Bhubaneswar"`, `"Bhubaneswar sale ends this"`, `"Stop overpaying Bhubaneswar"`, `"Don't pay full Bhubaneswar"`, `"Don't pay full Coimbatore fare"` — headlines partially truncated.

Likely root cause: ★ (U+2605, 3 UTF-8 bytes) being counted as 3 chars instead of 1 visible glyph, AND the pattern engine choosing to drop trailing words instead of swapping templates. Fix:
- Count visual width (`len()` after stripping zero-width chars), not byte length.
- Add a fallback template branch when the long-name version doesn't fit, instead of dropping trailing words.

### 8. Within-RSA H1/H2/H14/H15 repetition
Every variant within an ad group shares H1, H2, H14, and H15. That's 4/15 (27%) of every variant being identical strings. Vary these per variant role to give Google's RSA engine real signal:
- Variant 1 (price_led) H14: `"Lowest {name} fare today"`
- Variant 2 (discount_led) H14: `"{name}: {disc}% off this week"`
- Variant 3 (social_proof) H14: `"4.5★ on Trustpilot"`
- Variant 4 (urgency) H14: `"{name} fares updated hourly"`
- Variant 5 (loss_aversion) H14: `"Skip the OTA markup"`
And similarly for H15.

### 9. H3 (the de-facto eye-catcher position) is weakest in urgency/loss_aversion variants
- urgency H3 `"Book before seats sell"` (22) → `"{name} fares update hourly"` (length-dependent) — converts a real differentiator into the headline position.
- loss_aversion H3 `"See real flight prices"` (22) → `"Skip the OTA markup on {name}"` or `"Pay airline price, not OTA markup"` (33 — too long; use `"Pay the airline price"` 22).

### 10. "Price Drop Alerts Free" Title Case button-label
- H12 in price_led: `"Price Drop Alerts Free"` (22) reads like a UI element pulled out of context. Reword: `"Free price-drop alerts"` (22) or `"Get price-drop alerts"` (21).

### 11. Compliance/brand-safety pre-flight
- Confirm Groznyj is on Flightnetwork's permitted destinations list before this ad ships. (Chechnya routing has had sanctions overlay historically; not a copy bug but a launch blocker.)
- Confirm the "60-second book" claim is verifiable on the LP.
- Confirm "1.5M travelers/year" and "800+ airlines" are current numbers from the brand book, not aspirational.

---

## Final winners summary

| Ad group | Winner | Why |
|---|---|---|
| Konya (KYA) | Variant 5 — loss_aversion | Only differentiated angle; passes read-aloud |
| Vienna (VIE) | Variant 5 — loss_aversion | By elimination; discount/social/urgency all blocked or weak |
| Natal (NAT) | Variant 5 — loss_aversion | $533 fare is exactly where loss-aversion wins |
| Bhubaneswar (BBI) | Variant 2 — discount_led | 60% off is the rare case where discount actually leads |
| Groznyj (GRV) | Variant 5 — loss_aversion | Edges discount_led on pattern-interrupt; both viable |
| Coimbatore (CJB) | Variant 1 — price_led (or v5 once truncation fixed) | $162 is category-leading price; v5 currently bug-truncated |

**If only one pattern change ships before launch, it should be #1 (banned-phrase removal — "Top-rated travel agent" + "ATOL-style protection"). Those two ship a fabrication risk and a banned phrase to every social_proof RSA in the catalog.**

**If two ship: also #4 (min_discount_pct floor). The current 5%/8%/11% discount_led variants are a CTR drain and dilute the Ad Strength signal of the rest of the RSA group.**
