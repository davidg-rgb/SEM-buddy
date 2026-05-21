"""Tests for the `__sku__` diff type added to `apply_proposal`.

The `__sku__` field on a CleaningDiff renames a row's primary key. It must:
  - Successfully rename a row's key when no collision exists.
  - Drop the source row (keeping the existing target) when the target key
    already exists in the catalog.
  - Let subsequent diffs in the same proposal reference the NEW key.
"""

from __future__ import annotations

from src.catalog import (
    Catalog,
    CatalogConfig,
    CatalogRow,
    SourceConfig,
)
from src.catalog.cleaners import (
    CleaningDiff,
    CleaningProposal,
    apply_proposal,
)


def _make_catalog(rows: list[tuple[str, str, dict]]) -> Catalog:
    config = CatalogConfig(
        primary_key="sku",
        sources=[SourceConfig(type="csv", path="unused.csv")],
    )
    return Catalog(
        config=config,
        rows=[CatalogRow(key=k, name=n, attributes=dict(a)) for k, n, a in rows],
    )


# --- basic rename behaviour -------------------------------------------------


def test_sku_diff_renames_row_key() -> None:
    catalog = _make_catalog([
        ("Louisville", "SDF", {"from_price": None}),
    ])
    proposal = CleaningProposal(diffs=[
        CleaningDiff(
            row_key="Louisville",
            field="__sku__",
            before="Louisville",
            after="SDF",
            reason="Fix inversion",
        ),
    ])
    cleaned = apply_proposal(catalog, proposal)

    assert len(cleaned) == 1
    assert cleaned.rows[0].key == "SDF"
    # Name and attributes carried over unchanged
    assert cleaned.rows[0].name == "SDF"
    assert cleaned.rows[0].attributes["from_price"] is None


def test_sku_diff_does_not_mutate_source_catalog() -> None:
    catalog = _make_catalog([("Louisville", "SDF", {})])
    proposal = CleaningProposal(diffs=[
        CleaningDiff(
            row_key="Louisville",
            field="__sku__",
            before="Louisville",
            after="SDF",
            reason="Fix inversion",
        ),
    ])
    apply_proposal(catalog, proposal)
    # Source untouched
    assert catalog.rows[0].key == "Louisville"


# --- subsequent diffs referencing the NEW key -------------------------------


def test_sku_diff_then_name_diff_on_new_key() -> None:
    """A `__sku__` rename followed by a name diff keyed by the NEW sku
    should successfully update both fields on the renamed row."""
    catalog = _make_catalog([
        ("Louisville", "SDF", {"from_price": None}),
    ])
    proposal = CleaningProposal(diffs=[
        CleaningDiff(
            row_key="Louisville",
            field="__sku__",
            before="Louisville",
            after="SDF",
            reason="Fix inversion",
        ),
        CleaningDiff(
            row_key="SDF",  # NEW key
            field="name",
            before="SDF",
            after="Louisville, KY",
            reason="Restore customer-facing name",
        ),
        CleaningDiff(
            row_key="SDF",  # NEW key
            field="from_price",
            before=None,
            after=200,
            reason="Placeholder until live pricing wired up",
        ),
    ])
    cleaned = apply_proposal(catalog, proposal)

    assert len(cleaned) == 1
    row = cleaned.rows[0]
    assert row.key == "SDF"
    assert row.name == "Louisville, KY"
    assert row.attributes["from_price"] == 200


def test_sku_diff_with_name_diff_on_old_key_still_applies() -> None:
    """A name diff keyed by the OLD key (alongside the __sku__ rename)
    should also apply — operators sometimes write proposals that way."""
    catalog = _make_catalog([
        ("Louisville", "SDF", {}),
    ])
    proposal = CleaningProposal(diffs=[
        CleaningDiff(
            row_key="Louisville",
            field="__sku__",
            before="Louisville",
            after="SDF",
            reason="Fix inversion",
        ),
        CleaningDiff(
            row_key="Louisville",  # OLD key
            field="name",
            before="SDF",
            after="Louisville, KY",
            reason="Restore name",
        ),
    ])
    cleaned = apply_proposal(catalog, proposal)
    assert cleaned.rows[0].key == "SDF"
    assert cleaned.rows[0].name == "Louisville, KY"


# --- collision handling -----------------------------------------------------


def test_sku_diff_collision_drops_source_keeps_target() -> None:
    """If the rename target already exists, drop the source row entirely.
    The existing target row's data is canonical and must NOT be overwritten."""
    catalog = _make_catalog([
        ("NY", "New York City", {"from_price": None, "discount_pct": 0.0}),
        ("NYC", "New York City", {"from_price": 452.0, "discount_pct": 0.24}),
    ])
    proposal = CleaningProposal(diffs=[
        CleaningDiff(
            row_key="NY",
            field="__sku__",
            before="NY",
            after="NYC",
            reason="Canonicalise to IATA metro code",
        ),
    ])
    cleaned = apply_proposal(catalog, proposal)

    assert len(cleaned) == 1
    row = cleaned.rows[0]
    assert row.key == "NYC"
    # Target's data wins — price is preserved
    assert row.attributes["from_price"] == 452.0
    assert row.attributes["discount_pct"] == 0.24


def test_sku_diff_no_collision_when_target_is_self() -> None:
    """A `__sku__` rename where before == after is a no-op (not a collision)."""
    catalog = _make_catalog([("NYC", "New York City", {})])
    proposal = CleaningProposal(diffs=[
        CleaningDiff(
            row_key="NYC",
            field="__sku__",
            before="NYC",
            after="NYC",
            reason="Idempotent rename",
        ),
    ])
    cleaned = apply_proposal(catalog, proposal)
    assert len(cleaned) == 1
    assert cleaned.rows[0].key == "NYC"


# --- co-existence with existing __key__ and name diffs ---------------------


def test_existing_name_diff_still_works() -> None:
    """Regression: the new `__sku__` handling must not break the existing
    `name` and `__key__` diff types."""
    catalog = _make_catalog([
        ("bkk", "Bangkok`", {}),  # lowercase IATA + backtick
    ])
    proposal = CleaningProposal(diffs=[
        CleaningDiff(
            row_key="bkk",
            field="__key__",
            before="bkk",
            after="BKK",
            reason="Uppercased IATA",
        ),
        CleaningDiff(
            row_key="bkk",
            field="name",
            before="Bangkok`",
            after="Bangkok",
            reason="Backtick stripped",
        ),
    ])
    cleaned = apply_proposal(catalog, proposal)
    assert cleaned.rows[0].key == "BKK"
    assert cleaned.rows[0].name == "Bangkok"


def test_multiple_sku_renames_in_one_proposal() -> None:
    """Three independent renames in one proposal should all apply."""
    catalog = _make_catalog([
        ("NY", "New York City", {"from_price": None}),
        ("NYC", "NYC", {"from_price": 452.0}),
        ("LON-Heathrow", "London", {"from_price": None}),
        ("Louisville", "SDF", {"from_price": None}),
    ])
    proposal = CleaningProposal(diffs=[
        CleaningDiff(row_key="NY", field="__sku__", before="NY", after="NYC", reason="r"),
        CleaningDiff(row_key="LON-Heathrow", field="__sku__", before="LON-Heathrow", after="LHR", reason="r"),
        CleaningDiff(row_key="Louisville", field="__sku__", before="Louisville", after="SDF", reason="r"),
        CleaningDiff(row_key="LHR", field="name", before="London", after="London Heathrow", reason="r"),
        CleaningDiff(row_key="SDF", field="name", before="SDF", after="Louisville, KY", reason="r"),
    ])
    cleaned = apply_proposal(catalog, proposal)

    by_key = {r.key: r for r in cleaned}
    # NY collapsed into NYC, LON-Heathrow renamed to LHR, Louisville to SDF
    assert set(by_key) == {"NYC", "LHR", "SDF"}
    assert by_key["NYC"].attributes["from_price"] == 452.0   # target wins
    assert by_key["LHR"].name == "London Heathrow"
    assert by_key["SDF"].name == "Louisville, KY"
