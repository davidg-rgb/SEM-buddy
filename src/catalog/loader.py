"""Catalog loader.

Reads sources (XLSX/CSV/JSON), renames columns according to each source's
column map, and joins secondary sources into the primary using `join_key`.

The first source is always the primary; subsequent sources contribute extra
columns matched by their `join_key`. Missing values get filled from
`CatalogConfig.defaults`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.catalog.models import (
    Catalog,
    CatalogConfig,
    CatalogRow,
    SourceConfig,
)
from src.catalog.sources import read_csv, read_json, read_xlsx

logger = logging.getLogger(__name__)


def _read_source(source: SourceConfig, base_dir: Path | None) -> list[dict[str, Any]]:
    if source.type == "xlsx":
        assert source.sheet is not None  # validator enforces
        return read_xlsx(source.path, source.sheet, base_dir=base_dir)
    if source.type == "csv":
        return read_csv(source.path, encoding=source.encoding, base_dir=base_dir)
    if source.type == "json":
        return read_json(source.path, base_dir=base_dir)
    raise ValueError(f"Unknown source type: {source.type}")


def _rename_columns(
    raw_rows: list[dict[str, Any]],
    columns_map: dict[str, str],
    source_label: str,
) -> list[dict[str, Any]]:
    """Apply the catalog-column-name → raw-column-name map to each row.

    Returns rows keyed by the catalog column names. Raw columns not in the
    map are dropped (keeps the catalog narrow and predictable).
    """
    if not columns_map:
        # No remap requested — keep everything as-is
        return [dict(r) for r in raw_rows]

    renamed: list[dict[str, Any]] = []
    missing_warned: set[str] = set()
    for row in raw_rows:
        out: dict[str, Any] = {}
        for catalog_col, raw_col in columns_map.items():
            if raw_col not in row:
                if raw_col not in missing_warned:
                    logger.warning(
                        "Source '%s' missing raw column '%s' (mapped to '%s'); "
                        "remaining rows will use the default if any.",
                        source_label, raw_col, catalog_col,
                    )
                    missing_warned.add(raw_col)
                continue
            out[catalog_col] = row[raw_col]
        renamed.append(out)
    return renamed


def _validate_required(
    rows: list[dict[str, Any]], required: list[str], primary_source_label: str
) -> None:
    if not required:
        return
    if not rows:
        raise ValueError(
            f"Primary source '{primary_source_label}' produced zero rows — "
            "check the path, sheet name, and column map."
        )
    sample = rows[0]
    missing = [c for c in required if c not in sample]
    if missing:
        raise ValueError(
            f"Primary source '{primary_source_label}' is missing required "
            f"columns {missing} (after renaming). "
            f"Available columns: {sorted(sample.keys())}"
        )


def load_catalog(config: CatalogConfig, base_dir: Path | None = None) -> Catalog:
    """Load and join all configured sources into a `Catalog`.

    `base_dir` is the directory paths in the config are resolved against;
    callers should pass the directory containing `catalog.yaml`.
    """
    if not config.sources:
        raise ValueError("CatalogConfig has no sources")

    # 1. Load primary
    primary = config.sources[0]
    primary_label = f"{primary.type}:{primary.path}" + (f"!{primary.sheet}" if primary.sheet else "")
    raw_primary = _read_source(primary, base_dir)
    primary_rows = _rename_columns(raw_primary, primary.columns, primary_label)
    _validate_required(primary_rows, config.required_columns, primary_label)

    pk = config.primary_key
    if not primary_rows:
        logger.warning("Primary source %s yielded zero rows", primary_label)
    elif pk not in primary_rows[0]:
        raise ValueError(
            f"Primary source '{primary_label}' missing primary_key column "
            f"'{pk}' after renaming. Map it via the source's `columns:` block."
        )

    # 2. Build index by primary key for efficient join
    index: dict[Any, dict[str, Any]] = {}
    for row in primary_rows:
        key_val = row.get(pk)
        if key_val is None or key_val == "":
            logger.warning("Skipping primary row with empty %s: %r", pk, row)
            continue
        key_str = str(key_val)
        if key_str in index:
            logger.warning("Duplicate primary key %r in %s — last wins", key_str, primary_label)
        index[key_str] = dict(row)

    # 3. Join secondaries
    for secondary in config.sources[1:]:
        sec_label = (
            f"{secondary.type}:{secondary.path}" + (f"!{secondary.sheet}" if secondary.sheet else "")
        )
        raw_sec = _read_source(secondary, base_dir)
        renamed = _rename_columns(raw_sec, secondary.columns, sec_label)
        jk = secondary.join_key
        assert jk is not None, "validator should prevent this"

        # The join_key.source_column is the column name *in the secondary's
        # raw data* — i.e. *before* renaming. After our rename pass it may or
        # may not still exist. Resolve it cleverly: prefer the raw name, fall
        # back to the target name, and finally try the first key in row.
        joined = 0
        skipped = 0
        for sec_row, raw_sec_row in zip(renamed, raw_sec):
            join_val = raw_sec_row.get(jk.source_column)
            if join_val is None:
                # Try renamed view
                join_val = sec_row.get(jk.target_column)
            if join_val is None or join_val == "":
                skipped += 1
                continue
            key_str = str(join_val)
            target_row = index.get(key_str)
            if target_row is None:
                skipped += 1
                continue
            for k, v in sec_row.items():
                if k == jk.target_column:
                    continue  # don't overwrite primary key
                target_row[k] = v
            joined += 1
        logger.info(
            "Joined %d rows from %s into primary (%d unmatched)",
            joined, sec_label, skipped,
        )

    # 4. Apply defaults + build CatalogRow list
    name_col = config.name_column
    rows_out: list[CatalogRow] = []
    for key_str, attrs in index.items():
        # Apply defaults for any missing key
        merged: dict[str, Any] = {**config.defaults, **attrs}
        # Pop the primary key (already on the row)
        merged.pop(pk, None)
        name_val: str | None = None
        if name_col and name_col in merged:
            raw_name = merged.pop(name_col)
            name_val = str(raw_name) if raw_name is not None else None
        rows_out.append(CatalogRow(key=key_str, name=name_val, attributes=merged))

    logger.info(
        "Loaded catalog: %d rows, %d sources, primary_key=%s",
        len(rows_out), len(config.sources), pk,
    )
    return Catalog(config=config, rows=rows_out)


def load_catalog_from_yaml(yaml_path: str | Path) -> Catalog:
    """Convenience wrapper: read `catalog.yaml`, build `CatalogConfig`, load.

    Paths inside the YAML are resolved relative to the YAML file's directory.
    """
    p = Path(yaml_path)
    if not p.exists():
        raise FileNotFoundError(f"catalog.yaml not found: {p}")
    with p.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"catalog.yaml must be a mapping, got {type(raw).__name__}")
    config = CatalogConfig.model_validate(raw)
    return load_catalog(config, base_dir=p.parent)
