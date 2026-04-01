"""Live campaign data retrieval from Google Ads API.

Wraps GoogleAdsService to produce enriched campaign dicts suitable for
comparison against a locally generated CampaignPlan.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.apis.google_ads import get_ads_service
from src.auth import AuthError
from src.apis.errors import GoogleAdsApiError

logger = logging.getLogger(__name__)


async def fetch_live_campaigns(
    customer_id: str,
    dry_run: bool = False,
    campaign_ids: list[str] | None = None,
) -> list[dict]:
    """Fetch live campaign data enriched with ad groups, keywords, and ads.

    Calls the Google Ads API (or DryRunGoogleAdsService when dry_run=True) to
    retrieve the full campaign hierarchy for a customer account.

    Args:
        customer_id: Google Ads customer ID in XXX-XXX-XXXX format.
        dry_run: When True, use synthetic data instead of the live API.
        campaign_ids: Optional list of campaign IDs to limit the fetch.
            When None, all non-removed campaigns are returned.

    Returns:
        List of enriched campaign dicts, each with the shape::

            {
                "id": str,
                "name": str,
                "status": str,
                "advertising_channel_type": str,
                "campaign_budget": str,
                "ad_groups": [
                    {
                        "id": str,
                        "name": str,
                        "status": str,
                        "type": str,
                        "keywords": [{"text": str, "match_type": str, "status": str}],
                        "ads": [{"headlines": [str], "descriptions": [str], "status": str}],
                    }
                ],
            }

    Raises:
        AuthError: If not authenticated with Google Ads.
        GoogleAdsApiError: On API or quota errors.
    """
    service = get_ads_service(customer_id, dry_run=dry_run)

    campaigns = await service.get_campaigns()

    if campaign_ids is not None:
        campaign_ids_set = set(campaign_ids)
        campaigns = [c for c in campaigns if c["id"] in campaign_ids_set]

    enriched: list[dict] = []
    for campaign in campaigns:
        ad_groups_raw = await service.get_ad_groups(campaign["id"])

        ad_groups: list[dict] = []
        for ag in ad_groups_raw:
            keywords = await service.get_keywords(ag["id"])
            ads = await service.get_ads(ag["id"])
            ad_groups.append(
                {
                    "id": ag["id"],
                    "name": ag["name"],
                    "status": ag["status"],
                    "type": ag["type"],
                    "keywords": keywords,
                    "ads": ads,
                }
            )

        enriched.append(
            {
                "id": campaign["id"],
                "name": campaign["name"],
                "status": campaign.get("status", ""),
                "advertising_channel_type": campaign.get("advertising_channel_type", ""),
                "campaign_budget": str(campaign.get("campaign_budget", "")),
                "ad_groups": ad_groups,
            }
        )

    return enriched


async def fetch_keyword_performance(
    customer_id: str,
    dry_run: bool = False,
    date_range: str = "LAST_30_DAYS",
) -> list[dict]:
    """Fetch keyword performance metrics for the account.

    Args:
        customer_id: Google Ads customer ID.
        dry_run: When True, return synthetic performance data.
        date_range: GAQL date range constant (e.g. LAST_30_DAYS, LAST_7_DAYS).

    Returns:
        List of keyword performance dicts with keys:
        text, impressions, clicks, ctr, avg_cpc, conversions.
    """
    if dry_run:
        return _synthetic_keyword_performance()

    service = get_ads_service(customer_id, dry_run=False)

    query = (
        "SELECT ad_group_criterion.keyword.text, "
        "metrics.impressions, metrics.clicks, metrics.ctr, "
        "metrics.average_cpc, metrics.conversions "
        f"FROM keyword_view WHERE segments.date DURING {date_range}"
    )

    try:
        rows = service._search(query)
    except (GoogleAdsApiError, AuthError):
        raise
    except Exception as exc:
        logger.warning("fetch_keyword_performance failed: %s", exc)
        return []

    results: list[dict] = []
    for row in rows:
        criterion = row.ad_group_criterion
        metrics = row.metrics
        results.append(
            {
                "text": criterion.keyword.text,
                "impressions": int(metrics.impressions),
                "clicks": int(metrics.clicks),
                "ctr": float(metrics.ctr),
                "avg_cpc": float(metrics.average_cpc),
                "conversions": float(metrics.conversions),
            }
        )
    return results


def _synthetic_keyword_performance() -> list[dict]:
    """Return a small set of synthetic keyword performance rows for dry-run mode."""
    terms = [
        ("tandläkare stockholm", 1200, 84, 0.07, 15_000_000, 6.0),
        ("bästa tandvård", 540, 31, 0.057, 12_000_000, 2.0),
        ("akut tandläkare", 320, 28, 0.087, 18_000_000, 4.5),
        ("tandvård billig", 210, 14, 0.066, 9_000_000, 1.5),
        ("tandimplantat pris", 870, 63, 0.072, 22_000_000, 8.0),
        ("tandhygienist stockholm", 450, 34, 0.075, 11_000_000, 3.0),
    ]
    return [
        {
            "text": text,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "avg_cpc": avg_cpc_micros / 1_000_000,
            "conversions": conversions,
        }
        for text, impressions, clicks, ctr, avg_cpc_micros, conversions in terms
    ]


def fetch_live_campaigns_sync(
    customer_id: str,
    dry_run: bool = False,
    campaign_ids: list[str] | None = None,
) -> list[dict]:
    """Synchronous wrapper around fetch_live_campaigns for CLI use.

    Args:
        customer_id: Google Ads customer ID in XXX-XXX-XXXX format.
        dry_run: When True, use synthetic data instead of the live API.
        campaign_ids: Optional list of campaign IDs to filter.

    Returns:
        List of enriched campaign dicts (same shape as fetch_live_campaigns).

    Raises:
        AuthError: If not authenticated with Google Ads.
        GoogleAdsApiError: On API or quota errors.
    """
    return asyncio.run(
        fetch_live_campaigns(customer_id, dry_run=dry_run, campaign_ids=campaign_ids)
    )
