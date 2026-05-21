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


class TestGeoStructuredCampaigns:
    """Geo-structured path: each campaign owns its single geo, ads reflect it."""

    @pytest.fixture
    def multi_geo_client(self) -> ClientProfile:
        return ClientProfile(
            business_name="Etraveli",
            website_url="https://etraveli.com",
            industry="travel",
            products_services=["flight booking"],  # 1 service → geo-structured path
            geographic_targets=[
                GeoTarget(name="Stockholm", google_geo_id=2724072, radius_km=50.0),
                GeoTarget(name="Göteborg", google_geo_id=2711533, radius_km=40.0),
                GeoTarget(name="Malmö", google_geo_id=2692969, radius_km=30.0),
            ],
            monthly_budget_sek=50000,
        )

    def test_one_campaign_per_geo(self, multi_geo_client: ClientProfile):
        keyword_groups = {"flights": [{"text": "billiga flyg"}]}
        plan = build_campaigns(multi_geo_client, keyword_groups)
        assert len(plan.campaigns) == 3
        names = {c.name for c in plan.campaigns}
        assert "Etraveli - Stockholm" in names
        assert "Etraveli - Göteborg" in names
        assert "Etraveli - Malmö" in names

    def test_each_campaign_targets_only_its_geo(self, multi_geo_client: ClientProfile):
        """Regression test for the geo_targets overwrite bug.

        Before the fix, every campaign in geo-structured mode received ALL
        client.geographic_targets, defeating the per-location strategy.
        """
        keyword_groups = {"flights": [{"text": "billiga flyg"}]}
        plan = build_campaigns(multi_geo_client, keyword_groups)
        for campaign in plan.campaigns:
            assert len(campaign.geo_targets) == 1, (
                f"Campaign '{campaign.name}' has {len(campaign.geo_targets)} geo_targets, "
                f"expected exactly 1 (geo-structured)"
            )
            # Campaign name ends with the geo name
            assert campaign.name.endswith(campaign.geo_targets[0].name)

    def test_radius_preserved_through_pipeline(self, multi_geo_client: ClientProfile):
        keyword_groups = {"flights": [{"text": "billiga flyg"}]}
        plan = build_campaigns(multi_geo_client, keyword_groups)
        stockholm_campaign = next(c for c in plan.campaigns if "Stockholm" in c.name)
        assert stockholm_campaign.geo_targets[0].radius_km == 50.0

    def test_each_campaign_has_geo_specific_headlines(self, multi_geo_client: ClientProfile, monkeypatch):
        """Regression test for the ad-copy geo bug.

        Before the fix, every geo-structured campaign generated headlines
        using client.geographic_targets[0] — so the Göteborg campaign
        produced "Stockholm" headlines.
        """
        monkeypatch.setenv("SEM_DISABLE_LLM", "1")
        keyword_groups = {"flights": [{"text": "billiga flyg"}]}
        plan = build_campaigns(multi_geo_client, keyword_groups)

        for campaign in plan.campaigns:
            geo_name = campaign.geo_targets[0].name
            headlines = [h.text for h in campaign.ad_groups[0].ads[0].headlines]
            # Every campaign should include at least one headline mentioning its own geo
            assert any(geo_name in h for h in headlines), (
                f"Campaign '{campaign.name}' has no headline mentioning {geo_name}. "
                f"Headlines: {headlines}"
            )
            # And no headline should mention the OTHER geos (cross-contamination)
            other_geos = [g.name for g in multi_geo_client.geographic_targets if g.name != geo_name]
            for other in other_geos:
                assert not any(other in h for h in headlines), (
                    f"Campaign '{campaign.name}' contains headline mentioning {other}: "
                    f"{headlines}"
                )

    def test_service_structured_campaigns_inherit_all_geos(self, sample_client: ClientProfile):
        """Service-structured path (the non-geo branch) still merges the full geo list.

        sample_client has only 1 geo + multiple services → service-structured.
        """
        keyword_groups = {
            "rörmokare": [{"text": "rörmokare"}],
            "vvs_jour": [{"text": "vvs"}],
        }
        plan = build_campaigns(sample_client, keyword_groups)
        for campaign in plan.campaigns:
            assert campaign.geo_targets == sample_client.geographic_targets


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
