"""Pydantic models for catalog configuration and loaded data.

A `Catalog` is the in-memory result of loading one or more `Source`s described
in YAML and joining them on a primary key. Each row is keyed by `primary_key`
and carries an arbitrary `attributes` dict. Downstream code (campaign builder,
keyword/ad generators, promotion extension generator) consumes `CatalogRow`s.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class JoinKey(BaseModel):
    """How to join a secondary source into the primary."""

    source_column: str  # column in this source's raw data
    target_column: str  # column already in the primary catalog (after rename)


class SourceConfig(BaseModel):
    """One data source feeding the catalog."""

    type: Literal["xlsx", "csv", "json"]
    path: str
    sheet: str | None = None  # xlsx only
    join_key: JoinKey | None = None  # None ⇒ this source is the primary
    columns: dict[str, str] = Field(
        default_factory=dict,
        description="Map of catalog column name → raw source column name.",
    )
    encoding: str = "utf-8"  # csv only

    @model_validator(mode="after")
    def _xlsx_needs_sheet(self) -> SourceConfig:
        if self.type == "xlsx" and not self.sheet:
            raise ValueError("xlsx source requires 'sheet'")
        return self


class CatalogConfig(BaseModel):
    """Top-level catalog config (loaded from `catalog.yaml`)."""

    schema_version: int = 1
    primary_key: str = "sku"
    sources: list[SourceConfig] = Field(min_length=1)
    defaults: dict[str, Any] = Field(default_factory=dict)
    required_columns: list[str] = Field(
        default_factory=list,
        description="Columns that must be present in every row after joining.",
    )
    name_column: str | None = Field(
        default=None,
        description="If set, this column becomes the catalog row's display name.",
    )

    @model_validator(mode="after")
    def _first_source_is_primary(self) -> CatalogConfig:
        if self.sources[0].join_key is not None:
            raise ValueError(
                "First source must be the primary (no join_key). "
                "Reorder sources or remove join_key from the first entry."
            )
        return self


class CatalogRow(BaseModel):
    """One row of normalized catalog data.

    `key` is the value of the primary_key for this row (e.g. an IATA code).
    `name` is the human-readable label (optional, derived from `name_column`).
    `attributes` is everything else (price, discount, region, etc.).
    """

    key: str
    name: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    def get(self, attr: str, default: Any = None) -> Any:
        if attr == "key" or attr == self_primary_key_alias_for_get(attr):
            return self.key
        if attr == "name":
            return self.name
        return self.attributes.get(attr, default)


def self_primary_key_alias_for_get(attr: str) -> str:
    """Trivial helper so `.get('sku')` works even when key is named 'sku' in config.

    The CatalogRow doesn't carry the primary_key field name (just its value),
    so we let any non-'name'/'attributes' lookup fall through to attributes.
    """
    return attr


class Catalog(BaseModel):
    """A loaded catalog: ordered list of rows + the config that built it."""

    config: CatalogConfig
    rows: list[CatalogRow] = Field(default_factory=list)

    def __iter__(self):  # type: ignore[override]
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> CatalogRow:
        return self.rows[idx]

    def partition_by(self, attribute: str) -> dict[Any, list[CatalogRow]]:
        """Bucket rows by the given attribute value (used for partition_by_attribute)."""
        buckets: dict[Any, list[CatalogRow]] = {}
        for row in self.rows:
            val = row.attributes.get(attribute)
            buckets.setdefault(val, []).append(row)
        return buckets
