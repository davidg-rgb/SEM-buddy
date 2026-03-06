"""Google Ads Editor CSV export -- the highest-value deliverable.

Exports a CampaignPlan into a single CSV file that can be directly imported
into Google Ads Editor using UTF-8 BOM encoding for Excel compatibility.
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


def export_campaign_plan(plan: CampaignPlan, output_dir: str) -> str:
    """Export a complete campaign plan to a single Google Ads Editor CSV file.

    Returns the path to the generated CSV file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []

    # Build rows in Google Ads Editor order
    all_rows.extend(_campaign_rows(plan.campaigns))
    all_rows.extend(_ad_group_rows(plan.campaigns))
    all_rows.extend(_keyword_rows(plan.campaigns))
    all_rows.extend(_rsa_rows(plan.campaigns))
    all_rows.extend(_negative_keyword_rows(plan.campaigns))
    all_rows.extend(_sitelink_rows(plan.sitelinks))
    all_rows.extend(_callout_rows(plan.callouts))

    if not all_rows:
        logger.warning("No data to export")
        return ""

    # Use pandas to create a unified DataFrame with all columns
    df = pd.DataFrame(all_rows)

    # Fill NaN with empty string for clean CSV output
    df = df.fillna("")

    # Export with UTF-8 BOM for Excel compatibility
    csv_path = output_path / "google_ads_import.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    logger.info("Exported campaign plan to %s (%d rows)", csv_path, len(df))
    return str(csv_path)


def _campaign_rows(campaigns: list[Campaign]) -> list[dict]:
    """Generate campaign-level rows for Google Ads Editor."""
    rows = []
    for campaign in campaigns:
        locations = "; ".join(g.name for g in campaign.geo_targets)
        languages = "; ".join(campaign.language_codes)

        rows.append({
            "Row Type": "Campaign",
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
                "Row Type": "Ad Group",
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
                    "Row Type": "Keyword",
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
                    "Row Type": "Ad",
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


def _sitelink_rows(sitelinks: list[Sitelink]) -> list[dict]:
    """Generate sitelink extension rows."""
    rows = []
    for sl in sitelinks:
        rows.append({
            "Row Type": "Sitelink",
            "Sitelink text": sl.text,
            "Description 1": sl.desc1,
            "Description 2": sl.desc2,
            "Final URL": str(sl.final_url),
            "Status": "Enabled",
        })
    return rows


def _callout_rows(callouts: list[Callout]) -> list[dict]:
    """Generate callout extension rows."""
    rows = []
    for co in callouts:
        rows.append({
            "Row Type": "Callout",
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
                    "Row Type": "Negative Keyword",
                    "Campaign": campaign.name,
                    "Keyword": neg_kw,
                    "Criterion Type": "Broad",
                })
    return rows
