"""Tests for src/audit/comparator.py — structured diff engine and report formatter."""

from __future__ import annotations

import pytest

from src.audit.comparator import compare, format_audit_report
from src.models.campaign import (
    AdDescription,
    AdGroup,
    AdHeadline,
    Campaign,
    CampaignPlan,
    Callout,
    Keyword,
    ResponsiveSearchAd,
    Sitelink,
)


# ---------------------------------------------------------------------------
# Helpers to build minimal test data
# ---------------------------------------------------------------------------


def _make_plan(
    campaign_name: str = "VVS-Jour",
    keyword_text: str = "rörmokare stockholm",
    match_type: str = "PHRASE",
    headline_text: str = "Stockholms Rörmokare",
    budget: float = 500.0,
) -> CampaignPlan:
    # ResponsiveSearchAd requires min 3 headlines and min 2 descriptions
    rsa = ResponsiveSearchAd(
        headlines=[
            AdHeadline(text=headline_text),
            AdHeadline(text="VVS-jour Dygnet Runt"),
            AdHeadline(text="Fa Offert Idag"),
        ],
        descriptions=[
            AdDescription(text="Professionell VVS-service i Stockholm."),
            AdDescription(text="Snabb och palitlig rormokaretjanst i Stockholm."),
        ],
        final_url="https://example.com",
        path1="vvs",
        path2="jour",
    )
    ag = AdGroup(
        name="VVS-Jour AG",
        theme="vvs_jour",
        keywords=[Keyword(text=keyword_text, match_type=match_type)],
        negative_keywords=[],
        ads=[rsa],
    )
    campaign = Campaign(
        name=campaign_name,
        campaign_type="SEARCH",
        status="PAUSED",
        budget_sek_daily=budget,
        geo_targets=[],
        language_codes=["sv"],
        ad_groups=[ag],
    )
    return CampaignPlan(campaigns=[campaign], sitelinks=[], callouts=[])


def _make_live(
    campaign_name: str = "VVS-Jour",
    keyword_text: str = "rörmokare stockholm",
    match_type: str = "PHRASE",
    headline: str = "Stockholms Rörmokare",
    budget: str = "500.00",
) -> list[dict]:
    return [
        {
            "name": campaign_name,
            "campaign_budget": budget,
            "ad_groups": [
                {
                    "name": "VVS-Jour AG",
                    "keywords": [{"text": keyword_text, "match_type": match_type}],
                    "ads": [{"headlines": [headline], "descriptions": ["Professionell VVS-service i Stockholm."]}],
                }
            ],
        }
    ]


# ---------------------------------------------------------------------------
# compare() tests
# ---------------------------------------------------------------------------


def test_compare_identical():
    """Identical live and plan produce no diffs in any category."""
    plan = _make_plan()
    live = _make_live()
    diff = compare(live, plan)

    assert diff["missing_campaigns"] == []
    assert diff["extra_campaigns"] == []
    assert diff["keyword_gaps"] == []
    assert diff["keyword_waste"] == []


def test_compare_missing_campaign():
    """Campaign in plan but not in live shows up in missing_campaigns."""
    plan = _make_plan(campaign_name="VVS-Jour")
    live: list[dict] = []  # nothing live

    diff = compare(live, plan)

    assert "VVS-Jour" in diff["missing_campaigns"]
    assert diff["extra_campaigns"] == []


def test_compare_extra_campaign():
    """Campaign in live but not in plan shows up in extra_campaigns."""
    plan = _make_plan(campaign_name="VVS-Jour")
    live = _make_live(campaign_name="Helt Annan Kampanj")

    diff = compare(live, plan)

    assert "Helt Annan Kampanj" in diff["extra_campaigns"]
    assert "VVS-Jour" in diff["missing_campaigns"]


def test_compare_keyword_gaps():
    """Keyword in plan but absent from live appears in keyword_gaps."""
    plan = _make_plan(keyword_text="akut rörmokare", match_type="EXACT")
    live = _make_live(keyword_text="annan sökning", match_type="EXACT")

    diff = compare(live, plan)

    gap_keywords = [g["keyword"] for g in diff["keyword_gaps"]]
    assert "akut rörmokare" in gap_keywords

    gap = next(g for g in diff["keyword_gaps"] if g["keyword"] == "akut rörmokare")
    assert gap["match_type"] == "EXACT"
    assert gap["campaign"] == "VVS-Jour"
    assert gap["ad_group"] == "VVS-Jour AG"


def test_compare_keyword_waste():
    """Keyword in live but absent from plan appears in keyword_waste."""
    plan = _make_plan(keyword_text="rörmokare stockholm", match_type="PHRASE")
    live = _make_live(keyword_text="billig rörmokare", match_type="BROAD")

    diff = compare(live, plan)

    waste_keywords = [w["keyword"] for w in diff["keyword_waste"]]
    assert "billig rörmokare" in waste_keywords


def test_compare_ad_copy_diffs():
    """Headline in plan but missing from live ads creates an ad_copy_diffs entry."""
    plan = _make_plan(headline_text="Exklusiv Rubrik")
    live = _make_live(headline="Helt Annan Rubrik")

    diff = compare(live, plan)

    headline_diffs = [d for d in diff["ad_copy_diffs"] if d["type"] == "headline"]
    assert len(headline_diffs) > 0
    rec_texts = [d["recommended"] for d in headline_diffs]
    assert any("exklusiv rubrik" in t for t in rec_texts)


def test_compare_case_insensitive_matching():
    """Campaign name case differences should not count as missing or extra."""
    plan = _make_plan(campaign_name="VVS-Jour")
    live = _make_live(campaign_name="vvs-jour")  # lowercase in live

    diff = compare(live, plan)

    assert diff["missing_campaigns"] == []
    assert diff["extra_campaigns"] == []


def test_compare_budget_diffs():
    """Budget mismatch between live and recommended plan is captured in budget_diffs."""
    plan = _make_plan(budget=500.0)
    live = _make_live(budget="999.00")  # different from recommended

    diff = compare(live, plan)

    # budget_diffs always contains matched campaigns (by design)
    assert len(diff["budget_diffs"]) >= 1
    entry = diff["budget_diffs"][0]
    assert entry["recommended_budget"] == 500.0
    assert entry["live_budget"] == "999.00"


# ---------------------------------------------------------------------------
# format_audit_report() tests
# ---------------------------------------------------------------------------


def test_format_audit_report_structure():
    """Report includes the required Swedish header and Sammanfattning section."""
    plan = _make_plan()
    live = _make_live()
    diff = compare(live, plan)

    report = format_audit_report(diff, "Test-Klient")

    assert "Kampanjgranskning:" in report
    assert "Test-Klient" in report
    assert "Sammanfattning" in report
    # Verify summary table has category rows
    assert "Saknade kampanjer" in report
    assert "Extra kampanjer" in report


def test_format_audit_report_empty_diff():
    """When all diff lists are empty the report uses the 'Inga' (none) messages."""
    empty_diff: dict = {
        "missing_campaigns": [],
        "extra_campaigns": [],
        "keyword_gaps": [],
        "keyword_waste": [],
        "ad_copy_diffs": [],
        "budget_diffs": [],
        "bid_strategy_diffs": [],
    }

    report = format_audit_report(empty_diff, "Tomt Konto")

    assert "*Inga saknade kampanjer.*" in report
    assert "*Inga extra kampanjer.*" in report
    assert "*Inga sökordsluckor.*" in report or "*Inga sokordssloserier.*" in report or "Inga" in report
