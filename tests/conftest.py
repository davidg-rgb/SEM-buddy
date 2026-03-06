"""Common test fixtures for SEM Master test suite."""

import tempfile
from pathlib import Path

import pytest

from src.models.client import ClientProfile, GeoTarget, TargetAudience, CampaignGoal
from src.models.campaign import (
    Campaign, AdGroup, Keyword, ResponsiveSearchAd,
    AdHeadline, AdDescription, Sitelink, Callout, CampaignPlan,
)


@pytest.fixture
def sample_client() -> ClientProfile:
    """A minimal ClientProfile with Swedish text for testing."""
    return ClientProfile(
        business_name="Stockholms Rörmokare",
        website_url="https://www.stockholmsrormokare.se",
        industry="vvs",
        products_services=["rörmokare", "VVS-jour", "värmepump"],
        target_audience=TargetAudience(
            locations=["Stockholm"],
            b2b_or_b2c="b2c",
        ),
        geographic_targets=[
            GeoTarget(name="Stockholm", google_geo_id=1012728),
        ],
        monthly_budget_sek=15000,
        campaign_goals=[CampaignGoal(goal_type="leads", priority=1)],
        brand_voice="Professionell och pålitlig",
        language="sv",
    )


@pytest.fixture
def sample_campaign_plan(sample_client: ClientProfile) -> CampaignPlan:
    """A CampaignPlan with real Swedish ad text for testing."""
    url = str(sample_client.website_url)

    rsa = ResponsiveSearchAd(
        headlines=[
            AdHeadline(text="Stockholms Rörmokare"),
            AdHeadline(text="VVS-jour Dygnet Runt"),
            AdHeadline(text="Få Offert Idag"),
            AdHeadline(text="Rörmokare Stockholm"),
        ],
        descriptions=[
            AdDescription(text="Professionell VVS-service i Stockholm. Ring oss för en kostnadsfri offert idag."),
            AdDescription(text="Snabb och pålitlig rörmokare. Vi hjälper dig med allt inom VVS."),
        ],
        final_url=url,
        path1="vvs",
        path2="jour",
    )

    ad_group = AdGroup(
        name="VVS-Jour",
        theme="vvs_jour",
        keywords=[
            Keyword(text="rörmokare stockholm", match_type="PHRASE"),
            Keyword(text="VVS-jour", match_type="EXACT"),
            Keyword(text="akut rörmokare", match_type="BROAD"),
        ],
        negative_keywords=["jobb", "utbildning", "gratis"],
        ads=[rsa],
    )

    campaign = Campaign(
        name="Stockholms Rörmokare - VVS-Jour",
        campaign_type="SEARCH",
        status="PAUSED",
        budget_sek_daily=500.0,
        geo_targets=sample_client.geographic_targets,
        language_codes=["sv"],
        ad_groups=[ad_group],
    )

    sitelinks = [
        Sitelink(text="Om Oss", desc1="Läs mer om oss", desc2="Vår historia", final_url=f"{url}/om-oss"),
        Sitelink(text="Kontakta Oss", desc1="Ring eller maila", desc2="Snabb återkomst", final_url=f"{url}/kontakt"),
        Sitelink(text="Våra Tjänster", desc1="Se hela utbudet", desc2="VVS-lösningar", final_url=f"{url}/tjanster"),
        Sitelink(text="Få Offert", desc1="Kostnadsfri offert", desc2="Svar inom 24h", final_url=f"{url}/offert"),
    ]

    callouts = [
        Callout(text="Fri Offert"),
        Callout(text="Snabb Service"),
        Callout(text="Lokalt Företag"),
        Callout(text="Nöjd Kund-Garanti"),
    ]

    return CampaignPlan(
        campaigns=[campaign],
        sitelinks=sitelinks,
        callouts=callouts,
    )


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> str:
    """Temporary output directory for file export tests."""
    out = tmp_path / "output"
    out.mkdir()
    return str(out)
