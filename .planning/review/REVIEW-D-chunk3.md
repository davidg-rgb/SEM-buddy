# Reviewer D — Chunk 3 (LEA, DLC, SHE, NY, LON-Heathrow, Louisville)

## Summary

- **Total variants reviewed:** 25 RSAs across 6 ad groups (LEA=5, DLC=4, SHE=4, NY=4, LON-Heathrow=4, Louisville/SDF=4)
- **PASS: 1 / FLAG: 11 / BLOCK: 13**
- **Net assessment:** Three of six ad groups (NY, LON-Heathrow, Louisville/SDF) are categorically un-shippable due to `from_price=null` substitution leaving naked `$` and `from $` fragments in nearly every headline and description. The other three (LEA, DLC, SHE) are mechanically valid but stuck in Tier-2 angle parity — competitor-swappable, banned phrases throughout ("Top-rated travel agent", "Cheap [X] flights", "Price guarantee"), and one assertion ("ATOL-style protection") that is materially misleading for a US/CA OTA. The discount-led variant for LEA is the strongest unit in the chunk.
- **Cross-cutting wins:**
  - Discount-led LEA (variant 2) is the only variant that pulls real lever-stacking (% off + scarcity + price anchor) and front-loads numbers per the First-Three-Words Doctrine
  - "1.5M travelers" and "800+ airlines" are real proof points and used consistently
  - "Free 24h cancellation" is a legitimate risk-reversal lever that appears across variants
- **Cross-cutting issues:**
  - **BLOCK-level data bug:** When `from_price` is `null`, the pattern interpolates an empty value and produces headlines like "New York City from $", descriptions like "Stop overpaying for SDF. Lock before weekly hikes". This isn't a copywriting flaw, it's a code bug, and it ships broken English to Google. Half the chunk is affected.
  - **Louisville/SDF data inversion:** `sku="Louisville", name="SDF"` is backwards. The actual airport code is SDF and the city is Louisville. Every headline reads "SDF from $", "Cheap SDF flights", "Last-minute SDF flights" — nobody searches for "SDF flights" because nobody calls it that. This is a 0-CTR ad group as-is.
  - **"Top-rated travel agent"** appears in every social-proof variant. It's on the banned English list ("Top-rated" without a source = empty). Trustpilot 4.5★ is the source — front-load that instead.
  - **"Cheap [X] flights"** appears in every price-led variant H8. It's the lowest-status word in OTA copy and it reads like a 2010 AdSense farm. "From $X" already says cheap — let the number do the work.
  - **"ATOL-style protection"** is misleading for a US/CA OTA. ATOL is UK CAA financial protection; "ATOL-style" implies equivalence without provable basis. Either drop it or replace with the real US equivalent (IATA-accredited + USDOT licensed). This is the kind of line that gets ASA/FTC attention.
  - **"Price Drop Alerts Free"** (Title-Cased mid-sentence) reads like a banner ad. Either sentence-case it or kill it.
  - **Angle parity within the chunk:** Variants 1, 3, 4 across LEA/DLC/SHE are word-for-word identical except for the destination name and price. If the algorithm rotates them across keywords, Google's similarity-detection penalty applies and Ad Strength craters.
- **Non-IATA SKU recommendation:** **REMAP all three.** NY → NYC, LON-Heathrow → LHR, Louisville → SDF. Reasoning in the dedicated section below.

---

## Per-Ad-Group Reviews

### LEA (Learmonth, Australia) — `sku=LEA`

- Discount: 17% · From price: $576 · Name length: 9 · IATA-valid: Y (Learmonth Airport, AU)

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7 | "Cheap Learmonth flights" | Number-led but mostly redundant headline phrasing |
| 2 | discount_led | PASS | Excellent | 9 | none flagged | Best variant in the chunk; real % stacking |
| 3 | social_proof | BLOCK | Good | 6 | "Top-rated travel agent", "ATOL-style protection" | Banned + misleading |
| 4 | urgency | FLAG | Good | 7 | "Last-minute Learmonth flights" borderline | Real scarcity but reads thin |
| 5 | loss_aversion | FLAG | Good | 6 | none | Good angle, weak execution |

**Per-variant detail:**

#### Variant 1 — price_led
- **H1/H2/H3 first-three-words audit:** H1 "Flightnetwork" (brand, OK for pin1). H2 "Learmonth" (keyword, OK). H3 "Compare fares today" — fails First-Three-Words: "Compare fares today" front-loads a generic verb + generic noun + filler adverb. Closer to banned "Get started today!" than to a real CTA. Should be "Compare 800+ airlines" (already in variant 3) or "Fares from $576".
- **Banned phrases:** "Cheap Learmonth flights" — not literally on the banned list but it's the OTA equivalent of "Premium quality at affordable prices" — empty signaling. "Price Drop Alerts Free" — capitalisation reads AI-generated.
- **Levers actually pulled:** Specificity (price), friction-removal (no hidden fees, 24/7). Two only — meets minimum but barely.
- **Read-aloud test:** Sounds like every other OTA. Could be Kayak, Skyscanner, Kiwi, anyone.
- **Differentiation:** Could a competitor run identical copy? **Yes.** Swap the URL, ship for Expedia. Zero Flightnetwork-specific differentiation.
- **Rewrite suggestions:**
  - "Cheap Learmonth flights" (23 chars) → "Learmonth from $576, no fees" (28 chars)
  - "Compare fares today" (19 chars) → "800+ airlines compared" (22 chars) — already in variant 3, lift it
  - "24/7 booking, real prices" (25 chars) → "Real fares, 24/7 booking" (24 chars) — flip the order, real-fares first

#### Variant 2 — discount_led
- **H1/H2/H3 first-three-words audit:** H1 brand OK. H2 keyword OK. H3 "Claim 17% off now" (17 chars) — front-loads verb + number + urgency. **This is the textbook Tier-1 H3 in the entire chunk.**
- **Banned phrases:** None of the hard bans. "Was full price, now -17%" is a little 2008-direct-response but it's framed as loss-aversion, which is the variant's job.
- **Discount-mention contract (discount_led):** Required literal % in ≥1 headline AND ≥1 description. **CONFIRMED:** "17%" appears in 11 headlines and all 4 descriptions. (Arguably overstuffed — see below.)
- **Levers actually pulled:** Loss aversion (% off framing), scarcity ("Today only", "Limited inventory"), specificity ($576), risk reversal (free 24h cancel).
- **Read-aloud test:** Sounds like a real OTA promo email subject line. Passes.
- **Differentiation:** Harder to swap — the 17% is a real, claimed number. A competitor running this identical copy would need their own 17%, and they don't have it.
- **Issues to fix:**
  - "17% off, $576+" (14 chars) is the only headline that pairs both numbers — that's the winning combination. Promote it to a pinned-ish position by using it as H4. (You can't pin 4 positions without strength penalty, but you can de-duplicate so it's the strongest unpinned card.)
  - 11 of 15 headlines mention 17%. That triggers Google's semantic-similarity dampening. Cut to 5–6 % headlines max and replace the rest with proof variants ("4.5★ Trustpilot", "800+ airlines", "Free 24h cancel").
  - "Was full price, now -17%" (24 chars) — "full price" is fuzzy. Better: "$695 → $576 (-17%)" (18 chars) if the strike-through price is real and disclosable.

#### Variant 3 — social_proof
- **H1/H2/H3 first-three-words audit:** H3 "Compare 800+ airlines" (21 chars) — passes, number-led.
- **Banned phrases:** **"Top-rated travel agent" — hard banned** ("Top-rated" without a source is dead per the English table). **"ATOL-style protection" — compliance flag** (US/CA OTA claiming UK CAA-style protection without basis is materially misleading; "style" doesn't save it).
- **Levers actually pulled:** Social proof (1.5M, 800+, 4.5★), authority (IATA-accredited). Risk-reversal (refund policy) — but "no hassle" is a banned-phrase neighbour ("hassle-free [X]") that should be replaced with what's actually removed.
- **Read-aloud test:** "ATOL-style protection" stops the read cold for anyone in the UK who knows what ATOL is.
- **Differentiation:** Could be Expedia, but the 1.5M / 800+ / Trustpilot stack is at least real Flightnetwork ownership.
- **Rewrite suggestions:**
  - "Top-rated travel agent" (22 chars) → "4.5★ Trustpilot (X reviews)" — name the review count and cap to 30
  - "ATOL-style protection" (21 chars) → "USDOT-licensed agent" (20 chars) for US, or split markets
  - "Refund policy, no hassle" (24 chars) → "Free 24h cancel, no fees" (24 chars) — concrete

#### Variant 4 — urgency
- **H1/H2/H3 first-three-words audit:** H3 "Book before seats sell" (22 chars) — passes, verb-led + loss aversion.
- **Banned phrases:** "Last-minute Learmonth flights" — borderline OTA cliché. "Limited inventory, real fares" (29 chars) is OK but the comma-bracketed "real fares" reads tacked on.
- **Levers actually pulled:** Scarcity, friction removal (60 seconds), price.
- **Read-aloud test:** OK. Sounds like a sale-week email.
- **Differentiation:** Low. Anyone can claim limited inventory. The "fares update every hour" line is the only specific claim; lean harder into it.
- **Rewrite suggestions:**
  - "Limited inventory, real fares" → "Fares update hourly" (19 chars)
  - "Last-minute Learmonth flights" (29 chars) — keep but only if you actually have last-minute inventory advantage

#### Variant 5 — loss_aversion
- **H1/H2/H3 first-three-words audit:** H3 "See real flight prices" (22 chars) — front-loads imperative + "real" which earns a beat against opaque competitor pricing. Passes.
- **Banned phrases:** None hard-banned. "Skip the markup on LEA" — saying "LEA" as a customer-facing term is poor (see IATA section). Most travelers don't know LEA = Learmonth.
- **Levers actually pulled:** Loss aversion ("stop overpaying", "don't pay full"), framing ("airline price, not more"), specificity ($576). Three levers, good stack.
- **Read-aloud test:** "Pay airline price, not more" sounds like real OTA copy. The "Skip the markup" angle is genuinely a Flightnetwork-able message (they're a fare aggregator, not the airline).
- **Differentiation:** This is the second-best variant after V2. It picks a fight with "the markup" which is a real consumer pain point.
- **Rewrite suggestions:**
  - "Skip the markup on LEA" → "Skip the agency markup" (22 chars) — drop the IATA code from customer-facing headline
  - "Learmonth prices rise weekly" — claim or drop. If you don't have weekly hike data, this fails the compliance check.

**Winner for this ad group:** **Variant 2 (discount_led)**. It's the only variant where the lever stack is real, the specificity tax is paid (17% + $576), and the H3 ("Claim 17% off now") fronts a verb + number + urgency. The discount mention contract is over-fulfilled — trim the % repetition and it's shippable Tier 1.

---

### DLC (Dalian, China) — `sku=DLC`

- Discount: 0% (no discount_led variant) · From price: $260 · Name length: 6 · IATA-valid: Y

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7 | "Cheap Dalian flights" | Identical to LEA V1 with name swap |
| 2 | social_proof | BLOCK | Good | 6 | "Top-rated travel agent", "ATOL-style protection" | Same blockers as LEA V3 |
| 3 | urgency | FLAG | Good | 6 | none | Same template as LEA V4 |
| 4 | loss_aversion | FLAG | Good | 6 | none | Same template as LEA V5 |

**Per-variant detail:**

#### Variant 1 — price_led
- **First-three-words audit:** Same as LEA V1. H3 "Compare fares today" fails — generic.
- **Banned phrases:** "Cheap Dalian flights", "Price Drop Alerts Free".
- **Levers:** Specificity (price), friction removal. Two only.
- **Read-aloud test:** Word-for-word identical to LEA V1 except destination/price. **This is the cross-cutting problem:** if both ads serve, Google sees them as duplicates with low diversity. Either pattern-vary at the variant level or accept that the price-led template is the universal floor for every destination.
- **Differentiation:** None.
- **Rewrite suggestions:** Same as LEA V1. Pattern-level fix required.

#### Variant 2 — social_proof
- Same blockers as LEA V3. "Top-rated travel agent" + "ATOL-style protection" both fail.
- **Note:** The headline "1.5M travelers, every year" — Oxford comma between "travelers" and "every year" makes "every year" feel parenthetical and breaks the rhythm. Better: "1.5M travelers a year" (21 chars) which already appears in the descriptions and reads cleaner.

#### Variant 3 — urgency
- Standard urgency template. "DLC deals updated hourly" — same IATA-code-in-headline issue as LEA. Customers don't search DLC. Use "Dalian deals updated hourly" (already at 27 chars — fits).
- **Rewrite suggestions:**
  - "DLC deals updated hourly" → "Dalian fares update hourly" (26 chars)

#### Variant 4 — loss_aversion
- "Skip the markup on DLC" (22 chars) — same issue: replace IATA code with verbose form or drop entirely.
- **Rewrite suggestions:**
  - "Skip the markup on DLC" → "Skip the agency markup" (22 chars)

**Winner for this ad group:** **Variant 4 (loss_aversion)** by a thin margin. The "skip the markup" angle is the only variant that argues *why Flightnetwork specifically* rather than just *why any flight booking*. V1 is too generic, V2 has blockers, V3 is identical to every other urgency variant.

---

### SHE (Shenyang, China) — `sku=SHE`

- Discount: 0% (no discount_led variant) · From price: $237 · Name length: 8 · IATA-valid: Y

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7 | "Cheap Shenyang flights" | Template clone |
| 2 | social_proof | BLOCK | Good | 6 | "Top-rated travel agent", "ATOL-style protection" | Same blockers |
| 3 | urgency | FLAG | Good | 6 | none | Template clone |
| 4 | loss_aversion | FLAG | Good | 6 | none | Template clone |

**Per-variant detail:**

#### Variant 1 — price_led
- Word-for-word identical to LEA V1 / DLC V1 with name swap. Same critique applies.
- Specific Shenyang note: "SHE" as an IATA code reads awkwardly in English-language ads because it spells a pronoun. "SHE flights from $237" reads briefly as "she flights from $237" — pattern-interrupt for the wrong reason. Consider suppressing IATA-code headlines on SKUs where the code is a common-English word (SHE, HER, LAX is fine because it's a household IATA code).

#### Variant 2 — social_proof
- Same blockers.
- "Price guarantee on SHE" (22 chars) — even more egregious here. Reads "price guarantee on she". Suppress.

#### Variant 3 — urgency
- "SHE deals updated hourly" — same problem. "Shenyang deals updated hourly" is 30 chars; "Shenyang fares update hourly" (28 chars) is cleaner.

#### Variant 4 — loss_aversion
- "Skip the markup on SHE" — same problem.

**Winner for this ad group:** **Variant 4 (loss_aversion)** for the same reason as DLC — it's the only variant arguing a Flightnetwork-specific angle. But it needs the IATA-code suppression fix before shipping.

---

### NY (intended: New York City) — `sku=NY`

- Discount: 0% · From price: **null** (BLOCKING BUG) · Name length: 13 · IATA-valid: N (correct code is NYC for all NYC airports; JFK/LGA/EWR for individual airports)

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | BLOCK | Poor | 1 | "Cheap New York City flights" | Naked "$" everywhere |
| 2 | social_proof | BLOCK | Poor | 3 | "Top-rated travel agent", "ATOL-style protection" + naked $ | Two blockers compound |
| 3 | urgency | BLOCK | Poor | 2 | none | Naked "$" + truncation |
| 4 | loss_aversion | BLOCK | Poor | 2 | none | Naked "$" everywhere |

**Per-variant detail:**

All four NY variants are BLOCKED by the same root cause: `from_price` is `null` and the template interpolates the empty value, producing visible garbage.

#### Variant 1 — price_led
- **Headline 4:** "New York City from $" (20 chars) — ships a literal `$` with no number. Looks broken.
- **Headline 5:** "Flights to New York City $" (26 chars) — same.
- **Headline 7:** "NY flights from $" (17 chars) — uses "NY" (non-IATA, not searched), trailing `$`, broken.
- **Headline 10:** "Book New York City from $" (25 chars) — broken.
- **Description 1:** "New York City from $. Compare 800+ airlines, lock the lowest fare in 60 seconds" — ships "$." (dollar-sign-period). Looks like a typo from Google's perspective and reads like one to humans.
- **Description 3:** "Lock New York City from before fares climb. Compare 800+ airlines side by side" — the price was elided entirely, leaving "from before" which is gibberish.
- **First-three-words audit:** Irrelevant; copy doesn't ship.
- **Levers:** N/A — broken before lever evaluation matters.
- **Read-aloud test:** Fails catastrophically.
- **Differentiation:** Negative — actively makes Flightnetwork look unprofessional.
- **Rewrite:** Cannot rewrite. The pattern needs a conditional: when `from_price` is null, suppress the price-led variant entirely or fall back to "Find New York City fares" without a number anchor.

#### Variant 2 — social_proof
- Headline blockers still present ("Top-rated travel agent", "ATOL-style protection") AND naked `$` blockers.
- **Description 2:** "Price-match guarantee on New York City. 4.5★ Trustpilot, 24/7 support, free 24h" — got truncated to "free 24h" mid-thought because of name-length budget. Reads broken.
- **Description 3:** "Trusted by 1.5M travelers. Compare every New York City fare from 800+ airlines in one" — truncated at "in one" mid-sentence. Reads broken.
- **Description 4:** "IATA-accredited agent. New York City fares from $, with refund policy and 24/7 help" — naked `$`.

#### Variant 3 — urgency
- **Headlines 7, 8:** "Last-minute New York City" / "New York City sale ends this" — both truncated mid-thought because the destination name eats budget. "ends this" is grammatically incomplete.
- **Descriptions:** All four contain naked `$` or "from in" (preposition orphan).

#### Variant 4 — loss_aversion
- **Headline 6:** "Don't pay full New York City" (28 chars) — "full New York City" reads as "the entire city of New York" rather than "the full fare to NYC". Comprehension fails.
- **Headline 4:** "Stop overpaying New York City" (29 chars) — missing "for".
- **Descriptions:** All naked `$` or truncated.

**Winner for this ad group:** **None — block all four.** This entire ad group must be regenerated after (a) remapping SKU to NYC and (b) supplying a real `from_price` or implementing a null-safe template branch.

---

### LON-Heathrow (intended: London Heathrow) — `sku=LON-Heathrow`

- Discount: 0% · From price: **null** · Name length: 6 · IATA-valid: N (correct code is LHR for Heathrow specifically, LON for all London airports)

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | BLOCK | Poor | 2 | "Cheap London flights" + naked $ | Hyphenated SKU bleeds through |
| 2 | social_proof | BLOCK | Poor | 4 | "Top-rated travel agent", "ATOL-style protection" + naked $ | Blockers compound |
| 3 | urgency | BLOCK | Poor | 3 | none + naked $ | Truncation visible |
| 4 | loss_aversion | BLOCK | Poor | 3 | none + naked $ | Same |

**Per-variant detail:**

All four variants are BLOCKED by the same `from_price=null` bug as NY.

#### Variant 1 — price_led
- **Headline 7:** "LON-Heathrow flights from $" (27 chars) — the hyphenated SKU shows up verbatim. Reads as a typo of "London Heathrow" with extra punctuation. Customer parses "LON" as an abbreviation they don't recognise. No one searches "LON-Heathrow flights".
- **Headline 14:** "Flightnetwork - book" (20 chars) — got truncated because there was no value to inject after "book". Should have been "book LON-Heathrow" but the template chose to omit rather than ship the hyphenated form (good defensive behaviour but exposes the gap).
- **All descriptions:** Naked `$` everywhere.

#### Variant 2 — social_proof
- Same blockers as everywhere else, plus naked `$`.
- **Headline 6:** "Price guarantee" (15 chars) — got name-stripped down to a generic floating "Price guarantee" instead of "Price guarantee on London". The template's defensive fallback exposed that the SKU itself was being injected as guarantee target, which is wrong design.

#### Variant 3 — urgency
- **Headline 11:** "LON-Heathrow deals updated" (26 chars) — same hyphenated-SKU readability issue. Should say "London deals updated" (20 chars) which fits.
- **Descriptions:** Naked `$` and truncated price prepositions.

#### Variant 4 — loss_aversion
- **Headline 9:** "Skip the markup" (15 chars) — name-stripped to generic. Loses the destination tie.
- **Descriptions:** Naked `$`.

**ATOL note:** Of all six ad groups, the LON-Heathrow variants are the *worst* place for "ATOL-style protection" because the UK customer knows exactly what ATOL is — a regulatory protection scheme run by the UK CAA for package holidays. Claiming "ATOL-style" without actual ATOL membership invites a direct ASA complaint. Block the phrase wholesale, but especially in any London/UK-targeted ad group.

**Winner for this ad group:** **None — block all four.** Same regeneration path as NY: remap SKU to LHR (or LON for all-London), supply a from_price, and re-run.

---

### Louisville/SDF — `sku=Louisville, name=SDF` (INVERTED)

- Discount: 0% · From price: **null** · Name length field: 3 (mismatched — actually 10 for "Louisville", 3 for "SDF") · IATA-valid: data is inverted

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | BLOCK | Poor | 1 | "Cheap SDF flights" | SDF as customer-facing keyword |
| 2 | social_proof | BLOCK | Poor | 3 | "Top-rated travel agent", "ATOL-style protection" + name inversion | Multi-blocker |
| 3 | urgency | BLOCK | Poor | 2 | none + name inversion | Broken comprehension |
| 4 | loss_aversion | BLOCK | Poor | 2 | none + name inversion | Same |

This ad group has a **data-model bug on top of the from_price=null bug** which makes it the worst of the chunk. The fields are inverted: `name="SDF"` is treated as the customer-facing destination name, and `sku="Louisville"` is used as the URL/IATA token. Every headline that uses `{name}` says "SDF" where it should say "Louisville", and the URL targets `to=Louisville` which won't resolve.

#### Variant 1 — price_led
- "SDF from $" (10 chars) — nobody searches for "SDF" as the name of a place. SDF is the airport code. The destination is Louisville (and specifically Louisville, KY). This entire ad will see CTR close to zero because the headline name doesn't match the user's search intent.
- "Cheap SDF flights" (17 chars) — banned-adjacent (Cheap [X] flights) plus the code-as-name problem.
- "Louisville flights from $" (25 chars) — finally uses Louisville, but only here because the template happens to insert the SKU rather than the name. The pattern is upside down.
- **Final URL:** `?to=Louisville` — this is using the SKU (which here is the city name) as the IATA code. The destination resolver on flightnetwork.com won't have a code "Louisville"; it expects SDF. **The URL likely 404s or fuzzy-matches.**

#### Variant 2 — social_proof
- "Price guarantee on Louisville" (29 chars) — accidentally correct because the SKU happens to be the city name. But this is by chance, not by design.
- "SDF - 800+ airlines" (19 chars) — uses the code as the headline; meaningless to customers.

#### Variant 3 — urgency
- "Louisville deals updated" (24 chars) — accidentally correct via the inverted SKU.
- "SDF sale ends this week" (23 chars) — meaningless to a non-aviation-nerd customer.

#### Variant 4 — loss_aversion
- "Stop overpaying for SDF" (23 chars) — customer doesn't know what SDF is. Reads as a typo or unrelated acronym.
- "Skip the markup on Louisville" (29 chars) — accidentally correct.

**Winner for this ad group:** **None — block all four.** Fix the data model inversion (`name="Louisville"`, `sku="SDF"`), supply a from_price, and regenerate. As-is this ad group is broken at three layers (data, copy, URL routing) and ships zero impressions.

---

## Non-IATA SKU verdict

### NY — **REMAP to NYC**

- **Reasoning:** The IATA metro code for all New York City airports is **NYC**. Individual airport codes are JFK, LGA, EWR. "NY" is a US state postal abbreviation, not an IATA code, and Flightnetwork's destination resolver almost certainly accepts NYC but may or may not accept NY (the URL `?to=NY` likely fuzzy-matches but routes inconsistently).
- **Customer signal:** "NY" in headlines like "Book NY" or "Skip the markup on NY" is ambiguous (NY = New York state? New York City? The Yankees?). NYC removes the ambiguity at zero character cost. NYC also happens to be how Americans casually refer to the city ("NYC restaurants", "NYC weather").
- **Action:** Remap SKU to NYC. Update URL templating. Regenerate this ad group.

### LON-Heathrow — **REMAP to LHR**

- **Reasoning:** **LHR** is the IATA code for Heathrow specifically. **LON** is the IATA metro code for all five London airports (LHR, LGW, STN, LTN, LCY). The hyphenated form "LON-Heathrow" is not a Google Flights or aviation-industry construct — it's bespoke to this dataset, and it ships visibly into customer-facing headlines as "LON-Heathrow flights from $" which reads like a typo or mis-OCR.
- **Customer signal:** No one searches "LON-Heathrow flights". They search "Heathrow flights", "flights to Heathrow", "London Heathrow flights", or "LHR flights". The dataset is conflating "London (metro)" and "London Heathrow (specific airport)" into a Frankenstein token that satisfies neither.
- **Action:** Choose intent first. If targeting all London airports → SKU = LON, name = "London". If targeting Heathrow specifically → SKU = LHR, name = "London Heathrow" (16 chars, comfortably fits) or "Heathrow" (8 chars). Then regenerate.

### Louisville (currently inverted: `sku=Louisville, name=SDF`) — **REMAP — actually FIX the data inversion**

- **Reasoning:** The real problem isn't the SKU choice, it's the field inversion. `sku` should be the IATA code (SDF), `name` should be the customer-facing destination (Louisville). With those swapped, every downstream template uses the wrong token in the wrong slot.
- **Action:**
  1. Fix data: `sku="SDF"`, `name="Louisville"` (or "Louisville, KY" for disambiguation from Louisville, CO).
  2. Update URL templating to use SKU (SDF) as the destination code.
  3. Validate `name_length` field (currently shows 3, should be 10 for "Louisville" or longer with state).
  4. Regenerate the ad group.

**Recommendation: All three SKUs should be REMAPPED to canonical IATA codes** (NYC, LHR, SDF) and the data-model inversion on Louisville should be fixed. Beyond just these three, add an IATA-validator to the catalog loader that fails the load if any SKU is not a recognised 3-letter IATA code (city or airport), with override only via explicit `iata_override: true` flag. This is a one-time fix that prevents this entire class of bug forever.

---

## Pattern-level fixes (apply to ALL ad groups via patterns.json edits)

The following fixes should be made at the pattern/template level so every future destination benefits, not just this chunk.

### 1. Null-safe price interpolation (CRITICAL)

When `from_price` is null, the current behaviour ships visible `$` and "from " fragments. Required fixes:

- Add a conditional in the headline/description templates: if `from_price` is null, suppress the price token *and* the surrounding scaffolding ("from", "starting at", "Today's fare $") rather than just the number.
- For price_led variant specifically: if `from_price` is null, skip the variant entirely and only emit the other roles. A price-led ad with no price is a contradiction.
- For descriptions that anchor on price, supply a non-price fallback: "London fares compared across 800+ airlines" instead of "London from $".
- **Test:** Add a regression case in `test_ad_copy_english_and_product.py` that asserts no headline or description contains a bare `$` followed by whitespace, period, or end-of-string.

### 2. Banned-phrase scrub on every emission

Add a hard-fail validator that rejects any RSA containing:

- `"Top-rated travel agent"` → replace with `"4.5★ Trustpilot ({review_count} reviews)"` or drop
- `"Cheap {name} flights"` → replace with `"{name} from ${price}"` or `"Fares to {name}"`
- `"Price Drop Alerts Free"` → replace with `"Free price drop alerts"` (sentence case)
- `"ATOL-style protection"` → drop entirely; replace with market-appropriate authority signal (US: "USDOT-licensed", "BBB-accredited"; UK: only use ATOL if actually a member; CA: "TICO-registered" if applicable)
- `"Refund policy, no hassle"` → `"Free 24h cancellation"` (already a real Flightnetwork USP)
- `"Compare fares today"` (CTA H3) → `"Compare 800+ airlines"` (already in social_proof variants, lift to default H3)
- `"Limited inventory, real fares"` → `"Fares update hourly"` or `"Real-time airline inventory"`

### 3. IATA-code suppression in customer-facing headlines

The current pattern emits both `{name}` and `{sku}` headlines (e.g., "LEA flights from $576" alongside "Learmonth flights from $576"). The IATA-code form should be suppressed unless the code is one of a known set of household codes (LAX, JFK, LHR, CDG, NRT, DXB, etc.). Otherwise customers see "SHE flights", "DLC flights", "LEA flights" and either don't understand or skip.

- Maintain an allowlist of customer-recognised IATA codes (~30 globally).
- For all other SKUs, default to name-only headlines.
- Discounted variants should especially never use raw IATA codes — they reduce specificity exactly when you want to maximise it.

### 4. De-templatise across destinations to avoid semantic-similarity penalty

Currently variants 1, 3, and 4 across LEA/DLC/SHE are word-for-word identical except for name and price. Google's similarity detection will dampen serving across multiple ad groups that share too much copy. Pattern-level fix:

- Maintain a pool of 4–5 alternate phrasings per role and rotate by SKU hash. E.g. price_led H3 should rotate between "Compare 800+ airlines", "Real fares from $X", "Lock the lowest fare", "Find $X+ flights".
- Pool size of 4 across 1,000 destinations means each phrasing serves ~250 ad groups — still some overlap but well below the dampening threshold.

### 5. Pin position 1 is wasted on "Flightnetwork"

Pin position 1 on a single-word brand name is a Tier-2 default. Better pins for an OTA:

- H1 pinned: "{name} from ${price}" — keyword + number + value
- H2 pinned: "Flightnetwork" — brand confirmation
- H3 pinned: role-specific CTA ("Claim X% off now" for discount, "Compare 800+ airlines" for price-led)

This re-ordering puts the keyword in the eye-landing position and demotes the brand to position 2, where it functions as trust-confirmation rather than as the first thing the user reads. The First-Three-Words Doctrine demands the keyword/number/place lead, not the brand.

### 6. Discount-led variant: cap % repetition at 6 headlines

Variant 2 for LEA mentions 17% in 11 of 15 headlines. Google's semantic similarity detection will collapse those to one effective asset and penalise Ad Strength. Cap at 5–6 % headlines and fill the remaining slots with proof, urgency, and friction-removal phrases.

### 7. "ATOL-style" and compliance-flag phrasing

In addition to the banned-phrase scrub:

- Add a market-aware authority pool: SE → "F-skatt", "auktoriserad"; US → "USDOT", "IATA", "BBB"; UK → "ATOL" (only if real), "ABTA" (only if real), "CAA-registered"; Global → "IATA-accredited" only.
- Refuse any phrasing of the form "{regulator}-style {claim}" — the word "style" admits the claim is not literal and that's exactly the kind of phrasing that triggers ASA/FTC scrutiny.

### 8. Truncation guards on long destination names

NY ("New York City" = 13 chars) and similar long names cause headlines like "Today's New York City fare $" to crowd to 28 chars before the price even loads. When a name is >10 chars:

- Drop the trailing price token from urgency headlines and rely on social_proof / price_led variants to carry the price
- Provide a short-form name field on the catalog (e.g., "NYC" as short-form, "New York City" as long-form) so the template can pick the right token by character budget
- Reject any description that contains a sentence ending mid-preposition ("from in minutes", "save the difference on every", "free 24h" followed by nothing)

### 9. Add a stop-slop post-pass

Per the SKILL.md final safety net: every emitted RSA should run through stop-slop Part 1 hard bans before commit. The chunk shows multiple symptoms (em-dash use, mid-sentence Title Case, naked punctuation) that a stop-slop pass would catch automatically.

### 10. Read-aloud differentiation harness

The deepest issue across the chunk is angle parity: 22 of 25 variants could be run unchanged by Expedia, Kayak, Kiwi, or any other OTA. The fix isn't a banned-phrase list — it's a structural one. Pick one Flightnetwork-specific edge and lead with it across all variants:

- "Pay airline price, not the markup" (loss_aversion variant 5 already does this — promote to a default)
- "Real-time fares from 800+ airlines" (specific and provable)
- "Free 24h cancellation" (genuine USP vs most OTAs)
- "Price-match guarantee" (if true and disclosable)

Whichever one is the strongest single Flightnetwork moat — lead with it in the H4 of every variant, regardless of role. That gives angle consistency across the account while letting role-specific levers handle H3 and the descriptions.
