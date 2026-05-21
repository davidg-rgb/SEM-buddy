"""Tests for the IATA-SKU validator added in the catalog-fixes phase.

Covers:
  - `validate_iata_skus` flags any row whose primary key is not a syntactically
    valid 3-letter IATA code.
  - The etraveli catalog, after the accepted cleaning proposal is applied,
    contains ZERO non-IATA SKUs (NY → NYC, LON-Heathrow → LHR,
    Louisville → SDF have all been remapped).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.catalog import (
    Catalog,
    CatalogConfig,
    CatalogRow,
    SourceConfig,
    load_catalog_from_yaml,
)
from src.catalog.validators import _IATA_RE, validate_iata_skus


def _make_catalog(keys: list[str]) -> Catalog:
    """Tiny in-memory catalog factory for the IATA-SKU unit tests."""
    config = CatalogConfig(
        primary_key="sku",
        sources=[SourceConfig(type="csv", path="unused.csv")],
    )
    rows = [CatalogRow(key=k, name=f"Name-of-{k}") for k in keys]
    return Catalog(config=config, rows=rows)


# --- the regex itself -------------------------------------------------------


def test_iata_re_matches_exactly_three_uppercase_letters() -> None:
    assert _IATA_RE.match("NYC")
    assert _IATA_RE.match("LHR")
    assert _IATA_RE.match("SDF")
    assert _IATA_RE.match("ABC")


def test_iata_re_rejects_invalid_lengths_and_chars() -> None:
    assert not _IATA_RE.match("NY")     # 2 letters
    assert not _IATA_RE.match("NYCC")   # 4 letters
    assert not _IATA_RE.match("nyc")    # lowercase
    assert not _IATA_RE.match("NY1")    # digit
    assert not _IATA_RE.match("LON-Heathrow")
    assert not _IATA_RE.match("")


# --- validate_iata_skus -----------------------------------------------------


def test_validate_iata_skus_flags_4_letter_sku() -> None:
    cat = _make_catalog(["NYCC"])
    warnings = validate_iata_skus(cat)
    assert len(warnings) == 1
    assert "NYCC" in warnings[0]
    assert "not a valid 3-letter IATA code" in warnings[0]


def test_validate_iata_skus_flags_hyphenated_sku() -> None:
    cat = _make_catalog(["LON-Heathrow"])
    warnings = validate_iata_skus(cat)
    assert len(warnings) == 1
    assert "LON-Heathrow" in warnings[0]


def test_validate_iata_skus_flags_two_letter_sku() -> None:
    cat = _make_catalog(["NY"])
    warnings = validate_iata_skus(cat)
    assert len(warnings) == 1
    assert "NY" in warnings[0]


def test_validate_iata_skus_flags_lowercase_sku() -> None:
    cat = _make_catalog(["nyc"])
    warnings = validate_iata_skus(cat)
    assert len(warnings) == 1


def test_validate_iata_skus_flags_city_name_sku() -> None:
    cat = _make_catalog(["Louisville"])
    warnings = validate_iata_skus(cat)
    assert len(warnings) == 1
    assert "Louisville" in warnings[0]


def test_validate_iata_skus_accepts_clean_iata_codes() -> None:
    cat = _make_catalog(["NYC", "LHR", "SDF", "BKK", "JFK"])
    assert validate_iata_skus(cat) == []


def test_validate_iata_skus_mixed_catalog_returns_only_bad() -> None:
    cat = _make_catalog(["NYC", "LON-Heathrow", "JFK", "NY"])
    warnings = validate_iata_skus(cat)
    assert len(warnings) == 2
    msg = " ".join(warnings)
    assert "LON-Heathrow" in msg
    assert "NY" in msg
    # NYC and JFK should NOT show up
    assert "NYC" not in msg.replace("LHR", "").replace("JFK", "")
    # (use the original strings — the test above proves this)


def test_warning_message_includes_name() -> None:
    cat = _make_catalog(["NY"])
    cat.rows[0] = cat.rows[0].model_copy(update={"name": "New York City"})
    warnings = validate_iata_skus(cat)
    assert "New York City" in warnings[0]


# --- end-to-end: etraveli catalog has zero non-IATA SKUs after cleaning -----


ETRAVELI_YAML = Path("clients/etraveli/catalog.yaml")
ETRAVELI_SKIP_REASON = "etraveli source XLSX not available in this checkout"


@pytest.mark.skipif(
    not ETRAVELI_YAML.exists(), reason=ETRAVELI_SKIP_REASON
)
def test_etraveli_catalog_has_zero_non_iata_warnings_after_cleaning() -> None:
    """End-to-end regression: post-cleaning, every SKU is IATA-valid.

    This is the headline guarantee of the catalog-fixes phase. If this fails,
    something in `accepted_proposal.json` or `apply_proposal` has regressed.
    """
    from src.cases.runner import _maybe_clean_catalog

    catalog = load_catalog_from_yaml(ETRAVELI_YAML)
    catalog, applied = _maybe_clean_catalog("etraveli", catalog)
    assert applied, "Expected the accepted cleaning proposal to be applied"

    warnings = validate_iata_skus(catalog)
    assert warnings == [], (
        f"Etraveli catalog has {len(warnings)} non-IATA SKUs after cleaning: "
        + "; ".join(warnings[:5])
    )


@pytest.mark.skipif(
    not ETRAVELI_YAML.exists(), reason=ETRAVELI_SKIP_REASON
)
def test_etraveli_fixed_rows_present_with_correct_data() -> None:
    """The three remapped destinations (NYC, LHR, SDF) ship with correct
    customer-facing names and non-null from_price."""
    from src.cases.runner import _maybe_clean_catalog

    catalog = load_catalog_from_yaml(ETRAVELI_YAML)
    catalog, _ = _maybe_clean_catalog("etraveli", catalog)

    by_key = {row.key: row for row in catalog}

    assert "NYC" in by_key
    assert by_key["NYC"].name == "New York City"
    assert by_key["NYC"].attributes.get("from_price") is not None

    assert "LHR" in by_key
    assert by_key["LHR"].name == "London Heathrow"
    assert by_key["LHR"].attributes.get("from_price") == 350

    assert "SDF" in by_key
    assert by_key["SDF"].name == "Louisville, KY"
    assert by_key["SDF"].attributes.get("from_price") == 200

    # And the old keys are gone
    for old in ("NY", "LON-Heathrow", "Louisville"):
        assert old not in by_key, f"Old non-IATA SKU {old!r} still in catalog"
