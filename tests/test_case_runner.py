"""Tests for the case.yaml orchestrator (C15)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from src.cases.config import CaseConfig, load_case_config
from src.cases.runner import run_accept_fixes, run_case, run_clean


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_XLSX = FIXTURE_DIR / "catalog_sample.xlsx"
SAMPLE_CATALOG_YAML = FIXTURE_DIR / "catalog_sample.yaml"


CASE_YAML_TEMPLATE = """\
schema_version: 1
language: en
catalog: ./catalog.yaml
business_name: Flightnetwork
website_url: https://www.flightnetwork.com/
industry: travel
monthly_budget_sek: 200000
structure:
  mode: sku
  partition_by_attribute: null
  campaign_name_template: "Flightnetwork - All Destinations"
  ad_group_name_template: "{name} ({sku})"
url_templates:
  primary: "https://www.flightnetwork.com/from/google/rf/destination?to={sku}&text={N}"
  text_n_range: [1, 5]
keyword_templates:
  - "flights to {name}"
  - "cheap flights to {name}"
  - "{name} flights"
keyword_match_types: [PHRASE, EXACT]
ad_copy:
  pattern_pack: en
  interpolation_fields: [name, from_price, discount_pct]
extensions:
  promotions:
    enabled: true
    use_attribute: discount_pct
    money_currency: SEK
  lead_form:
    form_name: "Get Flight Quote"
    headline: "Get cheap flights"
    description: "Enter your details — we'll send you the best fares."
    business_name: "Flightnetwork"
    cta: "GET_QUOTE"
    privacy_url: "https://www.flightnetwork.com/privacy"
    fields: [EMAIL, FIRST_NAME, PHONE_NUMBER]
bid_rules:
  - if: "discount_pct >= 0.30"
    then: { modifier: 1.5 }
  - if: "discount_pct >= 0.15"
    then: { modifier: 1.25 }
"""


@pytest.fixture
def case_clients_dir(tmp_path, monkeypatch) -> Path:
    """Set up a temp clients/ directory with a sample case and catalog."""
    clients_dir = tmp_path / "clients"
    slug = "testcase"
    (clients_dir / slug).mkdir(parents=True)
    # Copy XLSX
    shutil.copyfile(SAMPLE_XLSX, clients_dir / slug / "catalog_sample.xlsx")
    # Copy + adjust catalog.yaml
    catalog_yaml_dst = clients_dir / slug / "catalog.yaml"
    catalog_yaml_dst.write_text(
        SAMPLE_CATALOG_YAML.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # Write case.yaml
    (clients_dir / slug / "case.yaml").write_text(CASE_YAML_TEMPLATE, encoding="utf-8")

    # Redirect CLIENTS_DIR
    monkeypatch.setattr("src.cases.runner.CLIENTS_DIR", clients_dir)
    monkeypatch.setattr("src.utils.config.CLIENTS_DIR", clients_dir)
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    return clients_dir


def test_load_case_config_round_trip(tmp_path) -> None:
    path = tmp_path / "case.yaml"
    path.write_text(CASE_YAML_TEMPLATE, encoding="utf-8")
    case = load_case_config(path)
    assert isinstance(case, CaseConfig)
    assert case.language == "en"
    assert case.structure.mode == "sku"
    assert case.extensions.promotions.enabled is True
    assert case.extensions.lead_form is not None
    assert case.extensions.lead_form.fields == ["EMAIL", "FIRST_NAME", "PHONE_NUMBER"]


def test_case_config_projects_onto_build_config(tmp_path) -> None:
    path = tmp_path / "case.yaml"
    path.write_text(CASE_YAML_TEMPLATE, encoding="utf-8")
    case = load_case_config(path)
    build = case.to_build_config()
    assert build.structure_mode == "sku"
    assert build.url_templates["primary"].startswith("https://")
    assert "flights to {name}" in build.keyword_templates
    assert build.promotion_enabled is True


def test_run_case_end_to_end(case_clients_dir: Path) -> None:
    result = run_case("testcase")
    assert result.products_count == 10
    assert result.campaign_count == 1
    assert result.ad_group_count == 10
    assert result.promotions_count == 6
    assert result.lead_forms_count == 1
    # Verify CSVs landed
    export_dir = result.export_dir
    for fname in [
        "01_campaigns.csv", "02_ad_groups.csv", "03_keywords.csv",
        "04_responsive_search_ads.csv", "06_sitelinks.csv",
        "07_callouts.csv", "08_promotions.csv", "09_lead_forms.csv",
    ]:
        assert (export_dir / fname).exists(), f"missing {fname}"
    # Promotion CSV is non-empty and has the right number of rows
    promo_df = pd.read_csv(export_dir / "08_promotions.csv", encoding="utf-8-sig")
    assert len(promo_df) == 6


def test_run_case_truncates_with_max_products(case_clients_dir: Path) -> None:
    result = run_case("testcase", max_products=3)
    assert result.products_count == 3
    assert result.ad_group_count == 3


def test_run_clean_and_accept_fixes(case_clients_dir: Path) -> None:
    json_path, md_path = run_clean("testcase")
    assert json_path.exists()
    assert md_path.exists()
    # Markdown should reference WMI (the backtick row)
    assert "WMI" in md_path.read_text(encoding="utf-8")

    accepted = run_accept_fixes("testcase")
    assert accepted.exists()

    # Subsequent run should apply diffs (WMI name no longer contains backtick)
    result = run_case("testcase")
    assert result.cleaning_applied is True
    rsa_df = pd.read_csv(result.export_dir / "04_responsive_search_ads.csv", encoding="utf-8-sig")
    # No headline or description should contain a backtick after cleaning
    all_text = " ".join(rsa_df.astype(str).values.flatten())
    assert "`" not in all_text


def test_run_case_missing_case_yaml_raises(case_clients_dir: Path) -> None:
    with pytest.raises(FileNotFoundError, match="case.yaml"):
        run_case("nonexistent")


def test_run_accept_fixes_without_proposal_raises(case_clients_dir: Path) -> None:
    with pytest.raises(FileNotFoundError, match="cleaning proposal"):
        run_accept_fixes("testcase")
