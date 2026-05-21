"""CSV exporter tests for the v0.3 additions: promotions (08), lead forms (09),
bid schedules (10), and the new bid_modifier column on ad groups."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pandas as pd

from src.generators.campaign_builder import (
    build_campaigns_from_catalog,
    catalog_row_to_product,
)
from src.generators.csv_exporter import export_campaign_plan
from src.catalog import load_catalog_from_yaml
from src.models.campaign import BidSchedule
from src.models.catalog import CampaignBuildConfig
from src.models.client import ClientProfile


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_YAML = FIXTURE_DIR / "catalog_sample.yaml"


def _plan_with_extensions(monkeypatch, *, with_schedules: bool = False):
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    bid_rules = []
    if with_schedules:
        # First-match-wins, so the schedule rule must come first for products
        # that would also satisfy the immediate rules.
        bid_rules.append(
            {
                "if": "discount_pct >= 0.20",
                "during": {"start": "2026-06-01", "end": "2026-08-31"},
                "then": {"modifier": 2.0, "reason": "Summer sale"},
            }
        )
    bid_rules += [
        {"if": "discount_pct >= 0.30", "then": {"modifier": 1.5}},
        {"if": "discount_pct >= 0.15", "then": {"modifier": 1.25}},
    ]
    cfg = CampaignBuildConfig(
        structure_mode="sku",
        campaign_name_template="Flightnetwork - All Destinations",
        ad_group_name_template="{name} ({sku})",
        language="en",
        url_templates={
            "primary": "https://www.flightnetwork.com/from/google/rf/destination?to={sku}&text={N}"
        },
        keyword_templates=["flights to {name}", "{name} flights"],
        keyword_match_types=["PHRASE"],
        promotion_enabled=True,
        bid_rules=bid_rules,
    )
    client = ClientProfile(
        business_name="Flightnetwork",
        website_url="https://www.flightnetwork.com/",
        industry="travel",
        language="en",
        monthly_budget_sek=200_000,
    )
    lead_form_cfg = {
        "form_name": "Get Flight Quote",
        "headline": "Get cheap flights",
        "description": "Enter your details — we'll send you the best fares.",
        "business_name": "Flightnetwork",
        "cta": "GET_QUOTE",
        "privacy_url": "https://www.flightnetwork.com/privacy",
        "fields": ["EMAIL", "FIRST_NAME", "PHONE_NUMBER"],
    }
    plan = build_campaigns_from_catalog(
        client, products, cfg,
        lead_form_config=lead_form_cfg,
        promotion_start_date=date(2026, 5, 20),
        promotion_end_date=date(2026, 6, 30),
    )
    return plan


def test_promotions_csv_written(tmp_path: Path, monkeypatch) -> None:
    plan = _plan_with_extensions(monkeypatch)
    out_dir = export_campaign_plan(plan, str(tmp_path))
    promo_path = Path(out_dir) / "08_promotions.csv"
    assert promo_path.exists()
    df = pd.read_csv(promo_path, encoding="utf-8-sig")
    # 6 discounted products in the fixture
    assert len(df) == 6
    # Editor-required columns
    expected_cols = {
        "Campaign", "Ad group", "Discount modifier", "Percent off",
        "Promotion start date", "Promotion end date", "Final URL",
        "Language", "Status",
    }
    assert expected_cols <= set(df.columns)
    # Percent column has integers (rendered, not floats with trailing zeros)
    pct_values = df["Percent off"].astype(str).tolist()
    assert any(v == "25" for v in pct_values)  # BKK
    assert any(v == "40" for v in pct_values)  # WMI


def test_lead_forms_csv_written(tmp_path: Path, monkeypatch) -> None:
    plan = _plan_with_extensions(monkeypatch)
    out_dir = export_campaign_plan(plan, str(tmp_path))
    lf_path = Path(out_dir) / "09_lead_forms.csv"
    assert lf_path.exists()
    df = pd.read_csv(lf_path, encoding="utf-8-sig")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["Form name"] == "Get Flight Quote"
    assert row["Form fields"] == "EMAIL; FIRST_NAME; PHONE_NUMBER"
    assert row["Privacy URL"].startswith("https://")


def test_bid_schedules_csv_written(tmp_path: Path, monkeypatch) -> None:
    plan = _plan_with_extensions(monkeypatch, with_schedules=True)
    out_dir = export_campaign_plan(plan, str(tmp_path))
    bs_path = Path(out_dir) / "10_bid_schedules.csv"
    assert bs_path.exists()
    df = pd.read_csv(bs_path, encoding="utf-8-sig")
    assert len(df) >= 1
    assert "Bid modifier" in df.columns
    assert "Reason" in df.columns
    # Plus-sign formatted bid modifier for 2.0x = +100.0%
    assert any(v == "+100.0%" for v in df["Bid modifier"])


def test_ad_group_csv_has_bid_modifier_column(tmp_path: Path, monkeypatch) -> None:
    plan = _plan_with_extensions(monkeypatch)
    out_dir = export_campaign_plan(plan, str(tmp_path))
    ag_path = Path(out_dir) / "02_ad_groups.csv"
    assert ag_path.exists()
    df = pd.read_csv(ag_path, encoding="utf-8-sig")
    assert "Bid modifier" in df.columns
    # WMI has 0.40 -> rule 1 -> 1.5 -> +50.0%
    wmi = df[df["Ad Group"].str.endswith("(WMI)")]
    assert len(wmi) == 1
    assert wmi.iloc[0]["Bid modifier"] == "+50.0%"


def test_keywords_csv_uses_per_ad_group_final_url(tmp_path: Path, monkeypatch) -> None:
    plan = _plan_with_extensions(monkeypatch)
    out_dir = export_campaign_plan(plan, str(tmp_path))
    kw_path = Path(out_dir) / "03_keywords.csv"
    df = pd.read_csv(kw_path, encoding="utf-8-sig")
    # Each ad group's keywords share that ag's URL
    bkk_kws = df[df["Ad Group"].str.endswith("(BKK)")]
    nyc_kws = df[df["Ad Group"].str.endswith("(NYC)")]
    bkk_urls = set(bkk_kws["Final URL"].unique())
    nyc_urls = set(nyc_kws["Final URL"].unique())
    assert all("to=BKK" in u for u in bkk_urls)
    assert all("to=NYC" in u for u in nyc_urls)
    assert bkk_urls != nyc_urls


def test_promotions_csv_url_is_templated_not_default(tmp_path: Path, monkeypatch) -> None:
    plan = _plan_with_extensions(monkeypatch)
    out_dir = export_campaign_plan(plan, str(tmp_path))
    df = pd.read_csv(Path(out_dir) / "08_promotions.csv", encoding="utf-8-sig")
    # Every URL contains a real SKU code
    for url in df["Final URL"]:
        assert "to=" in url
        # SKU should be 3 letters at that point
        sku = url.split("to=")[1].split("&")[0]
        assert len(sku) == 3


def test_readme_lists_all_files(tmp_path: Path, monkeypatch) -> None:
    plan = _plan_with_extensions(monkeypatch, with_schedules=True)
    out_dir = export_campaign_plan(plan, str(tmp_path))
    readme = (Path(out_dir) / "README_import_order.txt").read_text(encoding="utf-8")
    for fname in [
        "01_campaigns", "02_ad_groups", "03_keywords", "04_responsive_search_ads",
        "05_negative_keywords", "06_sitelinks", "07_callouts",
        "08_promotions", "09_lead_forms", "10_bid_schedules",
    ]:
        assert fname in readme


def test_promotion_exactly_one_of_validators() -> None:
    """The Pydantic model enforces exactly one of percent_off / money_amount_off."""
    import pytest
    from src.models.campaign import PromotionExtension
    with pytest.raises(ValueError, match="Exactly one of"):
        PromotionExtension(
            campaign_name="C", ad_group_name="A",
            percent_off=10, money_amount_off=5,
            final_url="https://x.com",
        )
    with pytest.raises(ValueError, match="Exactly one of"):
        PromotionExtension(
            campaign_name="C", ad_group_name="A",
            final_url="https://x.com",
        )
