"""Deterministic + optional LLM-assisted catalog cleaning.

Workflow:
  1. `propose_cleanings(catalog)` produces a `CleaningProposal` of (row_key,
     field, before, after, reason) diffs. Source data is never mutated.
  2. The proposal is serialized to `cleaning_log.json` and a human-readable
     `cleaning_diff.md`.
  3. `apply_proposal(catalog, proposal)` returns a *new* catalog with the
     diffs applied (the CLI persists this as a fresh XLSX/CSV).

LLM-assisted typo correction is opt-in via `clean_with_llm` and gated on
`SEM_DISABLE_LLM` plus the presence of the `claude` CLI on PATH.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.catalog.models import Catalog, CatalogRow

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Deterministic rule-based cleaning
# ----------------------------------------------------------------------------


_SMART_QUOTE_MAP = {
    "‘": "'",  # left single quote
    "’": "'",  # right single quote
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "′": "'",  # prime
}


def clean_destination_name(name: str) -> str:
    """Normalize a destination/product name.

    - Backtick → apostrophe (common XLSX misencoding)
    - Smart quotes → straight quotes
    - Collapse internal whitespace
    - Strip leading/trailing whitespace
    - Normalize Unicode to NFC
    """
    if not isinstance(name, str):
        return name
    out = unicodedata.normalize("NFC", name)
    out = out.replace("`", "'")
    for smart, straight in _SMART_QUOTE_MAP.items():
        out = out.replace(smart, straight)
    out = re.sub(r"\s+", " ", out).strip()
    return out


class CleaningDiff(BaseModel):
    """One proposed change to a catalog row.

    `field` semantics:
      - `"name"`        — replace the row's display name with `after`
      - `"__key__"`     — uppercase / minor primary-key fix (deterministic)
      - `"__sku__"`     — rename the row's primary key (SKU). `before` must
                          equal the row's current key; `after` becomes the new
                          key. If `after` collides with an existing catalog
                          key, the source row is DROPPED in favour of the
                          existing target (no duplicates). Diffs that follow
                          this rename in the same proposal can reference
                          either the old or new key — `apply_proposal`
                          resolves both.
      - any other value — set `row.attributes[field] = after`
    """

    row_key: str
    field: str
    before: Any
    after: Any
    reason: str


class CleaningProposal(BaseModel):
    diffs: list[CleaningDiff] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.diffs


def propose_cleanings(catalog: Catalog) -> CleaningProposal:
    """Generate a deterministic cleaning proposal.

    Currently covers:
      - Name normalization (backticks, smart quotes, whitespace)
      - Uppercasing 3-letter primary keys (case insensitive IATA codes)

    Source data is not modified.
    """
    diffs: list[CleaningDiff] = []
    for row in catalog.rows:
        # Name cleaning
        if row.name is not None:
            cleaned_name = clean_destination_name(row.name)
            if cleaned_name != row.name:
                diffs.append(
                    CleaningDiff(
                        row_key=row.key,
                        field="name",
                        before=row.name,
                        after=cleaned_name,
                        reason="Normalized name (backtick/smart-quote/whitespace)",
                    )
                )
        # Uppercase 3-letter primary keys
        if len(row.key) == 3 and row.key.isascii() and row.key.isalpha() and not row.key.isupper():
            diffs.append(
                CleaningDiff(
                    row_key=row.key,
                    field="__key__",
                    before=row.key,
                    after=row.key.upper(),
                    reason="Uppercased IATA code",
                )
            )
    return CleaningProposal(diffs=diffs)


def apply_proposal(catalog: Catalog, proposal: CleaningProposal) -> Catalog:
    """Return a new catalog with proposal diffs applied. Source untouched.

    Supports a `__sku__` diff field that renames a row's primary key. If the
    target key collides with an existing catalog row, the source row is
    DROPPED (the existing target wins) — this is the deliberate behaviour
    when canonicalising non-IATA SKUs onto codes that already exist in the
    catalog (e.g. `NY` → `NYC` when `NYC` is already present with real data).

    Subsequent diffs in the same proposal that reference the NEW key are
    applied to the renamed row in the order they appear.
    """
    if proposal.is_empty:
        # Return a copy anyway for consistency
        return Catalog(config=catalog.config, rows=[r.model_copy() for r in catalog.rows])

    # Index diffs by (row_key, field). row_key may refer to either the
    # current key OR a post-rename key — both lookups are tried below.
    by_row: dict[str, dict[str, CleaningDiff]] = {}
    for diff in proposal.diffs:
        by_row.setdefault(diff.row_key, {})[diff.field] = diff

    existing_keys: set[str] = {r.key for r in catalog.rows}

    new_rows: list[CatalogRow] = []
    seen_new_keys: set[str] = set()
    for row in catalog.rows:
        # Resolve any rename first, so subsequent diffs can be keyed by the
        # NEW name.
        diffs_under_old = by_row.get(row.key, {})
        new_key = row.key
        new_name = row.name
        new_attrs = dict(row.attributes)

        sku_diff = diffs_under_old.get("__sku__")
        if sku_diff is not None:
            target = str(sku_diff.after)
            # Collision check: if the target key already lives on another
            # row in the source catalog, drop this row entirely. The
            # existing row's data is canonical.
            if target != row.key and target in existing_keys:
                logger.info(
                    "Dropping row %r in favour of existing %r during __sku__ rename",
                    row.key, target,
                )
                continue
            new_key = target

        # Apply remaining diffs keyed under the OLD row_key (excluding the
        # __sku__ diff already handled).
        for field, diff in diffs_under_old.items():
            if field == "__sku__":
                continue
            if field == "__key__":
                new_key = diff.after
            elif field == "name":
                new_name = diff.after
            else:
                new_attrs[field] = diff.after

        # Apply diffs keyed under the NEW (post-rename) key, if any.
        if new_key != row.key:
            diffs_under_new = by_row.get(new_key, {})
            for field, diff in diffs_under_new.items():
                if field == "__sku__":
                    # Avoid recursive renames in a single application
                    continue
                if field == "__key__":
                    new_key = diff.after
                elif field == "name":
                    new_name = diff.after
                else:
                    new_attrs[field] = diff.after

        if new_key in seen_new_keys:
            logger.warning(
                "__sku__ rename produced duplicate key %r — keeping first occurrence",
                new_key,
            )
            continue
        seen_new_keys.add(new_key)
        new_rows.append(CatalogRow(key=new_key, name=new_name, attributes=new_attrs))

    return Catalog(config=catalog.config, rows=new_rows)


def proposal_to_markdown(proposal: CleaningProposal) -> str:
    """Render a CleaningProposal as a reviewer-friendly diff table."""
    if proposal.is_empty:
        return "# Cleaning Proposal\n\n_No changes proposed._\n"
    lines = [
        "# Cleaning Proposal",
        "",
        f"Total diffs: **{len(proposal.diffs)}**",
        "",
        "| Row key | Field | Before | After | Reason |",
        "|---|---|---|---|---|",
    ]
    for d in proposal.diffs:
        before = str(d.before).replace("|", "\\|")
        after = str(d.after).replace("|", "\\|")
        reason = d.reason.replace("|", "\\|")
        lines.append(f"| {d.row_key} | {d.field} | `{before}` | `{after}` | {reason} |")
    if proposal.notes:
        lines.append("")
        lines.append("## Notes")
        for note in proposal.notes:
            lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def write_cleaning_artifacts(
    proposal: CleaningProposal, out_dir: Path
) -> tuple[Path, Path]:
    """Persist a CleaningProposal as JSON + Markdown. Returns (json_path, md_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "cleaning_log.json"
    md_path = out_dir / "cleaning_diff.md"
    json_path.write_text(
        json.dumps(proposal.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(proposal_to_markdown(proposal), encoding="utf-8")
    return json_path, md_path


def load_proposal(json_path: Path) -> CleaningProposal:
    """Read a previously-written cleaning_log.json back into a CleaningProposal."""
    with json_path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return CleaningProposal.model_validate(raw)


# ----------------------------------------------------------------------------
# LLM-assisted fuzzy cleaning (opt-in)
# ----------------------------------------------------------------------------


CLAUDE_TIMEOUT_SEC = 60
CLAUDE_MODEL = "haiku"
CLAUDE_MAX_BUDGET_USD = 0.20

_LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "row_key": {"type": "string"},
                    "field": {"type": "string"},
                    "after": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["row_key", "field", "after", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["fixes"],
    "additionalProperties": False,
}


def _llm_enabled() -> bool:
    if os.getenv("SEM_DISABLE_LLM") == "1":
        return False
    return shutil.which("claude") is not None


def _invoke_claude(prompt: str) -> dict[str, Any] | None:
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return None
    cmd = [
        claude_bin,
        "-p", prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(_LLM_SCHEMA),
        "--model", CLAUDE_MODEL,
        "--no-session-persistence",
        "--max-budget-usd", str(CLAUDE_MAX_BUDGET_USD),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SEC,
            encoding="utf-8",
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        logger.warning("claude CLI invocation failed: %s", exc)
        return None
    if result.returncode != 0:
        logger.warning("claude CLI exited %d: %s", result.returncode, (result.stderr or "")[:500])
        return None
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        logger.warning("claude CLI returned non-JSON envelope: %s", exc)
        return None
    if envelope.get("is_error"):
        return None
    inner = envelope.get("result")
    if isinstance(inner, dict):
        return inner
    if isinstance(inner, str):
        try:
            parsed = json.loads(inner)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def clean_with_llm(
    catalog: Catalog, fields: list[str] | None = None
) -> CleaningProposal:
    """Optional LLM-assisted typo correction.

    Asks the local `claude` CLI to suggest typo fixes for the listed `fields`
    (defaults to `["name"]`). Returns an empty proposal if the LLM is disabled
    or the call fails.

    Each fix is added as a `CleaningDiff` with reason "LLM-suggested" so the
    reviewer can audit before applying.
    """
    fields = fields or ["name"]
    if not _llm_enabled():
        logger.info("LLM cleaning disabled (SEM_DISABLE_LLM=1 or no claude CLI)")
        return CleaningProposal()

    # Build a compact prompt: row_key + each requested field
    rows_data = []
    for row in catalog.rows:
        item: dict[str, Any] = {"row_key": row.key}
        for f in fields:
            item[f] = row.name if f == "name" else row.attributes.get(f)
        rows_data.append(item)

    prompt = (
        "You are a data-cleaning assistant. Given the catalog rows below, "
        "identify typos, truncations, or mojibake in the listed fields and "
        "suggest corrected values. Only suggest fixes you are highly confident "
        "in. Do NOT change values that are already plausible.\n\n"
        f"Fields to inspect: {fields}\n\n"
        f"Rows:\n{json.dumps(rows_data, ensure_ascii=False)}\n\n"
        "Return JSON: {\"fixes\": [{\"row_key\": str, \"field\": str, "
        "\"after\": str, \"reason\": str}, ...]}"
    )

    payload = _invoke_claude(prompt)
    if not payload or not isinstance(payload.get("fixes"), list):
        return CleaningProposal()

    diffs: list[CleaningDiff] = []
    row_index = {r.key: r for r in catalog.rows}
    for fix in payload["fixes"]:
        if not isinstance(fix, dict):
            continue
        rk = fix.get("row_key")
        fld = fix.get("field")
        after = fix.get("after")
        if not (isinstance(rk, str) and isinstance(fld, str) and isinstance(after, str)):
            continue
        row = row_index.get(rk)
        if row is None:
            continue
        before = row.name if fld == "name" else row.attributes.get(fld)
        if after == before:
            continue
        diffs.append(
            CleaningDiff(
                row_key=rk,
                field=fld,
                before=before,
                after=after,
                reason="LLM-suggested: " + str(fix.get("reason", "")).strip(),
            )
        )
    proposal = CleaningProposal(diffs=diffs)
    if proposal.diffs:
        proposal.notes.append(f"LLM produced {len(proposal.diffs)} suggestions")
    return proposal


__all__ = [
    "clean_destination_name",
    "CleaningDiff",
    "CleaningProposal",
    "propose_cleanings",
    "apply_proposal",
    "proposal_to_markdown",
    "write_cleaning_artifacts",
    "load_proposal",
    "clean_with_llm",
]
