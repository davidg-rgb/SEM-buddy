"""Catalog primitives: load arbitrary product catalogs (XLSX/CSV/JSON) and turn
them into Google Ads campaign structures.

This package is deliberately data-driven. Nothing in here mentions flights,
hotels, destinations, or IATA codes — the canonical first case (Flightnetwork)
is configured entirely through YAML, not code.
"""

from src.catalog.models import (
    Catalog,
    CatalogConfig,
    CatalogRow,
    JoinKey,
    SourceConfig,
)
from src.catalog.loader import load_catalog, load_catalog_from_yaml

__all__ = [
    "Catalog",
    "CatalogConfig",
    "CatalogRow",
    "JoinKey",
    "SourceConfig",
    "load_catalog",
    "load_catalog_from_yaml",
]
