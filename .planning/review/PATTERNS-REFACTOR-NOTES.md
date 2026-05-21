# Patterns Refactor Notes — `data/en/ad_copy_patterns.json` v2 -> v3

Date: 2026-05-20
File: `data/en/ad_copy_patterns.json`

## Patterns removed (and why)

| Removed | Reason |
|---|---|
| `"Top-rated travel agent"` | Banned per skill ("Top-rated" without source) -> replaced with `"4.5★ on Trustpilot"` (real proof). |
| `"ATOL-style protection"` | Misleading — Flightnetwork has no ATOL or ATOL-equivalent. ASA/FTC risk. Replaced with `"IATA-accredited agent"`. |
| `"Was full price, now -{discount_pct}%"` | False anchor (no reference price ever shown) — FTC/ASA exposure. Removed; Generator B will inject computed `"Was $was_price, now $from_price"`. |
| `"Today only: {discount_pct}% off"` | Fake scarcity, no real deadline. |
| `"Final seats: {name} ${from_price}"` | Fake inventory claim. |
| `"{name} sale ends this week"` | Undated countdown, fake scarcity. |
| `"Last-minute {name} flights"` | OTA cliche + no real urgency data. |
| `"Cheap {name} flights"` | Low-status OTA cliche; price already says "cheap." Replaced with `"{name} from ${from_price}"`. |
| `"Member, IATA accredited"` | Awkward word order. Replaced with `"IATA-accredited agent"`. |
| `"Price Drop Alerts Free"` | Title-Case UI-label voice. Replaced with `"Free price-drop alerts"`. |
| `"No hidden fees - ever"` | Hyphen-as-em-dash (stop-slop ban). Replaced with comma: `"No hidden fees, ever"`. |
| `"{name} - 800+ airlines"` | Same hyphen issue -> `"{name}, 800+ airlines"`. |
| `"{Company} - book {sku}"` | Same hyphen + IATA-code in customer copy. Deleted. |
| `"{sku} airport flights"` | IATA in customer copy. Deleted. |
| `"Skip the markup on {sku}"` | IATA in customer copy. Generalised to `"Skip the OTA markup"`. |
| `"Price guarantee on {sku}"` | IATA in customer copy. Replaced with `"Price-match {name} fares"`. |
| `"{sku} deals updated hourly"` | IATA in customer copy. Replaced with `"{name} fares update hourly"` (kept as `long_name_fallback`). |
| `"Compare fares today"` (generic H3) | Tier-2 parity. Replaced with role-specific CTAs (see below). |
| Top-level `headline_patterns`, `description_patterns`, `legacy_headline_patterns`, `legacy_description_patterns` | Dead-weight legacy blocks; variant architecture is canonical. |

## New variant role contracts

Each variant now ships seven required fields: `lever_stack`, `description`, `pattern_interrupt_h4`, `headline_patterns`, `description_patterns`, `cta_pinned`, `tail_headlines`.

- **price_led** — Lever: specificity + friction_removal. Pinned H3s: `Lock in 60 seconds` / `Compare 800+ airlines` / `See live flight prices`. Tail H14/H15: `Lowest fare today` / `Real-time price compare`. Wins when from-price is genuinely category-leading.
- **discount_led** — Lever: loss_aversion + specificity + scarcity. Requires `discount_pct >= 0.15` (enforced upstream). Pinned H3s: `Claim {discount_pct}% off now` / `Save {discount_pct}% on flights` / `Book before sale ends`. Tail: `{discount_pct}% off this week` / `Save ${was_minus_now}` (the second uses a Generator-B-computed placeholder).
- **social_proof** — Lever: authority + social_proof + risk_reversal. Pinned H3s: `Compare 800+ airlines` / `4.5★ on Trustpilot` / `Book with confidence`. Tail: `4.5★ Trustpilot reviews` / `IATA-accredited since 2007`. Real proof points only.
- **urgency** — Real urgency only. Lever stack unchanged but execution rebuilt around live pricing. Pinned H3s: `Fares update every hour` / `Lock today's price` / `Book before fares climb`. Tail: `Fares updated hourly` / `Lock today's price`. Zero fake-scarcity language.
- **loss_aversion** — Lever: loss_aversion + pain + specificity. The Flightnetwork moat — leans on "Pay the airline price, not the OTA markup." Pinned H3s: `Pay the airline price` / `Skip the OTA markup` / `See real flight prices`. Tail: `Pay airline price, not OTA` / `No hidden fees, ever`.

All five variants share the same two `pattern_interrupt_h4` candidates: `"Pay the airline price"` (22 chars) and `"Free 24h cancellation"` (21 chars). Generator B promotes one of these to H4 to break OTA parity.

## Patterns flagged `long_name_fallback`

A new top-level block `long_name_fallback_patterns` holds six headlines + two descriptions that substitute `{sku}` for `{name}` when the destination name is >= 18 chars. These are the ONLY patterns where IATA codes appear in customer-facing slots. Generator B opts into this block explicitly via name-length policy:

- `{sku} flights from ${from_price}` (requires_from_price)
- `{sku} from ${from_price}` (requires_from_price)
- `{sku} -{discount_pct}%`
- `Flights to {sku}`
- `{sku} fares`
- `{sku} fares update hourly`
- Two SKU-form descriptions

## Patterns flagged `requires_from_price`

Any pattern containing `${from_price}` carries `"requires_from_price": true` so Generator B can skip it cleanly when from_price is null. This closes Severity-0 finding S0-1 (naked `$` in NY/LHR/SDF). Counts: price_led has 6 price-dependent headlines, 3 price-dependent descriptions; discount_led has 1 + 2; social_proof has 0 + 2; urgency has 3 + 2; loss_aversion has 1 + 2; long_name_fallback has 2 + 1. Patterns without `from_price` (the discount headlines, proof headlines, urgency live-pricing claims, loss-aversion moats) keep working for null-price destinations.

## Ambiguities resolved

1. **Should pattern_interrupt_h4 vary by variant role?** The brief said "All variants" use the same two candidates. Kept that — every variant exposes the same two Flightnetwork-moat lines so the generator can A/B which one wins at H4 regardless of role. The variant-role differentiation lives in `cta_pinned` (H3) and `tail_headlines` (H14/H15) instead.
2. **`Save ${was_minus_now}` placeholder** is documented with `"requires_was_minus_now": true` so Generator B knows to skip until the computed delta is known (parallel to `requires_from_price`).
3. **Where do household IATA codes like LAX/JFK live?** Not in the patterns file — that's a Generator B allow-list concern, not a pattern concern. Patterns simply mark `long_name_fallback` and the generator decides when to substitute.
4. **Pinning_strategy block** — added an informational `headline_4` key documenting the new `pattern_interrupt_h4` slot. `max_pins` stays at 3 (compliance > algorithm), so H4 is "promoted" via headline ordering, not literal `pin_position=4`.
5. **The `requires_discount` flag on discount_led** — retained from v2. The 15%-floor enforcement is upstream (generator), not a pattern-file concern; the description docs the contract.

## Validation results

- JSON parses cleanly (Python `json.load`).
- 5 variant blocks present with all required fields.
- `universal` + `long_name_fallback_patterns` top-level blocks present.
- 0 banned phrases in any `pattern` string (recursive walk verified).
- 0 ` - ` (hyphen-space-padded) instances in any `pattern` string.
- 0 `{sku}` references in any `cta_pinned`, `tail_headlines`, or `pattern_interrupt_h4` entry.
- `pattern_pack_version` bumped to 3.
- Legacy blocks (`headline_patterns`, `description_patterns`, `legacy_*`) removed.

(Word count: ~610.)
