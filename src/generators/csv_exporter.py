"""Google Ads Editor CSV export -- the highest-value deliverable.

Exports a CampaignPlan into per-entity-type CSV files that can be directly
imported into Google Ads Editor using UTF-8 BOM encoding for Excel compatibility.
"""

from __future__ import annotations

import csv
import logging
from io import StringIO
from pathlib import Path

import pandas as pd

from src.models.campaign import (
    Campaign, CampaignPlan, Sitelink, Callout,
)

logger = logging.getLogger(__name__)

_README_CONTENT = """\
Google Ads Editor Import Order
==============================

Import the CSV files in numerical order:

1. 01_campaigns.csv        - Campaign settings (budget, bidding, targeting)
2. 02_ad_groups.csv        - Ad groups within each campaign
3. 03_keywords.csv         - Keywords with match types and final URLs
4. 04_responsive_search_ads.csv - RSA ads with headlines and descriptions
5. 05_negative_keywords.csv - Negative keywords for traffic filtering
6. 06_sitelinks.csv        - Sitelink extensions per campaign
7. 07_callouts.csv         - Callout extensions per campaign

Instructions:
- Open Google Ads Editor
- Select File > Import > From CSV
- Import each file in order (campaigns first, then ad groups, etc.)
- Review changes in the editor before posting
- All files use UTF-8 BOM encoding for compatibility
"""


def export_campaign_plan(plan: CampaignPlan, output_dir: str) -> str:
    """Export a complete campaign plan to per-entity-type CSV files.

    Returns the path to the output directory containing all files.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    campaign_names = [c.name for c in plan.campaigns]

    files = [
        ("01_campaigns.csv", _campaign_rows(plan.campaigns)),
        ("02_ad_groups.csv", _ad_group_rows(plan.campaigns)),
        ("03_keywords.csv", _keyword_rows(plan.campaigns)),
        ("04_responsive_search_ads.csv", _rsa_rows(plan.campaigns)),
        ("05_negative_keywords.csv", _negative_keyword_rows(plan.campaigns)),
        ("06_sitelinks.csv", _sitelink_rows(plan.sitelinks, campaign_names)),
        ("07_callouts.csv", _callout_rows(plan.callouts, campaign_names)),
    ]

    total_rows = 0
    for filename, rows in files:
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df = df.fillna("")
        csv_path = output_path / filename
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        total_rows += len(df)
        logger.info("Exported %s (%d rows)", filename, len(df))

    # Write README
    readme_path = output_path / "README_import_order.txt"
    readme_path.write_text(_README_CONTENT, encoding="utf-8")
    logger.info("Wrote %s", readme_path)

    logger.info("Exported campaign plan to %s (%d total rows)", output_path, total_rows)
    return str(output_path)


def _campaign_rows(campaigns: list[Campaign]) -> list[dict]:
    """Generate campaign-level rows for Google Ads Editor."""
    rows = []
    for campaign in campaigns:
        locations = "; ".join(g.name for g in campaign.geo_targets)
        languages = "; ".join(campaign.language_codes)

        rows.append({
            "Campaign": campaign.name,
            "Campaign Type": campaign.campaign_type,
            "Campaign Status": campaign.status,
            "Budget": round(campaign.budget_sek_daily, 2),
            "Budget type": "Daily",
            "Bid Strategy Type": campaign.bid_strategy,
            "Networks": "Google search",
            "Languages": languages or "sv",
            "Location": locations,
        })
    return rows


def _ad_group_rows(campaigns: list[Campaign]) -> list[dict]:
    """Generate ad group rows for Google Ads Editor."""
    rows = []
    for campaign in campaigns:
        for ag in campaign.ad_groups:
            rows.append({
                "Campaign": campaign.name,
                "Ad Group": ag.name,
                "Status": "Enabled",
                "Max CPC": "",
                "Ad Group Type": "Standard",
            })
    return rows


def _keyword_rows(campaigns: list[Campaign]) -> list[dict]:
    """Generate keyword rows for Google Ads Editor."""
    rows = []
    for campaign in campaigns:
        final_url = ""
        # Get final URL from the first ad in the campaign
        for ag in campaign.ad_groups:
            if ag.ads:
                final_url = str(ag.ads[0].final_url)
                break

        for ag in campaign.ad_groups:
            for kw in ag.keywords:
                # Google Ads Editor criterion type format
                criterion_map = {
                    "BROAD": "Broad",
                    "PHRASE": "Phrase",
                    "EXACT": "Exact",
                }
                rows.append({
                    "Campaign": campaign.name,
                    "Ad Group": ag.name,
                    "Keyword": kw.text,
                    "Criterion Type": criterion_map.get(kw.match_type, "Broad"),
                    "Status": "Enabled",
                    "Final URL": final_url,
                })
    return rows


def _rsa_rows(campaigns: list[Campaign]) -> list[dict]:
    """Generate Responsive Search Ad rows for Google Ads Editor."""
    rows = []
    for campaign in campaigns:
        for ag in campaign.ad_groups:
            for ad in ag.ads:
                row: dict = {
                    "Campaign": campaign.name,
                    "Ad Group": ag.name,
                    "Ad type": "Responsive search ad",
                    "Final URL": str(ad.final_url),
                    "Path 1": ad.path1,
                    "Path 2": ad.path2,
                    "Status": "Enabled",
                }

                # Add headlines (up to 15)
                for i, headline in enumerate(ad.headlines, 1):
                    row[f"Headline {i}"] = headline.text
                    # Pin positions: H1=brand (pos 1), H2=service (pos 2), H3+=unpinned
                    if i == 1:
                        row[f"Headline {i} position"] = "1"
                    elif i == 2:
                        row[f"Headline {i} position"] = "2"
                    else:
                        row[f"Headline {i} position"] = ""

                # Add descriptions (up to 4)
                for i, desc in enumerate(ad.descriptions, 1):
                    row[f"Description {i}"] = desc.text
                    if i == 1:
                        row[f"Description {i} position"] = "1"
                    else:
                        row[f"Description {i} position"] = ""

                rows.append(row)
    return rows


def _sitelink_rows(sitelinks: list[Sitelink], campaign_names: list[str]) -> list[dict]:
    """Generate sitelink extension rows, one per sitelink per campaign."""
    rows = []
    for campaign_name in campaign_names:
        for sl in sitelinks:
            rows.append({
                "Campaign": campaign_name,
                "Sitelink text": sl.text,
                "Description 1": sl.desc1,
                "Description 2": sl.desc2,
                "Final URL": str(sl.final_url),
                "Status": "Enabled",
            })
    return rows


def _callout_rows(callouts: list[Callout], campaign_names: list[str]) -> list[dict]:
    """Generate callout extension rows, one per callout per campaign."""
    rows = []
    for campaign_name in campaign_names:
        for co in callouts:
            rows.append({
                "Campaign": campaign_name,
                "Callout text": co.text,
                "Status": "Enabled",
            })
    return rows


def _negative_keyword_rows(campaigns: list[Campaign]) -> list[dict]:
    """Generate negative keyword rows for Google Ads Editor."""
    rows = []
    for campaign in campaigns:
        for ag in campaign.ad_groups:
            for neg_kw in ag.negative_keywords:
                rows.append({
                    "Campaign": campaign.name,
                    "Keyword": neg_kw,
                    "Criterion Type": "Broad",
                })
    return rows
