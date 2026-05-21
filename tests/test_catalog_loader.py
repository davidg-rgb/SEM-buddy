"""Tests for the catalog loader package (C1)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.catalog import (
    Catalog,
    CatalogConfig,
    CatalogRow,
    JoinKey,
    SourceConfig,
    load_catalog,
    load_catalog_from_yaml,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_YAML = FIXTURE_DIR / "catalog_sample.yaml"
SAMPLE_XLSX = FIXTURE_DIR / "catalog_sample.xlsx"


def test_load_catalog_from_yaml_returns_catalog_with_10_rows() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    assert isinstance(catalog, Catalog)
    assert len(catalog) == 10
    assert all(isinstance(r, CatalogRow) for r in catalog)


def test_loader_joins_secondary_sources_on_primary_key() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    # BKK has price 450 and discount 0.25 in the fixture
    bkk = next(r for r in catalog if r.key == "BKK")
    assert bkk.attributes["from_price"] == 450.0
    assert bkk.attributes["discount_pct"] == 0.25
    assert bkk.name == "Bangkok, Thailand"


def test_missing_secondary_data_falls_back_to_defaults() -> None:
    """NYC and EZE are in Destinations but not in Prices or Discounts."""
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    nyc = next(r for r in catalog if r.key == "NYC")
    eze = next(r for r in catalog if r.key == "EZE")
    # defaults: from_price=null, discount_pct=0.0
    assert nyc.attributes["from_price"] is None
    assert nyc.attributes["discount_pct"] == 0.0
    assert eze.attributes["from_price"] is None
    assert eze.attributes["discount_pct"] == 0.0


def test_loader_preserves_row_order_for_deterministic_output() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    keys = [r.key for r in catalog]
    # First row in the fixture is BKK; last is EZE
    assert keys[0] == "BKK"
    assert keys[-1] == "EZE"


def test_csv_source_works(tmp_path: Path) -> None:
    csv_path = tmp_path / "products.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sku", "name", "price"])
        writer.writerow(["A1", "Widget A", "9.99"])
        writer.writerow(["A2", "Widget B", "14.99"])

    config = CatalogConfig(
        primary_key="sku",
        name_column="name",
        sources=[
            SourceConfig(
                type="csv",
                path="products.csv",
                columns={"sku": "sku", "name": "name", "price": "price"},
            )
        ],
    )
    catalog = load_catalog(config, base_dir=tmp_path)
    assert len(catalog) == 2
    assert catalog[0].key == "A1"
    assert catalog[0].name == "Widget A"


def test_json_source_works(tmp_path: Path) -> None:
    json_path = tmp_path / "products.json"
    json_path.write_text(
        json.dumps([
            {"sku": "J1", "name": "Item 1", "stock": 5},
            {"sku": "J2", "name": "Item 2", "stock": 0},
        ]),
        encoding="utf-8",
    )
    config = CatalogConfig(
        primary_key="sku",
        name_column="name",
        sources=[
            SourceConfig(
                type="json",
                path="products.json",
                columns={"sku": "sku", "name": "name", "stock": "stock"},
            )
        ],
    )
    catalog = load_catalog(config, base_dir=tmp_path)
    assert len(catalog) == 2
    assert catalog[1].attributes["stock"] == 0


def test_first_source_must_not_have_join_key() -> None:
    with pytest.raises(ValueError, match="First source must be the primary"):
        CatalogConfig(
            primary_key="sku",
            sources=[
                SourceConfig(
                    type="csv",
                    path="x.csv",
                    join_key=JoinKey(source_column="sku", target_column="sku"),
                )
            ],
        )


def test_xlsx_source_requires_sheet() -> None:
    with pytest.raises(ValueError, match="xlsx source requires 'sheet'"):
        SourceConfig(type="xlsx", path="file.xlsx")


def test_missing_required_column_raises_clear_error(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("sku,name\nA1,Item\n", encoding="utf-8")
    config = CatalogConfig(
        primary_key="sku",
        required_columns=["sku", "name", "price"],
        sources=[
            SourceConfig(
                type="csv",
                path="bad.csv",
                columns={"sku": "sku", "name": "name"},
            )
        ],
    )
    with pytest.raises(ValueError, match="missing required columns.*price"):
        load_catalog(config, base_dir=tmp_path)


def test_partition_by_attribute() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    # We don't have a region attribute in this fixture; partition by
    # has_discount to demonstrate the helper
    for row in catalog:
        row.attributes["has_discount"] = bool(
            row.attributes.get("discount_pct") and row.attributes["discount_pct"] > 0
        )
    buckets = catalog.partition_by("has_discount")
    assert set(buckets.keys()) == {True, False}
    assert sum(len(v) for v in buckets.values()) == 10


def test_load_catalog_missing_yaml_raises() -> None:
    with pytest.raises(FileNotFoundError, match="catalog.yaml"):
        load_catalog_from_yaml("/nonexistent/path/catalog.yaml")


def test_xlsx_unknown_sheet_raises() -> None:
    config = CatalogConfig(
        primary_key="sku",
        sources=[
            SourceConfig(
                type="xlsx",
                path=str(SAMPLE_XLSX),
                sheet="NonexistentSheet",
            )
        ],
    )
    with pytest.raises(ValueError, match="Sheet 'NonexistentSheet'"):
        load_catalog(config)


def test_catalog_row_attributes_carry_join_data() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    pkc = next(r for r in catalog if r.key == "PKC")
    assert pkc.attributes["from_price"] == 380.0
    assert pkc.attributes["discount_pct"] == 0.0


# v0.3.6 — alias harvesting on duplicate primary keys ----------------------


def test_duplicate_primary_keys_collect_prior_names_into_aliases(tmp_path) -> None:
    """The real etraveli source has 33 IATA codes appearing multiple times
    under different names ('Bali' / 'Denpasar Bali' both → DPS). The loader
    must keep the LAST row's data as canonical and accumulate every prior
    name as an alias so keyword generation can broaden match coverage."""
    src = tmp_path / "duplicates.json"
    src.write_text(json.dumps([
        {"sku": "DPS", "name": "Bali"},
        {"sku": "DPS", "name": "Denpasar Bali"},
        {"sku": "DPS", "name": "Bali Denpasar"},
        {"sku": "RUN", "name": "St. Denis De La Reunion"},
        {"sku": "RUN", "name": "Reunion"},
        {"sku": "NCE", "name": "Nice"},  # no duplicates — empty aliases
    ]), encoding="utf-8")
    config = CatalogConfig(
        primary_key="sku",
        name_column="name",
        sources=[SourceConfig(type="json", path=str(src))],
    )
    catalog = load_catalog(config)
    by_sku = {r.key: r for r in catalog}
    # DPS: canonical name is the LAST row ('Bali Denpasar'); aliases preserve
    # the prior rows IN ORDER ('Bali' first, then 'Denpasar Bali').
    dps = by_sku["DPS"]
    assert dps.name == "Bali Denpasar"
    assert dps.aliases == ["Bali", "Denpasar Bali"]
    # RUN: 1 alias.
    run = by_sku["RUN"]
    assert run.name == "Reunion"
    assert run.aliases == ["St. Denis De La Reunion"]
    # NCE: never duplicated → empty alias list.
    assert by_sku["NCE"].aliases == []


def test_alias_dedup_against_canonical_name_and_each_other(tmp_path) -> None:
    """Aliases that equal the canonical name (case-insensitive) or each
    other should be deduplicated so we don't pollute downstream keyword
    generation with repeats."""
    src = tmp_path / "dup_aliases.json"
    src.write_text(json.dumps([
        {"sku": "NYC", "name": "New York City"},
        {"sku": "NYC", "name": "New York"},
        {"sku": "NYC", "name": "new york"},  # case-only dup of prior
        {"sku": "NYC", "name": "NYC"},  # canonical match → dropped from aliases
    ]), encoding="utf-8")
    config = CatalogConfig(
        primary_key="sku",
        name_column="name",
        sources=[SourceConfig(type="json", path=str(src))],
    )
    catalog = load_catalog(config)
    nyc = next(r for r in catalog if r.key == "NYC")
    assert nyc.name == "NYC"
    # Only the unique non-canonical prior names survive.
    assert nyc.aliases == ["New York City", "New York"]
