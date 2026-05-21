"""Tests for catalog validators + cleaners (C2)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.catalog import load_catalog_from_yaml
from src.catalog.cleaners import (
    CleaningProposal,
    apply_proposal,
    clean_destination_name,
    clean_with_llm,
    load_proposal,
    propose_cleanings,
    proposal_to_markdown,
    write_cleaning_artifacts,
)
from src.catalog.validators import (
    CatalogSchema,
    ValidationIssue,
    issues_to_markdown,
    validate_catalog,
    validate_iata_code,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_YAML = FIXTURE_DIR / "catalog_sample.yaml"


# --- IATA validator ---------------------------------------------------------

def test_validate_iata_code_accepts_uppercase_three_letters() -> None:
    assert validate_iata_code("BKK") is True
    assert validate_iata_code("PKC") is True


def test_validate_iata_code_rejects_invalid() -> None:
    assert validate_iata_code("bk") is False
    assert validate_iata_code("BKKK") is False
    assert validate_iata_code("BK1") is False
    assert validate_iata_code("bkk") is False  # lowercase not valid by spec
    assert validate_iata_code(None) is False
    assert validate_iata_code("") is False


# --- clean_destination_name -------------------------------------------------

def test_clean_destination_name_backtick_to_apostrophe() -> None:
    assert clean_destination_name("Mazow`iecki, Poland") == "Mazow'iecki, Poland"


def test_clean_destination_name_smart_quotes() -> None:
    assert clean_destination_name("It’s a test") == "It's a test"
    assert clean_destination_name("‘Quoted’") == "'Quoted'"


def test_clean_destination_name_whitespace_collapse() -> None:
    assert clean_destination_name("Foo   Bar  ") == "Foo Bar"


def test_clean_destination_name_handles_non_string() -> None:
    assert clean_destination_name(None) is None  # type: ignore[arg-type]


# --- propose_cleanings ------------------------------------------------------

def test_propose_cleanings_finds_backtick_in_fixture() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    proposal = propose_cleanings(catalog)
    # WMI has Mazow`iecki
    backtick_diffs = [d for d in proposal.diffs if d.row_key == "WMI" and d.field == "name"]
    assert len(backtick_diffs) == 1
    assert "`" not in backtick_diffs[0].after
    assert "'" in backtick_diffs[0].after


def test_propose_cleanings_skips_clean_rows() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    proposal = propose_cleanings(catalog)
    bkk_diffs = [d for d in proposal.diffs if d.row_key == "BKK"]
    # Bangkok name is already clean and code is uppercase
    assert bkk_diffs == []


# --- apply_proposal ---------------------------------------------------------

def test_apply_proposal_does_not_mutate_source() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    wmi_before = next(r for r in catalog if r.key == "WMI").name
    proposal = propose_cleanings(catalog)
    cleaned = apply_proposal(catalog, proposal)
    # Original catalog row still has backtick
    wmi_after_source = next(r for r in catalog if r.key == "WMI").name
    assert wmi_after_source == wmi_before
    assert "`" in wmi_after_source
    # Cleaned catalog has apostrophe
    wmi_cleaned = next(r for r in cleaned if r.key == "WMI").name
    assert "`" not in wmi_cleaned
    assert "'" in wmi_cleaned


def test_apply_proposal_empty_returns_copy() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    cleaned = apply_proposal(catalog, CleaningProposal())
    assert len(cleaned) == len(catalog)
    assert all(c.key == o.key for c, o in zip(cleaned.rows, catalog.rows))


# --- proposal_to_markdown / artifacts ---------------------------------------

def test_proposal_to_markdown_empty() -> None:
    md = proposal_to_markdown(CleaningProposal())
    assert "No changes" in md


def test_proposal_to_markdown_non_empty() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    proposal = propose_cleanings(catalog)
    md = proposal_to_markdown(proposal)
    assert "| Row key |" in md
    assert "WMI" in md


def test_write_and_load_artifacts(tmp_path: Path) -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    proposal = propose_cleanings(catalog)
    json_path, md_path = write_cleaning_artifacts(proposal, tmp_path)
    assert json_path.exists() and md_path.exists()
    reloaded = load_proposal(json_path)
    assert reloaded.diffs == proposal.diffs


# --- validate_catalog -------------------------------------------------------

def test_validate_catalog_iata_pattern_flags_lowercase() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    # Inject a bad row directly for the test
    catalog.rows[0] = catalog.rows[0].model_copy(update={"key": "bkk"})
    schema = CatalogSchema(primary_key_pattern=r"^[A-Z]{3}$")
    report = validate_catalog(catalog, schema)
    bad = [i for i in report.issues if i.code == "invalid_primary_key"]
    assert len(bad) == 1
    assert bad[0].row_key == "bkk"


def test_validate_catalog_backtick_warning() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    report = validate_catalog(catalog)
    backtick_warns = [i for i in report.issues if i.code == "suspicious_char"]
    assert any(i.row_key == "WMI" for i in backtick_warns)


def test_validate_catalog_required_attributes() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    schema = CatalogSchema(required_attributes=["from_price"])
    report = validate_catalog(catalog, schema)
    # NYC + EZE have None from_price -> 2 errors
    missing = [i for i in report.issues if i.code == "missing_required"]
    assert len(missing) >= 2
    assert {i.row_key for i in missing} >= {"NYC", "EZE"}


def test_validate_catalog_summary_format() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    schema = CatalogSchema(primary_key_pattern=r"^[A-Z]{3}$")
    report = validate_catalog(catalog, schema)
    summary = report.summary()
    assert "10 rows" in summary
    assert "errors" in summary
    assert "warnings" in summary


def test_validate_catalog_duplicate_key_detection() -> None:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    catalog.rows.append(catalog.rows[0].model_copy())  # duplicate BKK
    report = validate_catalog(catalog)
    dupes = [i for i in report.issues if i.code == "duplicate_key"]
    assert len(dupes) == 1


def test_issues_to_markdown_empty() -> None:
    assert "No issues" in issues_to_markdown([])


def test_issues_to_markdown_renders() -> None:
    issue = ValidationIssue(
        row_key="X", severity="error", field="f", code="c", message="hello | world"
    )
    md = issues_to_markdown([issue])
    assert "hello \\| world" in md  # pipe escaped


# --- LLM cleaning (mocked) --------------------------------------------------

def test_clean_with_llm_disabled_returns_empty(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    proposal = clean_with_llm(catalog)
    assert proposal.is_empty


def test_clean_with_llm_applies_fixes_when_mocked(monkeypatch) -> None:
    monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
    # Pretend claude is on PATH and returns a fix for the Vinyard typo
    with patch("src.catalog.cleaners.shutil.which", return_value="/fake/claude"), patch(
        "src.catalog.cleaners._invoke_claude",
        return_value={
            "fixes": [
                {
                    "row_key": "MVY",
                    "field": "name",
                    "after": "Vineyard Haven, USA",
                    "reason": "Typo: Vinyard -> Vineyard",
                }
            ]
        },
    ):
        catalog = load_catalog_from_yaml(SAMPLE_YAML)
        proposal = clean_with_llm(catalog)
    assert len(proposal.diffs) == 1
    diff = proposal.diffs[0]
    assert diff.row_key == "MVY"
    assert diff.after == "Vineyard Haven, USA"
    assert diff.reason.startswith("LLM-suggested")


def test_clean_with_llm_subprocess_failure_returns_empty(monkeypatch) -> None:
    monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
    with patch("src.catalog.cleaners.shutil.which", return_value="/fake/claude"), patch(
        "src.catalog.cleaners._invoke_claude", return_value=None
    ):
        catalog = load_catalog_from_yaml(SAMPLE_YAML)
        proposal = clean_with_llm(catalog)
    assert proposal.is_empty
