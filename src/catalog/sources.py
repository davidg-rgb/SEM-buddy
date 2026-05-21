"""Source readers — XLSX, CSV, JSON.

Each reader returns a `list[dict[str, Any]]` (row dicts keyed by the *raw*
column names). The loader is responsible for renaming columns and joining.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_path(path: str, base_dir: Path | None) -> Path:
    p = Path(path)
    if not p.is_absolute() and base_dir is not None:
        p = base_dir / p
    return p


def read_xlsx(path: str, sheet: str, base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read an Excel sheet into a list of {column_name: value} dicts.

    Uses openpyxl in read-only mode for memory-efficient streaming of large
    sheets. The first row is treated as the header.
    """
    import openpyxl  # type: ignore

    resolved = _resolve_path(path, base_dir)
    if not resolved.exists():
        raise FileNotFoundError(f"XLSX source not found: {resolved}")

    wb = openpyxl.load_workbook(resolved, read_only=True, data_only=True)
    try:
        if sheet not in wb.sheetnames:
            raise ValueError(
                f"Sheet '{sheet}' not found in {resolved.name}. "
                f"Available: {wb.sheetnames}"
            )
        ws = wb[sheet]
        iterator = ws.iter_rows(values_only=True)
        try:
            header_row = next(iterator)
        except StopIteration:
            return []
        headers = [str(h).strip() if h is not None else "" for h in header_row]
        rows: list[dict[str, Any]] = []
        for raw in iterator:
            if not raw or all(v is None for v in raw):
                continue
            row: dict[str, Any] = {}
            for idx, val in enumerate(raw):
                if idx >= len(headers) or not headers[idx]:
                    continue
                row[headers[idx]] = val
            rows.append(row)
        return rows
    finally:
        wb.close()


def read_csv(path: str, encoding: str = "utf-8", base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read a CSV into row dicts. Encoding defaults to UTF-8 (BOM tolerated)."""
    resolved = _resolve_path(path, base_dir)
    if not resolved.exists():
        raise FileNotFoundError(f"CSV source not found: {resolved}")

    # utf-8-sig strips BOM if present without affecting plain UTF-8 files
    effective_encoding = "utf-8-sig" if encoding.lower() in ("utf-8", "utf8") else encoding
    with resolved.open("r", encoding=effective_encoding, newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
    return rows


def read_json(path: str, base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read a JSON array of objects into row dicts."""
    resolved = _resolve_path(path, base_dir)
    if not resolved.exists():
        raise FileNotFoundError(f"JSON source not found: {resolved}")
    with resolved.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"JSON source {resolved} must be a top-level array of objects")
    rows = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"JSON source {resolved} contains non-object item: {item!r}")
        rows.append(item)
    return rows
