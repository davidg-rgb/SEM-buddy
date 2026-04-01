"""Tests for campaign builder -- structure, budget, bid strategy, extensions."""

import pytest

from src.generators.campaign_builder import (
    build_campaigns,
    _allocate_budget,
    _select_bid_strategy,
    _generate_extensions,
    ROT_INDUSTRIES,
)
from src.models.campaign import Campaign, CampaignPlan, AdGroup
from src.models.client import ClientProfile, GeoTarget, CampaignGoal


class TestBuildCampaigns:
    def test_creates_campaigns_from_keyword_groups(self, sample_client: ClientProfile):
        keyword_groups = {
            "rörmokare": [{"text": "rörmokare stockholm", "monthly_searches": 1200}],
            "vvs_jour": [{"text": "VVS-jour", "monthly_searches": 800}],
        }
        plan = build_campaigns(sample_client, keyword_groups)
        assert isinstance(plan, CampaignPlan)
        assert len(plan.campaigns) == 2

    def test_campaign_names_include_business(self, sample_client: ClientProfile):
        keyword_groups = {"rörmokare": [{"text": "rörmokare"}]}
        plan = build_campaigns(sample_client, keyword_groups)
        assert sample_client.business_name in plan.campaigns[0].name

    def test_all_campaigns_are_paused(self, sample_client: ClientProfile):
        keyword_groups = {"rörmokare": [{"text": "rörmokare"}]}
        plan = build_campaigns(sample_client, keyword_groups)
        for campaign in plan.campaigns:
            assert campaign.status == "PAUSED"

    def test_all_campaigns_have_swedish_language(self, sample_client: ClientProfile):
        keyword_groups = {"rörmokare": [{"text": "rörmokare"}]}
        plan = build_campaigns(sample_client, keyword_groups)
        for campaign in plan.campaigns:
            assert "sv" in campaign.language_codes

    def test_ad_groups_have_ads(self, sample_client: ClientProfile):
        keyword_groups = {"rörmokare": [{"text": "rörmokare"}]}
        plan = build_campaigns(sample_client, keyword_groups)
        for campaign in plan.campaigns:
            for ag in campaign.ad_groups:
                assert len(ag.ads) > 0, f"Ad group '{ag.name}' has no ads"

    def test_ad_groups_have_negative_keywords(self, sample_client: ClientProfile):
        keyword_groups = {"rörmokare": [{"text": "rörmokare"}]}
        plan = build_campaigns(sample_client, keyword_groups)
        for campaign in plan.campaigns:
            for ag in campaign.ad_groups:
                assert len(ag.negative_keywords) > 0


class TestAllocateBudget:
    def test_budget_sums_to_daily(self):
        campaigns = [
            Campaign(name="C1", budget_sek_daily=0, ad_groups=[
                AdGroup(name="AG1", theme="t1", keywords=[]),
            ]),
            Campaign(name="C2", budget_sek_daily=0, ad_groups=[
                AdGroup(name="AG2", theme="t2", keywords=[]),
            ]),
        ]
        result = _allocate_budget(campaigns, 30000)
        total_daily = sum(c.budget_sek_daily for c in result)
        assert abs(total_daily - 1000.0) < 1.0  # 30000/30 = 1000/day

    def test_empty_list_returns_empty(self):
        assert _allocate_budget([], 10000) == []


class TestSelectBidStrategy:
    def test_low_budget_gets_manual(self):
        assert _select_bid_strategy(3000, "leads") == "MANUAL_CPC"

    def test_leads_high_budget_gets_target_cpa(self):
        assert _select_bid_strategy(20000, "leads") == "TARGET_CPA"

    def test_traffic_gets_maximize_clicks(self):
        assert _select_bid_strategy(15000, "traffic") == "MAXIMIZE_CLICKS"

    def test_revenue_high_budget_gets_target_roas(self):
        assert _select_bid_strategy(25000, "revenue") == "TARGET_ROAS"

    def test_awareness_gets_impression_share(self):
        assert _select_bid_strategy(15000, "awareness") == "TARGET_IMPRESSION_SHARE"


class TestGenerateExtensions:
    def test_generates_sitelinks(self, sample_client: ClientProfile):
        sitelinks, callouts, snippets, call_ext = _generate_extensions(sample_client)
        assert len(sitelinks) >= 4

    def test_sitelink_texts_within_25_chars(self, sample_client: ClientProfile):
        sitelinks, _, _, _ = _generate_extensions(sample_client)
        for sl in sitelinks:
            assert len(sl.text) <= 25, f"Sitelink too long: '{sl.text}'"

    def test_callout_texts_within_25_chars(self, sample_client: ClientProfile):
        _, callouts, _, _ = _generate_extensions(sample_client)
        for co in callouts:
            assert len(co.text) <= 25, f"Callout too long: '{co.text}'"

    def test_rot_avdrag_for_vvs(self, sample_client: ClientProfile):
        # sample_client has industry="vvs"
        _, callouts, _, _ = _generate_extensions(sample_client)
        callout_texts = [c.text for c in callouts]
        assert "ROT-avdrag" in callout_texts

    def test_no_rot_for_dental(self, sample_client: ClientProfile):
        sample_client.industry = "tandvård"
        _, callouts, _, _ = _generate_extensions(sample_client)
        callout_texts = [c.text for c in callouts]
        assert "ROT-avdrag" not in callout_texts

    def test_snippets_include_services(self, sample_client: ClientProfile):
        _, _, snippets, _ = _generate_extensions(sample_client)
        service_snippet = next((s for s in snippets if s.header == "Tjänster"), None)
        assert service_snippet is not None
        assert len(service_snippet.values) > 0
