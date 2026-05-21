# Reviewer A — 10 Published RSAs (Campaign 23860402014)

## Summary

- **0 PASS / 0 FLAG / 10 BLOCK** (out of 10)
- Every single ad is a hard BLOCK. There is no version of "ship and iterate" here — these ads actively damage the Flightnetwork brand and waste auction budget on click-repellent copy. They must be replaced before they accrue more impressions.

### Cross-cutting issues found

- **Wrong vertical entirely.** Every ad reads like a home-services template ("local expert", "free consultation", "free quote", "Call .", "10 years of experience", "Certified", "Fast & Reliable"). Flightnetwork is an OTA. Customers searching for flights to Bariloche do not want a quote, a consultation, or a "local expert." They want a fare.
- **Banned phrases everywhere.** "Get a Free Quote", "Over 100 Happy Customers", "100 Years Experience", "Fast & Reliable", "Certified", "Professional [X]", "We offer", "Contact us today" — these are explicitly enumerated in the skill's English banned-phrase table.
- **Factual misrepresentations.** "100 Years Experience" is provably false (Flightnetwork was founded in 1997). "Over 100 Happy Customers" understates the truth by four orders of magnitude (1.5M+ travelers per year). The real proof points — 800+ airlines, IATA accreditation, 4.5★ Trustpilot — appear nowhere.
- **Truncation artifacts in headlines and descriptions.** "Petropavlovsk-kamchats,", "Pro San andres island,", "Certified San carlos de", "Fast & Reliable Santa cruz de", "Best Jerez de la frontera in" — these end mid-word with trailing commas, prepositions, or hyphens. Each one is a Google Ads disapproval risk and a confidence-destroying SERP appearance.
- **Broken description templates.** "We offer [city] in with 10 years of experience." The word "in" with nothing after it is a fill-in failure where a service/category should have been inserted. "Call ." with a phantom phone number (just a period after "Call") is the same bug. "We help you quickly & proly" (Petropavlovsk) — "proly" is a literal string truncation of "professionally".
- **No real CTA.** "Call Us" with no number. "Get a Free Quote" — Flightnetwork doesn't give quotes; users compare and book online. "Book online today" is the closest to legitimate, but it's buried in description 4 and competes with five other false CTAs.
- **Case mangling.** Headlines and descriptions show the destination as lowercase mid-sentence: "Pro West palm beach (florida)", "san carlos de bariloche", "santiago de compostela". The original casing was destroyed during template fill. A senior copywriter would never ship this.
- **Wrong-pronoun/identity framing.** "Your local [destination] expert" is the home-services template. Flightnetwork is not "local" to Petropavlovsk-Kamchatsky or San Andres Island. It's a global OTA. The framing is nonsensical.
- **Stop-slop hard bans triggered.** Em-dash → hyphen substitution ("Flightnetwork - local..."), punctuation orphans ("Call ."), and pair-clichés ("Fast & Reliable", "quickly and professionally"). These trip the defense-in-depth pass.
- **No specificity tax paid.** Not a single named airline, named route price, named airport code (e.g., PKC, ADZ exist as data but never surface), departure-city pairing, or seasonal hook. The skill's specificity ladder demands a number, a place, a year, or a count in every headline — these ads contain a destination string and that's it.
- **Identical structure across all 10 ads.** Same 15 headline slots, same 4 description slots, same broken template. The only thing that varies is the destination string. Google's Ad Strength algorithm sees this as low-variety low-quality fleet copy.

### Highest-priority fixes

1. **Kill all 10 ads immediately.** Pause campaign 23860402014 if not already, or push replacements within 24 hours. Do not let "100 Years Experience" and "Over 100 Happy Customers" continue serving against a Trustpilot 4.5★ / 1.5M+ traveler brand.
2. **Rebuild from the OTA vertical playbook**, not the home-services one. Levers: price specificity ("From $499 to PKC"), social proof ("1.5M+ travelers/year", "Trustpilot 4.5★", "800+ airlines compared"), risk reversal ("24h free cancellation", "no hidden fees"), authority ("IATA-accredited since 1997"), urgency only when real ("Fares update hourly").
3. **Fix the truncation pipeline.** The template builder is feeding 30-char-capped destination strings into 30-char headline slots that already contain prefix words ("Pro ", "Book ", "Certified ", "Best "). This produces guaranteed truncation. Either (a) drop prefix-word headlines for long destinations, or (b) substitute short city codes (IATA) when the full name overflows.
4. **Re-push with 3–5 distinct RSA variants per ad group** (the new generator standard): price_led, discount_led (when applicable), social_proof, urgency, loss_aversion. Single-RSA-per-ad-group is dead.

---

## Per-Ad Verdicts

### Ad 1 — Petropavlovsk-Kamchats, Russian Federation (PKC)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor. Despite filling 15 headlines and 4 descriptions, the semantic-similarity penalty will dominate ("Pro Petropavlovsk-kamchats,", "Best Petropavlovsk-kamchats,", "Book Petropavlovsk-kamchats,", "Petropavlovsk-kamchats," are functionally one headline with prefix swaps). Truncation will likely trigger disapprovals.
- **Banned-phrase hits:** "Get a Free Quote", "Over 100 Happy Customers", "100 Years Experience", "Fast & Reliable", "Certified", "Call Us", "Free Quote & Advice", "Contact us today", "Professional [X] at competitive prices", "We offer", "We help you quickly", "competitive prices". Eleven distinct banned items in one ad.
- **First-Three-Words audit:** H1 "Flightnetwork" — brand only (passable for pos 1). H2 "Petropavlovsk-Kamchats," — keyword present but mid-word truncated with orphaned comma; fails the read-aloud test. H3 not pinned but next significant headline "Pro Petropavlovsk-kamchats," opens with the meaningless "Pro" prefix and breaks mid-word again. None of H1–H3 front-load a number, verb, pain, or genuine offer.
- **Specificity score:** 1/10. The only specifics are "From $499" (which is a generic floor, not tied to PKC — see the same string on every ad) and the destination name itself. No airline, no flight time, no seasonal hook, no proof point.
- **OTA-vertical fit:** Zero. "Local Petropavlovsk-Kamchatsky expert" reads as either a delusional brag or a literal lie. "Free consultation" and "free quote" are not OTA value props.
- **Truncation/typo issues:** "Petropavlovsk-Kamchats," (trailing comma orphan, mid-word cut), "Pro Petropavlovsk-kamchats,", "Book Petropavlovsk-kamchats,", "Best Petropavlovsk-kamchats,", "Certified" (orphan word, fragment headline with no noun), "Cheap Flights to" (dangling preposition — to where?), "we help you quickly & proly" ("proly" is truncated "professionally"), "Contact us a" (truncated "for a"). Plus orphaned "Call ." in description 2.
- **Pre-flight checklist failures:** 1 (language fit fails on truncations), 2 (specificity — no real numbers), 3 (banned phrases everywhere), 4 (stop-slop: pair-clichés, em-dash sub, "Call ." orphan), 5 (first-three-words: H2 broken), 6 (lever count — zero genuine levers), 7 (vertical fit — wrong vertical), 8 (voice — no brand voice), 9 (differentiation — none), 10 (read-aloud — fails immediately), 11 (click test — would be skipped), 12 (compliance — "100 years" is false advertising risk). Fails 12 of 12.
- **Replacement recommendation:** **price_led** primary. PKC is an obscure long-haul Russian destination — the click decision is dominated by "is the fare real and reasonable?". Headline: "Flights to Petropavlovsk-Kamchatsky" + "Compare 800+ Airlines" + "Book in 60 Seconds". Description: "Cheapest fares to PKC compared across 800+ airlines. Trustpilot 4.5★. 24h free cancellation." Add a **social_proof** variant as second RSA in the ad group.

### Ad 2 — San Andres Island, Colombia (ADZ)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor. Same structural problem as Ad 1.
- **Banned-phrase hits:** Same 11 items. Add "your local san andres island, colombia expert" — a *Colombian island* expert from a Canadian OTA is implausible and reads as scammy.
- **First-Three-Words audit:** H2 "San Andres Island, Colombia" — passable but ends with a country name, eating the chars where a verb or number should sit. H3 unpinned. Position-3 fallbacks are all "Pro/Book/Best/Certified/Fast & Reliable San andres island," — all truncated.
- **Specificity score:** 1/10. "From $499" again. No airline (Avianca, LATAM, Wingo, Copa all fly here — none mentioned), no departure pairing, no season callout (Caribbean island, dry season Dec–Apr is huge).
- **OTA-vertical fit:** Zero.
- **Truncation/typo issues:** "Pro San andres island," "Book San andres island," "Certified San andres island," "Fast & Reliable San andres", "Best San andres island,", "San andres island, colombia in", "San andres island, colombia -". Lowercase "san andres island" everywhere mid-sentence in descriptions.
- **Pre-flight checklist failures:** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 — all 12 fail.
- **Replacement recommendation:** **price_led** + **urgency/seasonal**. San Andres is a discretionary beach trip. Lead with "Flights to San Andres from $X" if a real floor exists. Variant 2 should be **social_proof** ("1.5M+ travelers/year • Trustpilot 4.5★"). If there's a Caribbean seasonal angle, a discount_led variant pegged to the dry season works.

### Ad 3 — West Palm Beach (Florida) (PBI)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor.
- **Banned-phrase hits:** All 11 from above. "Local West Palm Beach expert" is again the home-services template — and West Palm Beach is a US domestic destination with intense competition (Expedia, Kayak, Google Flights itself). This template will lose every auction.
- **First-Three-Words audit:** H2 fine ("West Palm Beach (Florida)"), but the parenthetical eats the visible chars. H3 unpinned. Position-3 candidates all truncated or template-filler ("Pro West palm beach (florida)", "Book West palm beach", "Best West palm beach").
- **Specificity score:** 1/10. PBI is a US domestic short-haul. Flightnetwork should be naming a fare floor for nonstop from major NE/Midwest origins. None of that surfaces.
- **OTA-vertical fit:** Zero. This is the worst-case competitor environment (US OTA SERP) for a generic home-services template to compete in.
- **Truncation/typo issues:** Lowercase mid-sentence "west palm beach (florida)" throughout descriptions. "Fast & Reliable West palm" — truncated. "Best West palm beach" — looks like it might cut off "Florida" and reads as a generic claim.
- **Pre-flight checklist failures:** All 12.
- **Replacement recommendation:** **price_led** is mandatory here — US travelers search "cheap flights to West Palm Beach" and decide on the displayed fare. Lead headline: "Flights to West Palm Beach (PBI)" + "Nonstop & 1-Stop Options" + "From [actual floor]". Variant 2: **social_proof** with Trustpilot rating and traveler count.

### Ad 4 — Reunion (RUN)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor. This one is even worse than the others because H2 is just "Reunion" — a single ambiguous word that could mean a family reunion, a class reunion, or the island. Searchers querying for the island will not recognize this as their intent.
- **Banned-phrase hits:** All 11. Plus the "Reunion - Same-Day Service" headline — "Same-Day Service" is a home-services hallmark and is nonsensical for international flights to the Indian Ocean.
- **First-Three-Words audit:** H2 "Reunion" is one word — wastes the position. H3 unpinned. Fallbacks include "Professional Reunion" (meaningless), "Reunion in" (dangling preposition), "Best Reunion in" (truncated and meaningless).
- **Specificity score:** 0/10. There is literally nothing specific in this ad. Not even the destination is unambiguous.
- **OTA-vertical fit:** Zero. "Same-Day Service" actively misleads — Reunion is a 14-hour flight from most western markets.
- **Truncation/typo issues:** "Reunion in" (dangling), "Best Reunion in" (dangling + truncated), "Reunion - Same-Day Service" (false claim), "We offer reunion in with 10 years of experience" (broken template — "in" with nothing after it). Description 1 is incoherent.
- **Pre-flight checklist failures:** All 12, plus an extra ambiguity failure (the destination name).
- **Replacement recommendation:** **price_led** with disambiguation. Headline must specify "Flights to Réunion Island" (the accent helps disambiguate from "reunion" the event). Use airport code (RUN) as secondary signal. Lever stack: specificity (named airline if Air France/Corsair fly direct) + price floor + social_proof. Second RSA: **loss_aversion** ("Fares to RUN change daily — lock in today").

### Ad 5 — San Carlos De Bariloche (BRC)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor.
- **Banned-phrase hits:** All 11. "Local San Carlos de Bariloche expert" is geographically absurd — Bariloche is in Argentine Patagonia.
- **First-Three-Words audit:** H2 OK in raw form. Unpinned fallbacks all truncated ("Pro San carlos de bariloche", "Certified San carlos de", "Best San carlos de bariloche").
- **Specificity score:** 1/10. Bariloche is a ski/lake destination with strong seasonality (winter = Jul–Sep S. hemisphere). Zero seasonal hook. No mention of LATAM, Aerolíneas Argentinas, or Flybondi.
- **OTA-vertical fit:** Zero.
- **Truncation/typo issues:** "Certified San carlos de" (truncated), "Fast & Reliable San carlos de" (truncated), "Best San carlos de bariloche" (truncated), "San carlos de bariloche -" (orphaned hyphen), "san carlos de bariloche in with" (broken template).
- **Pre-flight checklist failures:** All 12.
- **Replacement recommendation:** **price_led** with a **seasonal/urgency** second variant tied to ski season. Bariloche is a high-consideration leisure destination — social_proof matters too. Three-variant minimum: price, social_proof, urgency.

### Ad 6 — Santiago De Compostela (SCQ)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor.
- **Banned-phrase hits:** All 11.
- **First-Three-Words audit:** H2 "Santiago De Compostela" — fine in raw form but eats the visible chars. Unpinned positions all truncated.
- **Specificity score:** 1/10. SCQ is the Camino de Santiago pilgrimage endpoint — a *huge* seasonal/identity angle exists (pilgrims, May–Sep peak) and is completely missed.
- **OTA-vertical fit:** Zero. "Local Santiago de Compostela expert" is nonsense; Flightnetwork is a Canadian OTA.
- **Truncation/typo issues:** "Certified Santiago de" (truncated), "Fast & Reliable Santiago de" (truncated), "Best Santiago de compostela in" (dangling), "Santiago de compostela -" (orphaned hyphen).
- **Pre-flight checklist failures:** All 12.
- **Replacement recommendation:** **price_led** + **identity** variant (Camino pilgrim). Headline: "Fly to Santiago de Compostela" + "Compare 800+ Airlines" + Iberia/Vueling/Ryanair specificity if true. Identity variant: "Walking the Camino? Book SCQ Flights" — this is the type of pattern interrupt the skill recommends for saturated verticals.

### Ad 7 — Santa Cruz De La Palma (SPC)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor.
- **Banned-phrase hits:** All 11.
- **First-Three-Words audit:** H2 "Santa Cruz De La Palma" — full destination name eats all 30 chars (22 used). Unpinned fallbacks all truncated.
- **Specificity score:** 1/10. La Palma is a Canary Island — winter sun is the dominant intent. No seasonal hook.
- **OTA-vertical fit:** Zero.
- **Truncation/typo issues:** "Certified Santa cruz de la" (truncated), "Fast & Reliable Santa cruz de" (truncated), "Best Santa cruz de la palma in" (dangling), "Santa cruz de la palma -" (orphaned hyphen). All-lowercase mid-sentence "santa cruz de la palma" in descriptions.
- **Pre-flight checklist failures:** All 12.
- **Replacement recommendation:** **price_led** + **seasonal/urgency** for winter sun. Binter Canarias is the main carrier — name it. Second variant: **social_proof** with Flightnetwork's actual trust signals.

### Ad 8 — Sao Jose Do Rio Preto (SJP)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor.
- **Banned-phrase hits:** All 11.
- **First-Three-Words audit:** H2 OK in raw form. Unpinned positions all truncated.
- **Specificity score:** 1/10. SJP is a Brazilian regional airport (interior São Paulo state) — typical traveler is domestic Brazilian or business. The home-services framing is doubly absurd here because the searcher is probably Portuguese-speaking, and the entire ad is in English. Language mismatch is a real failure on top of everything else.
- **OTA-vertical fit:** Zero. Plus a language-market fit failure — should this be Portuguese? Or US-English with Brazilian-routing intent? The brief doesn't say but the keyword targeting almost certainly captures Portuguese queries that this ad cannot serve well.
- **Truncation/typo issues:** "Certified Sao jose do rio" (truncated), "Fast & Reliable Sao jose do" (truncated), "Best Sao jose do rio preto in" (dangling), "Sao jose do rio preto -" (orphaned hyphen). Missing tilde on "São" throughout (ASCII approximation — a stop-slop hard ban under "ASCII approximations of accented characters").
- **Pre-flight checklist failures:** All 12. The "São" → "Sao" ASCII flattening is an extra stop-slop hit.
- **Replacement recommendation:** **price_led** with the accent restored ("Voos para São José do Rio Preto" if Portuguese, or "Flights to São José do Rio Preto" if English). Second variant: **social_proof**. Strong recommendation: split this into a Portuguese RSA and an English RSA, never one bilingual ad.

### Ad 9 — Nowy Dwór Mazow'iecki (WMI)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor.
- **Banned-phrase hits:** All 11.
- **First-Three-Words audit:** H2 "Nowy Dwór Mazow'iecki" — and that apostrophe is wrong. The Polish town is "Nowy Dwór Mazowiecki" — no apostrophe. The apostrophe is a data-cleaning failure that's now live on the SERP, signaling sloppiness to Polish-speaking searchers.
- **Specificity score:** 1/10. WMI is Warsaw-Modlin airport — Ryanair's secondary Warsaw hub. The keyword "flights to WMI" is overwhelmingly a Ryanair fare-seeking query. Zero mention of Ryanair, Warsaw, or budget-airline pricing.
- **OTA-vertical fit:** Zero. Plus language fit fails — Polish searchers should see Polish copy.
- **Truncation/typo issues:** Stray apostrophe in "Mazow'iecki" (data pipeline bug, must be fixed at source). "Certified Nowy dwór" (truncated), "Fast & Reliable Nowy dwór" (truncated), "Best Nowy dwór mazow'iecki in" (dangling + bad apostrophe), "Nowy dwór mazow'iecki -" (orphaned hyphen). Lowercase "nowy dwór" mid-sentence. Path2 = "dwór" with the accent character may render or break depending on Google's display encoding.
- **Pre-flight checklist failures:** All 12.
- **Replacement recommendation:** **price_led**, frame as Warsaw. Headline: "Cheap Flights to Warsaw-Modlin (WMI)" — searchers don't think of "Nowy Dwór Mazowiecki" as a destination, they think "Warsaw" or "WMI". Second variant: **social_proof** with traveler count. Fix the apostrophe in the source catalog before any push.

### Ad 10 — Jerez De La Frontera (XRY)

- **Verdict:** BLOCK
- **Estimated Ad Strength:** Poor.
- **Banned-phrase hits:** All 11.
- **First-Three-Words audit:** H2 OK in raw form. Unpinned fallbacks all truncated.
- **Specificity score:** 1/10. Jerez is sherry country and the gateway to Cádiz — strong identity/seasonal angles (sherry tourism, Costa de la Luz beaches, Feria del Caballo in May). Zero hooks.
- **OTA-vertical fit:** Zero.
- **Truncation/typo issues:** "Fast & Reliable Jerez de la" (truncated), "Best Jerez de la frontera in" (dangling), "Jerez de la frontera -" (orphaned hyphen). All-lowercase mid-sentence in descriptions.
- **Pre-flight checklist failures:** All 12.
- **Replacement recommendation:** **price_led** + **identity/seasonal** variant. Headline: "Flights to Jerez (XRY)" + "Sherry & Costa de la Luz" or simply name Ryanair/Vueling if true. Second variant: **social_proof**.

---

## Pattern-level fixes (apply to ALL future RSAs)

1. **Strip the home-services template completely.** No "Pro [X]", "Book [X]", "Certified [X]", "Fast & Reliable [X]", "Best [X]", "Professional [X]", "Local [X] expert", "Free consultation", "Get a Free Quote", "Free Quote & Advice", "Same-Day Service", "100 Years Experience", "Over 100 Happy Customers". These are exactly the patterns the skill's banned-English table enumerates. They should never have shipped on an OTA.

2. **Fix the truncation pipeline at the generator level, not in QA.** The bug is feeding a 28–30 char destination name into a 30 char headline slot that already has a prefix word ("Book ", "Best ", "Pro ", "Certified ", "Fast & Reliable "). For long destinations either (a) drop the prefix-word variants entirely, (b) substitute the IATA code ("Book PKC" rather than "Book Petropavlovsk-kamchats,"), or (c) skip headlines whose composed length exceeds 30 chars rather than truncating mid-word. The current behavior of trailing-comma cutoffs is a Google Ads disapproval hazard.

3. **Fix case preservation.** Whatever lowercase()'s the destination string when filling description templates ("we offer west palm beach (florida) in...") must preserve title case. "West Palm Beach" should appear as "West Palm Beach" in every position, not "west palm beach".

4. **Fix the broken interpolation slots.** "We offer [city] in with 10 years of experience" has a literal "in" with nothing after it — there's a missing variable slot. "Call ." has a missing phone number. "Contact us a free consultation" is missing "for". These are template variables that resolved to empty strings and were never re-validated. Fix the template, add a non-empty assertion, or remove the variable.

5. **Replace home-services proof points with OTA proof points.** Mandatory rotation pool: "800+ airlines compared", "1.5M+ travelers/year", "Trustpilot 4.5★", "IATA-accredited", "24h free cancellation", "No hidden fees", "24/7 support". Pick 2–3 per ad. None of "10 years experience", "100 years experience", "Over 100 happy customers", "Certified", "Licensed", "Insured" — these are all home-services-vertical signals that don't apply to a flight comparison site (and most are factually wrong for Flightnetwork).

6. **Lead with the fare, not the brand.** The skill's first-three-words doctrine: front-load keyword/number/verb/pain. For OTA, this means H3 should be "From $[X]" or "Compare 800+ Airlines" or "24h Free Cancellation", not "Get a Free Quote". The price floor must be real — pulled from current inventory, not a hardcoded "$499" placeholder copied across every destination on earth.

7. **Use IATA codes as a fallback for unwieldy destination names.** "Nowy Dwór Mazowiecki" → "Warsaw-Modlin (WMI)". "Petropavlovsk-Kamchatsky" → "PKC". "San Carlos de Bariloche" → "Bariloche (BRC)". This solves three problems: char-limit overflow, search-intent matching (people search "WMI" and "Bariloche", not the full official name), and truncation.

8. **Run the stop-slop pass.** ASCII approximation of "São" → "Sao" must restore "São". The em-dash → hyphen sub ("Flightnetwork - local...") should be either a real em-dash or removed. The "Call ." period orphan is a stop-slop hard ban. The pair-clichés "Fast & Reliable" and "quickly and professionally" are explicit slop tells.

9. **Generate 3–5 distinct RSA variants per ad group** with explicit lever roles: `price_led`, `discount_led` (only when `discount_pct > 0`, surface the literal %), `social_proof`, `urgency` (only with real deadlines), `loss_aversion`. The current 1-RSA-per-ad-group with 15 near-duplicate headlines is the worst of both worlds — fails Ad Strength on semantic similarity *and* gives Google nothing to A/B against.

10. **Language-match the SERP.** Brazilian destinations (SJP, etc.) likely capture Portuguese searches — write Portuguese ads. Polish destinations (WMI) likely capture Polish searches — write Polish ads. The skill is explicit: "If the client operates in multiple markets, write separate RSAs per market — never one bilingual ad." Right now everything is English regardless of destination, which is fine for US/UK-origin traffic but wastes impressions on local-language queries.

11. **Validate every published ad against the Pre-Flight Checklist before push.** Specifically item 12 (compliance): "100 Years Experience" on a 1997-founded brand is a false-claims risk under FTC truthfulness rules and Google Ads misleading-content policy. This should have been a hard fail at validation time.

12. **Bring back the keyword in 3+ headlines.** Currently each ad has H2 with the destination name and several truncated-destination headlines, but no clean "Flights to [destination]" or "Cheap flights to [destination]" headline. The Quality Score impact of keyword inclusion is real and these ads are leaving it on the table.

The TL;DR for the next push: throw all 10 out, regenerate with the OTA playbook (price + 800+ airlines + Trustpilot 4.5★ + 24h cancellation), 3–5 RSA variants per ad group, IATA codes for long destinations, fix the template truncation and case bugs, and run the pre-flight checklist before anything goes live.
