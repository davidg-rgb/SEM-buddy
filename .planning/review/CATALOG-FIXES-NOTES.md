# Catalog Fixes — IATA Canonicalisation Notes

## What shipped

Three non-IATA SKUs in the etraveli catalog (NY, LON-Heathrow, Louisville)
were canonicalised to proper IATA codes (NYC, LHR, SDF) via the existing
cleaning-proposal mechanism, plus a new IATA-SKU validator now flags any
future non-IATA codes.

## Diffs added to `accepted_proposal.json`

| row_key | field | before → after | reason |
|---|---|---|---|
| Louisville | `__sku__` | Louisville → SDF | Fix sku/name inversion (source XLSX columns swapped) |
| SDF | name | SDF → "Louisville, KY" | Restore customer-facing name after rename |
| SDF | from_price | null → 200 | Placeholder lower-bound retail until live pricing wired up |
| NY | `__sku__` | NY → NYC | Canonicalise to IATA metro code; collides with existing NYC, NY row dropped |
| NYC | name | NYC → "New York City" | Replace IATA code echoed in name field with the destination |
| LON-Heathrow | `__sku__` | LON-Heathrow → LHR | Canonicalise to IATA airport code (Heathrow specifically) |
| LHR | name | London → "London Heathrow" | Tighten name to match the LHR-specific code |
| LHR | from_price | null → 350 | Placeholder transatlantic baseline until live pricing wired up |

## New diff type: `__sku__`

`CleaningDiff.field == "__sku__"` renames a row's primary key. It is
applied first per row, so subsequent diffs in the same proposal can
reference either the old or the new key.

Collision behaviour: if the rename target already exists in the source
catalog (e.g. `NY → NYC` when `NYC` is already present), the source row
is DROPPED and the existing target stays — its data is canonical. This is
how the NYC row keeps its real $452 / 24% discount while the bogus
null-priced NY row disappears.

Implemented in `src/catalog/cleaners.py::apply_proposal`. Docstring on
`CleaningDiff` documents the field-type semantics.

## New validator: `validate_iata_skus`

In `src/catalog/validators.py`:

- Constant `_IATA_RE = re.compile(r"^[A-Z]{3}$")`
- Function `validate_iata_skus(catalog) -> list[str]` — returns a warning
  per non-IATA SKU. Format:
  `"SKU '{sku}' (name='{name}') is not a valid 3-letter IATA code"`
- Wired into `validate_catalog()` as a non-fatal `warning` with
  `code="non_iata_sku"`. Surfaces in the standard `ValidationReport`.

The validator is purely diagnostic — non-IATA codes never block the load.

## Final catalog state

```
NYC | 'New York City' | {'from_price': 452.0, 'discount_pct': 0.24}
LHR | 'London Heathrow' | {'from_price': 350, 'discount_pct': 0.0}
SDF | 'Louisville, KY' | {'from_price': 200, 'discount_pct': 0.0}
```

Old keys NY, LON-Heathrow, Louisville: not present (gone).
Total rows: 963 (was 964 — NY collapsed into existing NYC).
`validate_iata_skus()` post-cleaning: zero warnings.

## Test results

- New: `tests/test_iata_validator.py` (12 tests) — PASS
- New: `tests/test_sku_remap.py` (8 tests) — PASS
- Regression: `tests/test_catalog_loader.py` + `test_catalog_validators_cleaners.py` (36) — PASS
- Broader catalog suite (loader, validators, url-templating, bid-rules, campaign-builder, csv-exporter, iata-validator, sku-remap) — 100/100 PASS
- `tests/test_case_runner.py` (7) — PASS

## Out of scope (still outstanding)

- The remaining S0/S1 ad-copy items in CONSOLIDATED-REVIEW (null-safe
  price interpolation, banned-phrase scrubs, long-name fallback) — owned
  by Agents A/B per the brief.
- "iata_override: true" config flag for legitimate non-IATA SKUs (not
  needed for etraveli; can be added when a real case requires it).
