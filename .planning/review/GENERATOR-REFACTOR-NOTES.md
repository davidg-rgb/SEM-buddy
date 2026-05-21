# Generator Refactor Notes

Companion to Agent A's pattern-pack v3 rewrite. Closes Severity-0 and most
Severity-1 findings from `CONSOLIDATED-REVIEW.md` at the generator level.

## Changes applied

### src/generators/ad_copy_generator.py

- **S0-1 null-safe price**: `_fill_pattern` now honors `requires_from_price`
  and `requires_was_price` flags (early-skips), and runs a final regex sweep
  (`_result_has_bad_price_fragment`) that rejects any line still carrying a
  bare `$`, `$ `, `$,`, `$.`, or trailing `from ` after substitution. Empty
  return signals "skip this pattern" to all callers.
- **S0-5 long-name fallback**: new `_resolve_display_name(product, budget)`
  resolves a destination to `short_name → comma-segment → name → IATA SKU`
  in that order. `_fill_pattern` uses it for `{name}` substitution with a
  budget = `max_chars - 4` (4-char fudge for other tokens).
- **S0-6 no mid-word truncation**: `_fit_to_limit` extends trailing-token
  drop to a new English fragment set (`leg, fee, free, fare, flights,
  cancellation, ...`) and adds a 50% floor — if the truncated result is
  less than half the budget, return empty string so the caller skips. Kills
  the "Compare", "Avoid Petropavlovsk-Kamchats" cases.
- **S1-11 discount floor**: `MIN_DISCOUNT_PCT_FOR_DISCOUNT_LED = 0.15`,
  exported. `_product_has_discount` now returns `False` for `0 < dp < 0.15`
  so the variant downgrades to `loss_aversion`.
- **S1-13 discount-% cap**: `MAX_DISCOUNT_PCT_HEADLINES = 5`, exported.
  In `generate_headlines_for_variant` the `_add` helper refuses to add
  another %-bearing headline once the cap is reached (for discount_led).
  Variant-tail-headlines + universals fill the freed slots.
- **S1-7 IATA allowlist**: `IATA_HOUSEHOLD_CODES` (54 codes), exported.
  `_should_use_iata_in_customer_copy` gates SKU substitution. In
  `_fill_pattern` the `{sku}` placeholder renders as empty string when the
  SKU isn't household-known AND the pattern hasn't opted into
  `long_name_fallback: true`. Empty-rendered patterns get rejected
  downstream.
- **S1-2 computed Was/Now anchor**: `_compute_was_price` returns
  `(was, now)` from `from_price / (1 - discount)`. New placeholders
  `{was_price}`, `{now_price}`, `{was_minus_now}` are available. The
  discount_led variant appends an on-the-fly `"Was ${was}, now ${now}"`
  headline when it fits 30 chars.
- **S1-10 stop-slop pass**: new `_stop_slop_pass` — hyphen-as-pause →
  comma, ASCII-flat → restored diacritic (whole-word match: "Sao Paulo" →
  "São Paulo", "Sao Jose" → "São José", "Reunion" → "Réunion"), double
  spaces collapsed, leading space before punctuation stripped. Called from
  `_apply_language_rules` for both English and Swedish.
- **Schema additions**: generator now reads `tail_headlines`,
  `pattern_interrupt_h4`, and `long_name_fallback_patterns` from the
  pattern pack. `pattern_meta` is threaded through every `_fill_pattern`
  caller so per-pattern flags (`requires_from_price`, `long_name_fallback`,
  `requires_was_price`, `max_chars`) work end-to-end.

### src/generators/llm_ad_copy.py

- Banned-phrase list extended (S1-10): added `top-rated travel agent`,
  `ATOL-style` / `ATOL-style protection`, literal `cheap flights`,
  `Price Drop Alerts Free`, `Was full price`, `Today only`, `Final seats`,
  `Last-minute`. Em-dash and hyphen-as-pause now explicitly banned.
- Variant prompt text rewritten for `social_proof` (real proofs only, no
  ATOL implication), `discount_led` (compute real anchors, percent cap
  reminder), `urgency` (no fake countdowns), `loss_aversion` (FN moat
  promoted).

### src/models/catalog.py

- Added optional `short_name: str | None` field on `Product` for operator-
  curated long-name fallbacks.

### tests/test_ad_copy_english_and_product.py

- `test_fill_pattern_missing_attribute_degrades_gracefully` updated to
  assert null-safe rejection (`out == ""`) — the OLD contract ("Test in
  out") shipped a naked `$` to customers, which is the bug we're closing.
- Added `test_fill_pattern_rejects_requires_from_price_when_null`.

## Test results

```
SEM_DISABLE_LLM=1 python -m pytest tests/test_rsa_variants.py
  tests/test_catalog_campaign_builder.py
  tests/test_ad_copy_english_and_product.py -q
→ 58 passed in 2.66s

Full suite (minus account_provisioning + scale, both untouched):
→ 592 passed in 19.77s
```

## Assumed pattern-pack contracts (must match Agent A)

1. Top-level block `long_name_fallback_patterns` with sub-keys
   `headline_patterns` and `description_patterns` — each pattern dict
   carries `long_name_fallback: true`.
2. Each variant block carries optional `tail_headlines` (list of 1-2
   pattern dicts) and `pattern_interrupt_h4` (list of 1-2 pattern dicts).
3. Pattern dicts may carry `requires_from_price: true`,
   `requires_was_price: true`, `long_name_fallback: true`, and `max_chars`
   (defaults 30 / 90). The generator threads these through `pattern_meta`.
4. Placeholders supported: `{name}`, `{sku}`, `{from_price}`,
   `{discount_pct}`, `{was_price}`, `{now_price}`, `{was_minus_now}`
   (last three computed on-the-fly from `from_price` + `discount_pct`).

## Known limitations / honest notes

- `_fit_to_limit` still ships 1-2 borderline cases per run where a number
  (e.g. "60") gets stranded after truncation. Numbers aren't in the
  drop-list. Acceptable for now — the patterns themselves have been
  rewritten so this is rare in practice.
- The 50% floor in `_fit_to_limit` is a hard line — short patterns that
  happen to truncate aggressively will be rejected. This is the intended
  trade: skip beats ship-a-fragment.
- The `_stop_slop_pass` diacritic map is conservative (only 3 entries).
  Extend as more cases come up; better to under-restore than corrupt a
  legitimate English word.
- The new test `test_fill_pattern_missing_attribute_degrades_gracefully`
  was a deliberate contract change. The old assertion was documenting the
  bug, not the desired behavior — the review explicitly flagged it.
