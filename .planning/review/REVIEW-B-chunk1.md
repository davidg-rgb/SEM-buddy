# Reviewer B — Chunk 1 (PRN, RBA, PKC, CHQ, CHS, OOL)

## Summary

- **Total variants reviewed:** 30 RSAs across 6 ad groups (5 variants each — none of these ad groups had `discount_pct == 0`, so all 5 lever slots are populated)
- **Verdict counts:**
  - PASS: 4 (PRN-v3, CHQ-v3, OOL-v3, CHS-v3 — social_proof variants are the strongest pattern, though they still need work)
  - FLAG: 21 (most everything else: generic, mechanical, banned-phrase hits, fake-scarcity, weak CTAs)
  - BLOCK: 5 (all of PKC — name-length pattern collapses to word fragments; plus CHS-v5/OOL-v5 description truncation mid-sentence)

### Cross-cutting wins
- The 800+ airlines / 1.5M travelers / 4.5★ Trustpilot / IATA-accredited stack is genuinely strong proof. The social_proof variant (v3) is the closest thing to Tier-1 in every ad group.
- Descriptions are mostly within character limits and self-contained (Google can show any two and they still read).
- Discount_led variants do put the literal % in both H1+ headlines AND descriptions — contract is honored.
- Most price_led variants front-load the destination + number in H4–H7, which is correct First-Three-Words doctrine.

### Cross-cutting issues
1. **Banned phrase: "Top-rated travel agent"** appears in EVERY single v3 (social_proof) across all 6 ad groups. "Top-rated" is explicitly in the skill's English banned list ("Without a source, empty"). 6 instances. Pattern-level fix required.
2. **Compliance risk: "ATOL-style protection"** appears in every v3. ATOL is a UK CAA bond scheme; Flightnetwork is a Canadian/US OTA. "ATOL-style" is hand-wave weasel ("looks like ATOL but isn't") — this is a Konsumentverket / ASA / FTC trap. Remove immediately.
3. **Fake scarcity: "Today only: 22%/25%/34%/41%/42% off"** appears in every v2 with no real deadline. Skill explicitly bans fake scarcity ("Customers see through it; Google penalises misleading ads").
4. **Generic pinned H3: "Compare fares today"** appears as the pinned position-3 CTA on every v1. This is the most ignorable CTA possible — no friction removal, no specificity. Compare-as-CTA is dead in OTA. Should be price- or speed-anchored.
5. **Broken word order: "Price Drop Alerts Free"** appears in every v1. Reads as a translation artifact. Should be "Free Price Drop Alerts".
6. **Awkward syntax: "Member, IATA accredited"** appears in every v3. Reads like a JSON field, not an ad. Should be "IATA-accredited" (full stop) or "IATA member since [year]".
7. **The "Skip the markup" / "Pay airline price" angle in v5** is conceptually strong (a real differentiator vs. competitors who don't pitch direct-to-airline), but the execution is generic and could be run by any OTA. Needs sharper specificity.
8. **PKC pattern collapse:** when destination name = 42 chars, the pattern truncates to one-word fragments ("Flights", "Compare", "Limited", "Lowest") that carry zero information. PKC v4 and v5 are unshippable as written. This is a pattern-level bug.
9. **Hyphen-as-em-dash:** the recurring " - " separator (e.g., "Pristina flights -22%", "No hidden fees - ever") is fine for Google rendering but the underlying patterns should use commas where the dash isn't doing structural work — half of these dashes are pure visual filler.
10. **Truncation mid-sentence:** CHS-v5 D4 and OOL-v5 D4 both end "save the difference on every" — the word "leg" got chopped to hit 90 chars. Mid-sentence cut is per the skill worse than a different sentence.
11. **No "free 24h cancellation" on most v5 descriptions.** v5 is the strongest competitive angle (anti-agency-markup) but it abandons the strongest risk-reversal asset.
12. **Variant order vs. naming inconsistency:** the JSON tags v3 as social_proof, v4 as urgency, v5 as loss_aversion — but the urgency variant (v4) leans heavily on fake-scarcity tropes ("Final seats", "Today only", "ends this week") which read as manipulation, not real urgency. Real urgency for an OTA = "fares update hourly" — and that line is only present once per v4.

---

## Per-Ad-Group Reviews

### Pristina (PRN)
- Discount: 22% · From price: $580 · Name length: 8 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7/10 | "Price Drop Alerts Free" (broken syntax, slop tell) | Solid price anchor, weak pinned CTA |
| 2 | discount_led | FLAG | Good | 6/10 | "Today only: 22% off" (fake scarcity) | % contract honored; scarcity is fake |
| 3 | social_proof | PASS (with edits) | Excellent | 8/10 | "Top-rated travel agent", "ATOL-style" | Strongest variant — fix the two banned items |
| 4 | urgency | FLAG | Good | 6/10 | "Final seats" (fake scarcity unless verified) | Real urgency hook ("fares update hourly") is buried in D1 |
| 5 | loss_aversion | FLAG | Good | 6/10 | None banned, but generic | "Skip the markup" is good; rest is filler |

**Per-variant detail:**

#### Variant 1 — price_led
- H1/H2/H3 first-three-words audit: H1 "Flightnetwork" (brand-fine, pinned), H2 "Pristina" (keyword-fine, pinned), H3 "Compare fares today" (generic verb — "compare" doesn't sell, doesn't remove friction). H3 fails the First-Three-Words doctrine — "Compare" is the wrong verb for a transactional moment.
- Banned phrases: "Price Drop Alerts Free" — broken English word order; reads like an AI translation. Not in the banned list per se but fails read-aloud test.
- Levers actually pulled: Specificity (price), friction-removal (24/7, no hidden fees). Missing: outcome framing.
- Read-aloud test: Five headlines say "Pristina from $580" in different syntax ("Pristina from $580", "Flights to Pristina $580", "$580 flights to Pristina", "PRN flights from $580", "Book Pristina from $580"). Google will flag this as semantic redundancy and drop strength. Three of these five would be enough.
- Differentiation: Any OTA could run identical copy. No mention of Trustpilot, IATA, 24h free cancel anywhere in headlines.
- Specific rewrite suggestions:
  - H3 "Compare fares today" (19) → **"Lock $580 in 60 seconds"** (22) — names price + speed
  - "Price Drop Alerts Free" (22) → **"Free price drop alerts"** (22) — fix word order
  - Cut one of the redundant "$580 to Pristina" variants; replace with **"Free 24h cancellation"** (20)

#### Variant 2 — discount_led
- H1/H2/H3 audit: H3 "Claim 22% off now" (18) — verb-led, number-led, urgency-led. This is good.
- Banned phrases: "Today only: 22% off" — explicit fake scarcity, banned by the skill ("Never fake countdowns"). "Was full price, now -22%" — "full price" is an undefined anchor, slight compliance concern (FTC requires reference price be a bona fide previously offered price for >30 days).
- Discount-mention contract: Confirmed — % appears in headlines 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 AND descriptions 1, 2, 3, 4. Honored.
- Levers pulled: Loss aversion (discount framing), scarcity (mostly fake), specificity (price + %). Good lever stack but scarcity is the weak link.
- Read-aloud test: Same problem as v1 — six headlines say "22% off Pristina" in different syntactic packages. Not enough actual variation.
- Differentiation: "Save 22% on Pristina" is a perfectly fine OTA line, but identical to what Kiwi.com, Skyscanner, Kayak would write.
- Specific rewrite suggestions:
  - "Today only: 22% off" (19) → either remove entirely, OR if the discount has a real Sunday-night deadline, use **"22% off ends Sunday 11pm"** (24) with the actual date pulled from the catalog
  - "Was full price, now -22%" (24) → **"Was $744, now $580"** (16) — give the math, not the abstraction
  - "Deal: 22% off Pristina" (21) → **"22% off, only on FN"** (19) — adds differentiation

#### Variant 3 — social_proof
- H1/H2/H3 audit: H3 "Compare 800+ airlines" (21) — number + verb + specificity. This is the strongest pinned H3 in the entire chunk.
- Banned phrases:
  - **"Top-rated travel agent"** (22) — explicit ban. Without a source it's empty.
  - **"ATOL-style protection"** (21) — misleading compliance. ATOL is UK CAA. "Style" is weasel.
- Levers pulled: Social proof (1.5M, 800+, 4.5★, IATA), authority (IATA, accreditation), risk reversal (refund policy, 24/7). Excellent lever stack.
- Read-aloud test: This is the only variant that sounds like a human OTA wrote it. The proof points are real and earned.
- Differentiation: 4.5★ Trustpilot and IATA-accredited are honest, defensible differentiators competitors don't all share. Real edge.
- Specific rewrite suggestions:
  - "Top-rated travel agent" → **"4.5★ on Trustpilot"** (18) — name the source
  - "ATOL-style protection" → **"Free 24h cancellation"** (21) — cite a real benefit
  - "Member, IATA accredited" (22) → **"IATA-accredited agent"** (21) — natural English

#### Variant 4 — urgency
- H1/H2/H3 audit: H3 "Book before seats sell" (22) — verb-led, friction-led. Acceptable but vague (what seats? whose seats?).
- Banned phrases: None in the literal banned list, but "Final seats: Pristina $580", "Limited Pristina fares left", and "Pristina sale ends this week" are all fake-scarcity flavors unless a real deadline exists.
- Levers pulled: Scarcity, urgency, friction-removal. The lever stack is technically right but the execution feels manipulative.
- Read-aloud test: "Pristina deals end soon" is what every dropshipping store says. The one earned line — **"PRN deals updated hourly"** (24) — is the actual differentiator (real-time OTA inventory feeds). It should be H4, not H11.
- Differentiation: Same problem — any OTA runs this.
- Specific rewrite suggestions:
  - Promote **"PRN deals updated hourly"** to H4
  - "Pristina sale ends this week" (27) → **"Fares update every hour"** (23) — real-time = real urgency
  - Drop "Final seats: Pristina $580" — unfalsifiable scarcity claim

#### Variant 5 — loss_aversion
- H1/H2/H3 audit: H3 "See real flight prices" (22) — contrarian, decent. Implies competitors show fake prices (mild swipe — good for OTA category).
- Banned phrases: None banned, but "Lowest Pristina fare today" is borderline-superlative (ASA-style risk in regulated markets).
- Levers pulled: Loss aversion (stop overpaying, skip markup, no hidden fees), specificity (price). Good lever stack.
- Read-aloud test: "Stop overpaying for Pristina" + "Skip the markup on PRN" + "Pay airline price, not more" is a coherent anti-agency-markup narrative. This is conceptually the most interesting variant.
- Differentiation: "Skip the markup" is a real angle — most OTAs DO add a markup. Flightnetwork claiming to skip it is a legitimate fight to pick. But the execution doesn't name a competitor or a number.
- Specific rewrite suggestions:
  - "Don't pay full Pristina fare" (27) → **"Save $40 vs. Expedia avg"** (25) — name the rival
  - "Lowest Pristina fare today" (26) → **"Avg saving $40 vs. agents"** (25) — name the saving
  - Add a description line citing the saving math

**Winner for this ad group:** **Variant 3 (social_proof)** — earned proof points, strongest lever stack, only variant a senior copywriter would defend on the merits. But it must lose "Top-rated travel agent" and "ATOL-style protection" before shipping.

---

### Rabat (RBA)
- Discount: 25% · From price: $88 · Name length: 5 chars

The Rabat ad group is structurally identical to Pristina with the destination name and price/discount swapped. All five variants exhibit the same patterns and the same flaws — same banned phrases, same fake scarcity, same generic CTAs.

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7/10 | "Price Drop Alerts Free" | $88 is a strong number — needs to be louder |
| 2 | discount_led | FLAG | Good | 6/10 | "Today only: 25% off" | Same fake scarcity |
| 3 | social_proof | PASS (with edits) | Excellent | 8/10 | "Top-rated travel agent", "ATOL-style" | Strongest variant |
| 4 | urgency | FLAG | Good | 6/10 | "Final seats" | Same as PRN-v4 |
| 5 | loss_aversion | FLAG | Good | 6/10 | None | Skip-markup angle still good |

**Per-variant detail:**

#### Variant 1 — price_led
- First-three-words audit: H3 "Compare fares today" — same generic failure.
- $88 is a remarkable price point and the copy underuses it. "Rabat from $88" appears in 5 headlines but never with a comparative anchor ("Cheaper than Marrakech!", "Avg flight $245 — you pay $88").
- Specific rewrite: H3 → **"$88 in 60 seconds"** (16). Frees pin slot for urgency.

#### Variant 2 — discount_led
- Same fake scarcity problems.
- Discount contract honored (% in 11 headlines + 4 descs).
- "25% off, $88+" (15) — short and tight, works.
- "Was full price, now -25%" — same FTC concern.

#### Variant 3 — social_proof
- Same two banned phrases.
- D2 "Price-match guarantee on Rabat. 4.5★ Trustpilot, 24/7 support, free 24h cancellation" — this is the single best description in the whole chunk. Three real proof points, ends on risk reversal.

#### Variant 4 — urgency
- Same patterns. The $88 price actually creates real urgency that the copy doesn't lean into. At $88 Rabat is the cheapest destination in the chunk — that itself is the headline.
- Specific rewrite: H4 "Rabat deals end soon" → **"Rabat under $100 today"** (21).

#### Variant 5 — loss_aversion
- At $88, "Don't pay full Rabat fare" is more credible than at $589 (Chania). The anti-markup story lands harder on cheap fares.

**Winner for this ad group:** **Variant 3 (social_proof)** — same logic as PRN. Same two fixes required.

---

### Petropavlovsk-Kamchats, Russian Federation (PKC)
- Discount: 22% · From price: $224 · Name length: 42 chars

**This ad group is largely unshippable in its current form.** The pattern-level handling of 42-char destination names breaks down catastrophically. Headlines collapse to one-word fragments with zero information value, and the path1 "petropavlovskka" is a mangled URL display.

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | BLOCK | Poor | 3/10 | none | "Flights" / "Compare" alone as headlines — unshippable |
| 2 | discount_led | BLOCK | Poor | 4/10 | "Today only" + truncated | Acceptable on chars, broken on info |
| 3 | social_proof | FLAG | Good | 6/10 | "Top-rated", "ATOL-style" | Best variant only because proof points don't need the destination name |
| 4 | urgency | BLOCK | Poor | 2/10 | none | "Limited", "Last-minute", "Today's", "Final seats" — pure fragments |
| 5 | loss_aversion | BLOCK | Poor | 2/10 | none | "Stop overpaying", "Don't pay full", "Avoid Petropavlovsk-Kamchats", "Lowest" — fragments |

**Per-variant detail:**

#### Variant 1 — price_led
- First-three-words audit: H4 = "Flights" (7 chars). H5 = "$224 flights" (12). H8 = "Compare" (7). These are placeholder strings, not headlines.
- The pattern is doing `"Flights to {name} ${price}"` and when name = 42 chars, the templater silently drops the name. Result: useless.
- Descriptions are also weak: D1 "Petropavlovsk-Kamchats, Russian Federation from $224" (53) — the literal name eats the whole description. No CTA, no lever.
- Specific rewrite suggestions:
  - Use IATA fallback: **"PKC from $224"** (14), **"Flights to PKC $224"** (19), **"Book PKC from $224"** (18) — IATA codes are searched and recognized
  - Use a city shorthand: **"Kamchatka from $224"** (19) — the destination is colloquially "Kamchatka" in English travel content
  - D1 → **"PKC (Petropavlovsk) from $224. 800+ airlines, free 24h cancellation"** (66) — parens shorten the long name

#### Variant 2 — discount_led
- "Claim 22% off now" (18), "22% off" (8), "Save 22%" (9), "22% off, $224+" (15) — these work because they're focused on the number.
- But the destination is missing from 10 of 15 headlines. Google's algorithm needs the keyword in headlines for Quality Score. Quality Score will be poor.
- Discount contract: technically honored (% appears) but the destination context evaporates.

#### Variant 3 — social_proof
- This variant survives because the proof points (800+, 1.5M, IATA, Trustpilot) don't depend on the destination name.
- Same two banned phrases.
- Descriptions truncated mid-thought (D3 ends "Compare every Petropavlovsk-Kamchats, Russian Federation fare", D4 ends "fares from $224, refund") — the literal name eats the budget. Need to use "Kamchatka" or "PKC" shorthand.

#### Variant 4 — urgency
- "Limited" (7), "Last-minute" (11), "Today's" (7), "Final seats" (11), "Book before seats sell" (22) — five headlines that say literally nothing. The reader sees "Limited" and asks "Limited what?"
- Block. Must not ship.

#### Variant 5 — loss_aversion
- "Stop overpaying" (15), "Don't pay full" (14), "Avoid Petropavlovsk-Kamchats" (28 — the only one that includes the name and it's an anti-CTA: "Avoid this destination"), "Book before" (11), "No hidden" (9), "Lowest" (6).
- "Avoid Petropavlovsk-Kamchats" is **active harm** — it tells the searcher to avoid the place they're searching for. Block.

**Winner for this ad group:** None. Variant 3 (social_proof) is the only one shippable, and only after the banned-phrase fixes plus replacing "Petropavlovsk-Kamchats, Russian Federation" with "Kamchatka" or "PKC" in descriptions. PKC needs a separate name-length policy at the pattern level (see Pattern-level fixes below).

---

### Chania (CHQ)
- Discount: 42% · From price: $589 · Name length: 6 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7/10 | "Price Drop Alerts Free" | $589 is a high anchor — discount should lead |
| 2 | discount_led | FLAG (strong) | Excellent | 8/10 | "Today only: 42% off" | 42% is the loudest number in the chunk |
| 3 | social_proof | PASS (with edits) | Excellent | 8/10 | "Top-rated", "ATOL-style" | Strong |
| 4 | urgency | FLAG | Good | 6/10 | "Final seats" | Same fake-scarcity issue |
| 5 | loss_aversion | FLAG | Good | 6/10 | None | At $589, "Stop overpaying" is credible |

**Per-variant detail:**

#### Variant 1 — price_led
- Same template, but $589 is a high anchor and the price-led story works less well at this price point than at $88 Rabat. A 42% discount is the bigger story here.
- Read-aloud: "Cheap Chania flights" at $589 reads as a lie. Chania at $589 is "Mediterranean island for under $600", not "cheap".
- Specific rewrite: H8 "Cheap Chania flights" (20) → **"Chania under $600"** (17) — same meaning, more honest.

#### Variant 2 — discount_led
- This is the strongest discount_led in the chunk. 42% is genuinely big and the headlines land.
- "42% off Chania flights" (22), "Save 42% on Chania" (18), "Chania: save 42% now" (20) — all clear, all specific.
- But: "Today only: 42% off" is still fake scarcity, and "Was full price, now -42%" is FTC-risky.
- Specific rewrite:
  - If 42% has a real end date (likely — it's a high-discount flag), put it: **"42% off ends Sunday"** (19)
  - "Was full price, now -42%" → **"Was $1,015, now $589"** (20) — show the math

#### Variant 3 — social_proof
- Same two banned phrases.
- D2 "Price-match guarantee on Chania. 4.5★ Trustpilot, 24/7 support, free 24h cancellation" (89) — strong.
- D3 "Trusted by 1.5M travelers. Compare every Chania fare from 800+ airlines in one search" (87) — strong.

#### Variant 4 — urgency
- Same fake-scarcity issues. The 42% discount creates real urgency the urgency variant doesn't borrow.
- Variant 2 (discount_led) and Variant 4 (urgency) overlap heavily. They should be more differentiated — one should be "the deal", the other should be "the inventory".

#### Variant 5 — loss_aversion
- "Stop overpaying for Chania" at $589 is credible. The math (42% discount = $415 saving) supports the claim.
- Add the saving math: **"Save $426 on Chania"** (18).

**Winner for this ad group:** **Variant 2 (discount_led)** — at 42% off this is the strongest angle in the chunk, and it executes the discount contract cleanly. Replace fake scarcity with real deadline.

---

### Charleston (CHS)
- Discount: 41% · From price: $254 · Name length: 10 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7/10 | "Price Drop Alerts Free" | |
| 2 | discount_led | FLAG | Excellent | 8/10 | "Today only: 41% off" | 41% + $254 is a strong combo |
| 3 | social_proof | PASS (with edits) | Excellent | 8/10 | "Top-rated", "ATOL-style" | |
| 4 | urgency | FLAG | Good | 6/10 | "Final seats" | |
| 5 | loss_aversion | BLOCK | Good | 6/10 | None — but D4 is truncated | D4 ends "save the difference on every" — missing "leg" |

**Per-variant detail:**

#### Variant 1 — price_led
- Standard pattern, same problems. Charleston is a US domestic destination — the Flightnetwork "compare 800+ airlines" lever is overkill (most US domestic routes are dominated by 6–8 carriers). The lever stack is wrong for the vertical here.
- Specific rewrite: "Cheap Charleston flights" (24) → **"Charleston nonstop $254"** (23) — domestic US searchers care about nonstop.

#### Variant 2 — discount_led
- 41% is loud. "41% off Charleston flights" (26) — strong.
- Same fake-scarcity problem.

#### Variant 3 — social_proof
- Same two banned phrases.
- D2 "Price-match guarantee on Charleston. 4.5★ Trustpilot, 24/7 support, free 24h cancellation" — count: 90 chars exact, right at the limit.

#### Variant 4 — urgency
- "Last-minute Charleston flights" (30) — exactly at the 30-char limit. Risky margin.
- "Charleston sale ends this week" (30) — same.
- Same fake-scarcity issue.

#### Variant 5 — loss_aversion
- **D4: "Don't pay full fare to Charleston. Compare 800+ airlines, save the difference on every"** — cuts off. The Chania version of the same description ends "...save the difference on every leg" (88 chars including the leg). For Charleston (10 chars vs Chania's 6), the line breaks the 90-char limit and the generator chopped "leg" off rather than rewriting. BLOCK until fixed.
- Specific rewrite of D4: **"Don't pay full Charleston fare. Compare 800+ airlines, save on every leg."** (74) — shorter, complete sentence.

**Winner for this ad group:** **Variant 3 (social_proof)** — but a strong case for Variant 2 (discount_led) at 41%. Pick v3 for the proof stack and the cleaner read.

---

### Gold Coast (OOL)
- Discount: 34% · From price: $317 · Name length: 10 chars

| Variant | Role | Verdict | Ad Strength | Specificity | Banned-phrase hits | Notes |
|---|---|---|---|---|---|---|
| 1 | price_led | FLAG | Good | 7/10 | "Price Drop Alerts Free" | "Gold Coast" reads natively |
| 2 | discount_led | FLAG | Good | 7/10 | "Today only: 34% off" | |
| 3 | social_proof | PASS (with edits) | Excellent | 8/10 | "Top-rated", "ATOL-style" | |
| 4 | urgency | FLAG | Good | 6/10 | "Final seats" | |
| 5 | loss_aversion | BLOCK | Good | 6/10 | None — but D4 truncated | Same "every" → missing "leg" issue as CHS |

**Per-variant detail:**

#### Variant 1 — price_led
- Path display: `path1="gold"` `path2="coast"` — clean and readable. Best path handling in the chunk.
- "Gold Coast" is a 10-char two-word destination, mostly Australian intent. The Flightnetwork USP of 800+ airlines is genuinely useful here (limited carriers fly OOL).
- Same generic H3 problem.

#### Variant 2 — discount_led
- Same as other discount_led — % in 11 headlines, fake scarcity in two.

#### Variant 3 — social_proof
- Same two banned phrases.
- D2 hits 90 chars: "Price-match guarantee on Gold Coast. 4.5★ Trustpilot, 24/7 support, free 24h cancellation" — at the limit.

#### Variant 4 — urgency
- Five headlines at or near 30 chars: "Last-minute Gold Coast flights" (30), "Gold Coast sale ends this week" (30), "Book Gold Coast flights today" (29), "Limited Gold Coast fares left" (29), "Today's Gold Coast fare $317" (28). Length spread is too narrow — the skill recommends mixing short and long.

#### Variant 5 — loss_aversion
- D4: "Don't pay full fare to Gold Coast. Compare 800+ airlines, save the difference on every" — same truncation as CHS-v5. BLOCK.
- Specific rewrite: **"Don't pay full Gold Coast fare. 800+ airlines, save on every leg."** (66) — complete sentence.

**Winner for this ad group:** **Variant 3 (social_proof)** — same pattern.

---

## Pattern-level fixes (apply to ALL ad groups via patterns.json edits)

These are systemic issues that should be fixed in the templates, not in 30 individual RSAs.

### Banned phrases — remove globally
1. **"Top-rated travel agent"** — replace with **"4.5★ on Trustpilot"** (18) or **"$X.X★ on Trustpilot"** with real review count. Banned per skill.
2. **"ATOL-style protection"** — remove. ATOL is UK CAA, misleading for FN. Replace with **"Free 24h cancellation"** or **"Price-match guarantee"** — real benefits FN actually offers.
3. **"Member, IATA accredited"** — replace with **"IATA-accredited agent"** (21) — natural English word order.
4. **"Price Drop Alerts Free"** — replace with **"Free price drop alerts"** (22) — natural word order.

### Compliance and fake-scarcity — rebuild the urgency lever
5. **"Today only: X% off"** — remove. The skill bans fake scarcity outright. Either pipe the real promotion deadline from the catalog (`promotion.end_date`) and render **"X% off ends [Day Mon DD]"**, or drop the line.
6. **"Was full price, now -X%"** — replace with **"Was $Y, now $Z"** using calculated `Y = from_price / (1 - discount_pct)`. Names the math, satisfies FTC, more credible.
7. **"Final seats: [Dest] $X"** — remove unless real inventory count is available. Otherwise it's unfalsifiable and Google will lower Quality Score over time.
8. **"Today only", "Final seats", "Last-minute"** — these three patterns collectively make v4 (urgency) the weakest variant. The real urgency angle for an OTA is the live-pricing feed: **"Fares update every hour"**, **"Real-time inventory"**, **"Live airline pricing"**. That's a competitive moat. Use it.

### Generic CTAs — promote the strongest CTA to pinned H3
9. **"Compare fares today"** as pinned H3 across all v1 — replace with **"Lock $X in 60 seconds"** (price + speed + friction) using the from_price. Far stronger pinned CTA. Counter-rule: if "Lock $X" reads as a financial term in regulated markets, fall back to **"Book in 60 seconds"** (19).

### Name-length policy (PKC and any destination >25 chars)
10. **Long destination names (>25 chars)** need a fallback policy. Today the pattern silently drops the name and leaves fragments ("Flights", "Limited", "Lowest"). Three fixes, in order of preference:
    - **(a)** Pull a `short_name` field from the catalog ("Kamchatka" for PKC, "DC" for Washington, "NYC" for New York). Use `short_name` whenever full name exceeds X chars.
    - **(b)** Fall back to IATA code: "PKC flights from $224", "PKC from $224 only", "PKC fares update hourly". IATA codes are universally searched and 3 chars.
    - **(c)** Use parenthetical shortform in descriptions: **"PKC (Petropavlovsk) from $224"** — fits.

### Description truncation (CHS-v5 D4, OOL-v5 D4)
11. **The "save the difference on every leg" pattern** breaks 90 chars when destination = 10+ chars. Rewrite the template:
    - Before: `"Don't pay full fare to {dest}. Compare 800+ airlines, save the difference on every leg"` — breaks for 8+ char destinations.
    - After: `"Don't pay full {dest} fare. 800+ airlines, save on every leg."` (~65 chars + destination) — fits all destinations.

### Headline redundancy (price_led variants)
12. **v1 has 5 headlines saying "[dest] from $X" with different syntax.** Google's RSA optimizer treats these as semantically identical and lowers Ad Strength. Cut to 2 variants, fill the freed slots with proof-point headlines (Trustpilot, 24h cancel, 800+ airlines) so v1 isn't proof-point-empty.

### Path handling (PKC)
13. `path1="petropavlovskka"` is a broken word that no user will associate with the destination. Path policy for long names: use the IATA code as path1 (`pkc`) and a region descriptor as path2 (`russia` or `kamchatka`).

### Length spread (urgency variants)
14. **OOL-v4 has five headlines at 28–30 chars and none under 20.** Google's "Excellent" Ad Strength needs length spread (8–15 short, 28–30 long). Force at least 3 short headlines into v4: **"Live fares"** (10), **"$317 now"** (8), **"Last seats"** (10).

### Risk-reversal under-use in v5
15. **v5 (loss_aversion) drops "free 24h cancellation"** in favor of "skip the markup" — but the strongest defense against "what if I'm wrong?" loss aversion IS free cancellation. Add **"Free 24h cancellation"** to v5 descriptions.

### Lever overlap between v2 and v4
16. **discount_led (v2) and urgency (v4)** overlap on scarcity. They should be more differentiated. v2 = "the deal" (price + saving). v4 = "the inventory" (live fares, hourly updates, real-time). Currently both lean on fake-scarcity scaffolding.

### Final compliance scan
17. **"Top-rated", "Best", "Lowest [dest] fare today"** — all soft superlatives that ASA / FTC / Konsumentverket flag without substantiation. Either prove ("$X average saving across last 30 days") or drop.

---

End of review. The strongest ad in this chunk is **PRN/RBA/CHQ/CHS/OOL Variant 3 (social_proof)** once "Top-rated travel agent" and "ATOL-style protection" are removed and "Member, IATA accredited" is fixed to "IATA-accredited agent". PKC needs a name-length policy at the pattern level before any of its variants can ship.
