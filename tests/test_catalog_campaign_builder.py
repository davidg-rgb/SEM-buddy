"""End-to-end tests for the SKU-mode campaign builder (C3 + integration)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.catalog import load_catalog_from_yaml
from src.generators.campaign_builder import (
    build_campaigns_from_catalog,
    catalog_row_to_product,
)
from src.models.catalog import CampaignBuildConfig, Product
from src.models.client import ClientProfile


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_YAML = FIXTURE_DIR / "catalog_sample.yaml"


def _en_client() -> ClientProfile:
    return ClientProfile(
        business_name="Flightnetwork",
        website_url="https://www.flightnetwork.com/",
        industry="travel",
        products_services=["cheap flights"],
        language="en",
        monthly_budget_sek=200000,
    )


def _load_products() -> list[Product]:
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    return [catalog_row_to_product(row) for row in catalog]


def _build_config() -> CampaignBuildConfig:
    return CampaignBuildConfig(
        structure_mode="sku",
        campaign_name_template="Flightnetwork - All Destinations",
        ad_group_name_template="{name} ({sku})",
        language="en",
        url_templates={
            "primary": "https://www.flightnetwork.com/from/google/rf/destination?to={sku}&text={N}"
        },
        text_n_range=(1, 5),
        keyword_templates=[
            "flights to {name}",
            "cheap flights to {name}",
            "{name} flights",
            "{sku} flights",
        ],
        keyword_match_types=["PHRASE", "EXACT"],
        promotion_enabled=True,
        promotion_attribute="discount_pct",
        bid_rules=[
            {"if": "discount_pct >= 0.30", "then": {"modifier": 1.5}},
            {"if": "discount_pct >= 0.15", "then": {"modifier": 1.25}},
            {"if": "from_price < 100", "then": {"modifier": 1.1}},
        ],
    )


def test_catalog_build_produces_one_campaign_with_one_ag_per_product(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())
    assert len(plan.campaigns) == 1
    campaign = plan.campaigns[0]
    assert campaign.name == "Flightnetwork - All Destinations"
    assert len(campaign.ad_groups) == len(products)
    # Each ad group name matches the template
    names = [ag.name for ag in campaign.ad_groups]
    assert "Bangkok, Thailand (BKK)" in names


def test_each_ad_group_has_unique_final_url_with_n_rotation(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())
    urls = []
    for ag in plan.campaigns[0].ad_groups:
        rsa = ag.ads[0]
        urls.append(str(rsa.final_url))
    # All URLs contain the SKU and the N parameter
    assert all("text=" in u for u in urls)
    # Different SKUs in URLs
    assert any("to=BKK" in u for u in urls)
    assert any("to=NYC" in u for u in urls)


def test_bid_rules_applied_per_ad_group(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())
    # Find ad group for WMI (discount=0.40 -> rule 1 -> 1.5)
    wmi_ag = next(ag for ag in plan.campaigns[0].ad_groups if ag.name.endswith("(WMI)"))
    assert wmi_ag.bid_modifier == 1.5
    # BKK has 0.25 -> rule 2 -> 1.25
    bkk_ag = next(ag for ag in plan.campaigns[0].ad_groups if ag.name.endswith("(BKK)"))
    assert bkk_ag.bid_modifier == 1.25
    # MVY has discount 0.0 but from_price 95 < 100 -> rule 3 -> 1.1
    mvy_ag = next(ag for ag in plan.campaigns[0].ad_groups if ag.name.endswith("(MVY)"))
    assert mvy_ag.bid_modifier == 1.1
    # NYC has no discount and no price -> no rule fires -> 1.0
    nyc_ag = next(ag for ag in plan.campaigns[0].ad_groups if ag.name.endswith("(NYC)"))
    assert nyc_ag.bid_modifier == 1.0


def test_seasonality_overlay_fires_in_window_falls_back_out_of_window(monkeypatch) -> None:
    """End-to-end check of the seasonality system the brief asks for.

    Same case.yaml, same products — running the builder with `today` inside
    the SUMMER_SALE window should boost the bid modifier on high-discount
    ad groups; running with `today` after the window should drop them back
    to the base ladder. The 10_bid_schedules.csv (plan.bid_schedules) stays
    populated either way for documentation.
    """
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    cfg = _build_config()
    # Replace the toy bid_rules from _build_config with a real overlay+base
    # ladder so we can prove the active-window behavior.
    cfg.bid_rules = [
        {
            "if": "discount_pct >= 0.30",
            "during": {"start": "2026-05-20", "end": "2026-08-31"},
            "then": {"modifier": 2.5, "reason": "SUMMER_SALE overlay 30%+"},
        },
        {"if": "discount_pct >= 0.30", "then": {"modifier": 1.5, "reason": "Base 30%+"}},
        {"if": "discount_pct >= 0.15", "then": {"modifier": 1.25, "reason": "Base 15%+"}},
    ]

    # Inside the window — overlay fires; high-discount ad groups get 2.5×.
    plan_in = build_campaigns_from_catalog(
        _en_client(), products, cfg, today=date(2026, 6, 15),
    )
    wmi_in = next(ag for ag in plan_in.campaigns[0].ad_groups if ag.name.endswith("(WMI)"))
    # WMI has discount=0.40 → matches the 30%+ overlay → 2.5×
    assert wmi_in.bid_modifier == 2.5
    # Schedule documented for WMI
    wmi_schedules = [s for s in plan_in.bid_schedules if s.ad_group_name.endswith("(WMI)")]
    assert len(wmi_schedules) == 1
    assert wmi_schedules[0].reason == "SUMMER_SALE overlay 30%+"

    # Outside the window — overlay drops out; same product gets base 1.5×.
    # Schedule is STILL recorded for documentation.
    plan_out = build_campaigns_from_catalog(
        _en_client(), products, cfg, today=date(2026, 11, 15),
    )
    wmi_out = next(ag for ag in plan_out.campaigns[0].ad_groups if ag.name.endswith("(WMI)"))
    assert wmi_out.bid_modifier == 1.5
    wmi_schedules_out = [s for s in plan_out.bid_schedules if s.ad_group_name.endswith("(WMI)")]
    assert len(wmi_schedules_out) == 1
    assert wmi_schedules_out[0].reason == "SUMMER_SALE overlay 30%+"


def test_promotion_extensions_emitted_for_discounted_products(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())
    # 6 of the 10 products have discount > 0 in the fixture
    assert len(plan.promotions) == 6
    for promo in plan.promotions:
        assert promo.percent_off is not None and promo.percent_off > 0
        # URLs are templated, not the campaign default
        assert "to=" in str(promo.final_url)


def test_keywords_generated_from_templates(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())
    bkk_ag = next(ag for ag in plan.campaigns[0].ad_groups if ag.name.endswith("(BKK)"))
    kw_texts = {k.text for k in bkk_ag.keywords}
    # 4 templates × 2 match types — Google Ads-illegal characters (commas) get
    # sanitized out, so "Bangkok, Thailand" becomes "Bangkok Thailand".
    assert "flights to Bangkok Thailand" in kw_texts
    assert "BKK flights" in kw_texts


def test_lead_form_emitted_when_config_provided(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
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
        _en_client(), products, _build_config(),
        lead_form_config=lead_form_cfg,
    )
    assert len(plan.lead_forms) == 1
    lf = plan.lead_forms[0]
    assert lf.campaign_name == "Flightnetwork - All Destinations"
    assert lf.form_name == "Get Flight Quote"
    assert lf.fields == ["EMAIL", "FIRST_NAME", "PHONE_NUMBER"]


def test_partition_by_attribute_creates_multiple_campaigns(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    # Synthesise a region attribute
    region_map = {"BKK": "asia", "TYO": "asia", "SIN": "asia",
                  "SFO": "americas", "NYC": "americas", "MVY": "americas", "EZE": "americas",
                  "PKC": "europe", "WMI": "europe", "REK": "europe"}
    products = [p.model_copy(update={"attributes": {**p.attributes, "region": region_map.get(p.sku, "other")}}) for p in products]

    cfg = _build_config()
    cfg = cfg.model_copy(update={
        "partition_by_attribute": "region",
        "campaign_name_template": "Flightnetwork - {partition}",
    })
    plan = build_campaigns_from_catalog(_en_client(), products, cfg)
    assert len(plan.campaigns) == 3
    names = sorted(c.name for c in plan.campaigns)
    assert names == [
        "Flightnetwork - americas",
        "Flightnetwork - asia",
        "Flightnetwork - europe",
    ]


def test_no_promotion_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    cfg = _build_config()
    cfg = cfg.model_copy(update={"promotion_enabled": False})
    plan = build_campaigns_from_catalog(_en_client(), products, cfg)
    assert plan.promotions == []


def test_bid_schedules_appear_with_during_clause(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    products = _load_products()
    cfg = _build_config()
    cfg = cfg.model_copy(update={
        "bid_rules": [
            {
                "if": "discount_pct >= 0.20",
                "during": {"start": "2026-06-01", "end": "2026-08-31"},
                "then": {"modifier": 2.0, "reason": "Summer sale"},
            },
        ],
    })
    plan = build_campaigns_from_catalog(_en_client(), products, cfg)
    # Products with >=0.20 discount in the fixture: BKK(0.25), WMI(0.40), TYO(0.30), SIN(0.20)
    schedules_skus = {s.ad_group_name.split("(")[-1].rstrip(")") for s in plan.bid_schedules}
    assert {"BKK", "WMI", "TYO", "SIN"} <= schedules_skus


def test_legacy_build_campaigns_still_works(monkeypatch) -> None:
    """Sanity: the non-catalog code path must still work."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    from src.generators.campaign_builder import build_campaigns
    client = ClientProfile(
        business_name="Testbolaget",
        website_url="https://test.se/",
        industry="bygg_renovering",
        products_services=["renovering"],
        language="sv",
        monthly_budget_sek=20000,
    )
    keyword_groups = {"renovering": [{"text": "renovering stockholm", "match_type": "PHRASE"}]}
    plan = build_campaigns(client, keyword_groups)
    assert len(plan.campaigns) >= 1
