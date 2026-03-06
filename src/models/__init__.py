"""SEM Master data models."""

from .client import ClientProfile, TargetAudience, GeoTarget, CampaignGoal
from .campaign import (
    AdHeadline,
    AdDescription,
    ResponsiveSearchAd,
    Keyword,
    AdGroup,
    Campaign,
    Sitelink,
    Callout,
    StructuredSnippet,
    CallExtension,
    CampaignPlan,
)
from .competitor import TransparencyAd, CompetitorProfile
from .research import (
    CrawledPage,
    SiteCrawl,
    Review,
    SocialProfile,
    GoogleBusinessProfile,
    DigitalPresence,
)

__all__ = [
    "ClientProfile",
    "TargetAudience",
    "GeoTarget",
    "CampaignGoal",
    "AdHeadline",
    "AdDescription",
    "ResponsiveSearchAd",
    "Keyword",
    "AdGroup",
    "Campaign",
    "Sitelink",
    "Callout",
    "StructuredSnippet",
    "CallExtension",
    "CampaignPlan",
    "TransparencyAd",
    "CompetitorProfile",
    "CrawledPage",
    "SiteCrawl",
    "Review",
    "SocialProfile",
    "GoogleBusinessProfile",
    "DigitalPresence",
]
