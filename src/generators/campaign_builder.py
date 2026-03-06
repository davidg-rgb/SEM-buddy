"""Full campaign structure builder for Google Ads."""

from __future__ import annotations

import logging
from typing import Literal

from src.models.campaign import (
    Campaign, AdGroup, Keyword, ResponsiveSearchAd,
    Sitelink, Callout, StructuredSnippet, CallExtension,
    CampaignPlan,
)
from src.models.client import ClientProfile
from src.models.research import DigitalPresence
from src.generators.ad_copy_generator import generate_rsa
from src.generators.keyword_generator import (
    generate_negative_keywords, assign_match_types,
)

logger = logging.getLogger(__name__)

# Home service industries eligible for ROT-avdrag
ROT_INDUSTRIES = [
    "bygg_renovering", "bygg", "renovering", "vvs", "el",
    "målare", "snickare", "takläggare", "golvläggning",
]

# Swedish business hours schedule
DEFAULT_AD_SCHEDULE = {
    "monday": {"start": "07:00", "end": "21:00"},
    "tuesday": {"start": "07:00", "end": "21:00"},
    "wednesday": {"start": "07:00", "end": "21:00"},
    "thursday": {"start": "07:00", "end": "21:00"},
    "friday": {"start": "07:00", "end": "21:00"},
    "saturday": {"start": "09:00", "end": "18:00"},
    "sunday": {"start": "10:00", "end": "17:00"},
}


def build_campaigns(
    client: ClientProfile,
    keyword_groups: dict[str, list[dict]],
    digital_presence: DigitalPresence | None = None,
) -> CampaignPlan:
    """Build a complete campaign structure from client profile and keyword groups.

    Decides between service-based or geo-based structuring based on the client profile.
    """
    # Decide structure strategy
    has_multiple_geos = len(client.geographic_targets) > 2
    has_multiple_services = len(client.products_services) > 3

    if has_multiple_geos and not has_multiple_services:
        campaigns = _structure_by_geo(client, keyword_groups)
    else:
        campaigns = _structure_by_service(client, keyword_groups)

    # Allocate budget
    campaigns = _allocate_budget(campaigns, client.monthly_budget_sek)

    # Apply ad schedule and bid strategy
    for campaign in campaigns:
        campaign.ad_schedule = _generate_ad_schedule()
        campaign.bid_strategy = _select_bid_strategy(
            int(campaign.budget_sek_daily * 30),
            client.campaign_goals[0].goal_type if client.campaign_goals else "traffic",
        )
        campaign.geo_targets = client.geographic_targets
        campaign.language_codes = ["sv"]

    # Generate extensions
    sitelinks, callouts, snippets, call_extensions = _generate_extensions(client)

    plan = CampaignPlan(
        campaigns=campaigns,
        sitelinks=sitelinks,
        callouts=callouts,
        snippets=snippets,
        call_extensions=call_extensions,
    )

    logger.info(
        "Built campaign plan: %d campaigns, %d ad groups total",
        len(campaigns),
        sum(len(c.ad_groups) for c in campaigns),
    )
    return plan


def _structure_by_service(
    client: ClientProfile,
    keyword_groups: dict[str, list[dict]],
) -> list[Campaign]:
    """Create one campaign per major service/keyword group."""
    campaigns: list[Campaign] = []
    website_url = str(client.website_url)

    for group_name, kw_dicts in keyword_groups.items():
        # Create keywords with match types based on budget
        typed_keywords = assign_match_types(kw_dicts, client.monthly_budget_sek)
        keywords = [
            Keyword(
                text=kw["text"],
                match_type=kw.get("match_type", "PHRASE"),
                monthly_searches=kw.get("monthly_searches"),
                avg_cpc_sek=kw.get("avg_cpc_sek"),
                competition=kw.get("competition"),
            )
            for kw in typed_keywords
        ]

        # Generate negative keywords for this group
        target_texts = [kw["text"] for kw in kw_dicts]
        negatives = generate_negative_keywords(target_texts, client.industry)

        # Generate RSA for this ad group
        rsa = generate_rsa(
            ad_group_theme=group_name,
            client=client,
            keywords=target_texts[:5],
            final_url=website_url,
        )

        ad_group = AdGroup(
            name=group_name.replace("_", " ").title(),
            theme=group_name,
            keywords=keywords,
            negative_keywords=negatives[:50],
            ads=[rsa],
        )

        campaign_name = f"{client.business_name} - {group_name.replace('_', ' ').title()}"
        campaign = Campaign(
            name=campaign_name,
            campaign_type="SEARCH",
            status="PAUSED",
            budget_sek_daily=0,  # Will be set by _allocate_budget
            ad_groups=[ad_group],
        )
        campaigns.append(campaign)

    return campaigns


def _structure_by_geo(
    client: ClientProfile,
    keyword_groups: dict[str, list[dict]],
) -> list[Campaign]:
    """Create one campaign per geographic target, each containing all keyword groups."""
    campaigns: list[Campaign] = []
    website_url = str(client.website_url)

    for geo in client.geographic_targets:
        ad_groups: list[AdGroup] = []

        for group_name, kw_dicts in keyword_groups.items():
            typed_keywords = assign_match_types(kw_dicts, client.monthly_budget_sek)
            keywords = [
                Keyword(
                    text=kw["text"],
                    match_type=kw.get("match_type", "PHRASE"),
                    monthly_searches=kw.get("monthly_searches"),
                    avg_cpc_sek=kw.get("avg_cpc_sek"),
                    competition=kw.get("competition"),
                )
                for kw in typed_keywords
            ]

            target_texts = [kw["text"] for kw in kw_dicts]
            negatives = generate_negative_keywords(target_texts, client.industry)

            rsa = generate_rsa(
                ad_group_theme=group_name,
                client=client,
                keywords=target_texts[:5],
                final_url=website_url,
            )

            ad_group = AdGroup(
                name=f"{group_name.replace('_', ' ').title()} - {geo.name}",
                theme=group_name,
                keywords=keywords,
                negative_keywords=negatives[:50],
                ads=[rsa],
            )
            ad_groups.append(ad_group)

        campaign = Campaign(
            name=f"{client.business_name} - {geo.name}",
            campaign_type="SEARCH",
            status="PAUSED",
            budget_sek_daily=0,
            geo_targets=[geo],
            ad_groups=ad_groups,
        )
        campaigns.append(campaign)

    return campaigns


def _allocate_budget(
    campaigns: list[Campaign],
    total_monthly_sek: int,
) -> list[Campaign]:
    """Distribute monthly budget across campaigns based on keyword volume/priority.

    Campaigns with more keywords get proportionally more budget.
    """
    if not campaigns:
        return campaigns

    # Weight by total keyword count per campaign
    weights: list[int] = []
    for campaign in campaigns:
        kw_count = sum(len(ag.keywords) for ag in campaign.ad_groups)
        weights.append(max(kw_count, 1))

    total_weight = sum(weights)
    daily_total = total_monthly_sek / 30

    for campaign, weight in zip(campaigns, weights):
        share = weight / total_weight
        campaign.budget_sek_daily = round(daily_total * share, 2)

    logger.info(
        "Allocated %d SEK/month across %d campaigns",
        total_monthly_sek, len(campaigns),
    )
    return campaigns


def _select_bid_strategy(budget_sek: int, goal_type: str) -> str:
    """Select appropriate bid strategy based on budget and goal type.

    Returns Google Ads bid strategy name.
    """
    goal_type = goal_type.lower()

    if budget_sek < 5_000:
        return "MANUAL_CPC"

    if goal_type in ("conversions", "leads", "sales"):
        if budget_sek >= 15_000:
            return "TARGET_CPA"
        return "MAXIMIZE_CONVERSIONS"

    if goal_type in ("revenue", "roas"):
        if budget_sek >= 20_000:
            return "TARGET_ROAS"
        return "MAXIMIZE_CONVERSION_VALUE"

    if goal_type in ("traffic", "clicks"):
        return "MAXIMIZE_CLICKS"

    if goal_type in ("awareness", "impressions"):
        return "TARGET_IMPRESSION_SHARE"

    return "MAXIMIZE_CLICKS"


def _generate_ad_schedule() -> dict:
    """Generate Swedish business hours ad schedule."""
    return DEFAULT_AD_SCHEDULE


def _generate_extensions(
    client: ClientProfile,
) -> tuple[list[Sitelink], list[Callout], list[StructuredSnippet], list[CallExtension]]:
    """Generate ad extensions based on client profile."""
    website_url = str(client.website_url)
    industry_lower = client.industry.lower().replace(" ", "_")

    # Sitelinks
    sitelinks = [
        Sitelink(
            text="Om Oss",
            desc1=f"Läs mer om {client.business_name}",
            desc2="Vår historia och vårt team",
            final_url=f"{website_url}/om-oss",
        ),
        Sitelink(
            text="Våra Tjänster",
            desc1="Se hela vårt utbud",
            desc2="Professionella lösningar",
            final_url=f"{website_url}/tjanster",
        ),
        Sitelink(
            text="Kontakta Oss",
            desc1="Ring eller maila oss",
            desc2="Snabb återkomst",
            final_url=f"{website_url}/kontakt",
        ),
        Sitelink(
            text="Få Offert",
            desc1="Kostnadsfri prisuppskattning",
            desc2="Svar inom 24 timmar",
            final_url=f"{website_url}/offert",
        ),
    ]

    # Callouts
    callout_texts = [
        "Fri Offert",
        "Snabb Service",
        "Lokalt Företag",
        "Nöjd Kund-Garanti",
    ]

    # Add ROT-avdrag callout for home service industries
    if any(rot in industry_lower for rot in ROT_INDUSTRIES):
        callout_texts.append("ROT-avdrag")

    callouts = [Callout(text=t) for t in callout_texts]

    # Structured Snippets
    snippets = []
    if client.products_services:
        snippets.append(
            StructuredSnippet(
                header="Tjänster",
                values=client.products_services[:10],
            )
        )

    if client.geographic_targets:
        snippets.append(
            StructuredSnippet(
                header="Platser",
                values=[g.name for g in client.geographic_targets[:10]],
            )
        )

    # Call Extensions (empty list if no phone info available)
    call_extensions: list[CallExtension] = []

    logger.info(
        "Generated extensions: %d sitelinks, %d callouts, %d snippets, %d call ext",
        len(sitelinks), len(callouts), len(snippets), len(call_extensions),
    )
    return sitelinks, callouts, snippets, call_extensions
