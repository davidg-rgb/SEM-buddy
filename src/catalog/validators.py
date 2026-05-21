"""Catalog validation — IATA codes, required columns, sanity checks.

Validation is purely diagnostic: it produces a `ValidationReport` describing
issues without mutating data. Cleaning is in `cleaners.py`.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from pydantic import BaseModel, Field

from src.catalog.models import Catalog, CatalogRow


IATA_CODE_RE = re.compile(r"^[A-Z]{3}$")
_IATA_RE = IATA_CODE_RE  # alias used by validate_iata_skus and downstream callers


def validate_iata_code(code: str | None) -> bool:
    """Return True if `code` is a syntactically valid 3-letter IATA code."""
    if not isinstance(code, str):
        return False
    return bool(IATA_CODE_RE.match(code))


def validate_iata_skus(catalog: Catalog) -> list[str]:
    """Scan the catalog and return a warning per row whose primary key is not
    a syntactically valid 3-letter IATA code.

    This is a diagnostic check — it never raises and never mutates data. Use
    it after `apply_proposal` to verify that catalog cleaning successfully
    canonicalised every SKU (NY→NYC, LON-Heathrow→LHR, Louisville→SDF, etc.).

    Returns an empty list when every SKU is IATA-valid.
    """
    warnings: list[str] = []
    for row in catalog.rows:
        if not _IATA_RE.match(row.key):
            warnings.append(
                f"SKU '{row.key}' (name='{row.name}') is not a valid "
                f"3-letter IATA code"
            )
    return warnings


class ValidationIssue(BaseModel):
    row_key: str
    severity: str  # error | warning | info
    field: str | None = None
    code: str  # machine-readable issue code
    message: str


class ValidationReport(BaseModel):
    issues: list[ValidationIssue] = Field(default_factory=list)
    total_rows: int = 0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def summary(self) -> str:
        n_err = sum(1 for i in self.issues if i.severity == "error")
        n_warn = sum(1 for i in self.issues if i.severity == "warning")
        return (
            f"Catalog validation: {self.total_rows} rows, "
            f"{n_err} errors, {n_warn} warnings"
        )


class CatalogSchema(BaseModel):
    """What a catalog needs to look like to be considered valid.

    Built independently of `CatalogConfig` so case authors can layer extra
    constraints (e.g. enforce IATA on the primary key for the etraveli case).
    """

    primary_key_pattern: str | None = None  # e.g. "^[A-Z]{3}$" for IATA
    required_attributes: list[str] = Field(default_factory=list)
    numeric_attributes: list[str] = Field(default_factory=list)
    max_name_length: int | None = None


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float))


def validate_catalog(catalog: Catalog, schema: CatalogSchema | None = None) -> ValidationReport:
    """Check the catalog against the schema; return a `ValidationReport`."""
    schema = schema or CatalogSchema()
    issues: list[ValidationIssue] = []

    pk_pattern = re.compile(schema.primary_key_pattern) if schema.primary_key_pattern else None

    seen_keys: set[str] = set()

    for row in catalog.rows:
        # 1. Primary key syntax
        if pk_pattern and not pk_pattern.match(row.key):
            issues.append(
                ValidationIssue(
                    row_key=row.key,
                    severity="error",
                    field=catalog.config.primary_key,
                    code="invalid_primary_key",
                    message=(
                        f"Primary key '{row.key}' does not match pattern "
                        f"{schema.primary_key_pattern!r}"
                    ),
                )
            )

        # 2. Duplicates
        if row.key in seen_keys:
            issues.append(
                ValidationIssue(
                    row_key=row.key,
                    severity="error",
                    field=catalog.config.primary_key,
                    code="duplicate_key",
                    message=f"Primary key {row.key!r} appears more than once",
                )
            )
        else:
            seen_keys.add(row.key)

        # 3. Required attributes
        for attr in schema.required_attributes:
            if attr == "name":
                val: Any = row.name
            else:
                val = row.attributes.get(attr)
            if val is None or (isinstance(val, str) and not val.strip()):
                issues.append(
                    ValidationIssue(
                        row_key=row.key,
                        severity="error",
                        field=attr,
                        code="missing_required",
                        message=f"Required attribute '{attr}' is missing or empty",
                    )
                )

        # 4. Numeric attributes
        for attr in schema.numeric_attributes:
            val = row.attributes.get(attr)
            if val is None:
                continue  # missing numerics are warnings only if also required
            if not _is_number(val):
                issues.append(
                    ValidationIssue(
                        row_key=row.key,
                        severity="error",
                        field=attr,
                        code="non_numeric",
                        message=f"Attribute '{attr}' must be numeric, got {type(val).__name__}: {val!r}",
                    )
                )

        # 5. Name length
        if schema.max_name_length and row.name and len(row.name) > schema.max_name_length:
            issues.append(
                ValidationIssue(
                    row_key=row.key,
                    severity="warning",
                    field="name",
                    code="name_too_long",
                    message=(
                        f"Name has {len(row.name)} chars, exceeds soft limit "
                        f"{schema.max_name_length}"
                    ),
                )
            )

        # 6. Suspicious characters in name (backticks, weird quotes)
        if row.name and "`" in row.name:
            issues.append(
                ValidationIssue(
                    row_key=row.key,
                    severity="warning",
                    field="name",
                    code="suspicious_char",
                    message=f"Name contains backtick — likely a misencoded apostrophe: {row.name!r}",
                )
            )

    # 7. Non-IATA primary keys (always warned, regardless of schema). This is
    # the catch-all that flags SKUs like 'NY', 'LON-Heathrow', 'Louisville'
    # that survived cleaning and should never ship to Google Ads as-is.
    for row in catalog.rows:
        if not _IATA_RE.match(row.key):
            issues.append(
                ValidationIssue(
                    row_key=row.key,
                    severity="warning",
                    field=catalog.config.primary_key,
                    code="non_iata_sku",
                    message=(
                        f"SKU '{row.key}' (name='{row.name}') is not a valid "
                        f"3-letter IATA code"
                    ),
                )
            )

    return ValidationReport(issues=issues, total_rows=len(catalog))


def issues_to_markdown(issues: Iterable[ValidationIssue]) -> str:
    """Render a list of issues as a human-readable Markdown table."""
    issues = list(issues)
    if not issues:
        return "_No issues._\n"
    lines = [
        "| Row key | Severity | Field | Code | Message |",
        "|---|---|---|---|---|",
    ]
    for i in issues:
        msg = i.message.replace("|", "\\|")
        lines.append(f"| {i.row_key} | {i.severity} | {i.field or '—'} | {i.code} | {msg} |")
    return "\n".join(lines) + "\n"


__all__ = [
    "IATA_CODE_RE",
    "_IATA_RE",
    "validate_iata_code",
    "validate_iata_skus",
    "ValidationIssue",
    "ValidationReport",
    "CatalogSchema",
    "validate_catalog",
    "issues_to_markdown",
]
