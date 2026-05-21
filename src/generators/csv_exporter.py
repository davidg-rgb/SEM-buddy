"""Google Ads Editor CSV export — the highest-value deliverable.

Exports a CampaignPlan into per-entity-type CSV files that can be directly
imported into Google Ads Editor using UTF-8 BOM encoding for Excel compatibility.

v0.3 adds promotion extensions (08), lead forms (09), and a documentation-only
bid-schedules export (10).
"""

from __future__ import annotations

import csv
import logging
from io import StringIO
from pathlib import Path

import pandas as pd

from src.models.campaign import (
    BidSchedule,
    Callout,
    Campaign,
    CampaignPlan,
    LeadFormExtension,
    PromotionExtension,
    Sitelink,
)

logger = logging.getLogger(__name__)

_README_CONTENT = """\
Google Ads Editor Import Order
==============================

Import the CSV files in numerical order:

1. 01_campaigns.csv            - Campaign settings (budget, bidding, targeting)
2. 02_ad_groups.csv            - Ad groups within each campaign (bid modifier column)
3. 03_keywords.csv             - Keywords with match types and final URLs
4. 04_responsive_search_ads.csv - RSA ads with headlines and descriptions
5. 05_negative_keywords.csv    - Negative keywords for traffic filtering
6. 06_sitelinks.csv            - Sitelink extensions per campaign
7. 07_callouts.csv             - Callout extensions per campaign
8. 08_promotions.csv           - Promotion extensions (per ad group / per product)
9. 09_lead_forms.csv           - Lead form extensions (one per campaign)
10. 10_bid_schedules.csv       - DOCUMENTATION ONLY — Seasonality/scheduled bids
                                 do NOT auto-import via Editor; apply via Google
                                 Ads scripts or UI using this as the source-of-truth.

Instructions:
- Open Google Ads Editor
- Select File > Import > From CSV
- Import each file in order (campaigns first, then ad groups, etc.)
- Review changes in the editor before posting
- All files use UTF-8 BOM encoding for compatibility
"""


def export_campaign_plan(plan: CampaignPlan, output_dir: str) -> str:
    """Export a complete campaign plan to per-entity-type CSV files."""
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
        ("08_promotions.csv", _promotion_rows(plan.promotions)),
        ("09_lead_forms.csv", _lead_form_rows(plan.lead_forms)),
        ("10_bid_schedules.csv", _bid_schedule_rows(plan.bid_schedules)),
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

    readme_path = output_path / "README_import_order.txt"
    readme_path.write_text(_README_CONTENT, encoding="utf-8")
    logger.info("Wrote %s", readme_path)

    logger.info("Exported campaign plan to %s (%d total rows)", output_path, total_rows)
    return str(output_path)


def _campaign_rows(campaigns: list[Campaign]) -> list[dict]:
    rows = []
    for campaign in campaigns:
        locations = "; ".join(g.name for g in campaign.geo_targets)
        languages = "; ".join(campaign.language_codes)
        radii = "; ".join(
            f"{g.name}={g.radius_km}km" for g in campaign.geo_targets if g.radius_km is not None
        )
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
            "Location radius (km)": radii,
        })
    return rows


def _ad_group_rows(campaigns: list[Campaign]) -> list[dict]:
    """Ad-group rows with bid modifier / max CPC columns.

    Google Ads Editor accepts these columns; if they're empty Editor ignores them.
    Bid modifier is emitted as a percentage delta (Google's display convention).
    """
    rows = []
    for campaign in campaigns:
        for ag in campaign.ad_groups:
            max_cpc_str = f"{ag.max_cpc_sek:.2f}" if ag.max_cpc_sek else ""
            if ag.bid_modifier == 1.0:
                modifier_str = ""
            else:
                # Google Ads expresses this as +50% or -10% relative to base bid
                delta_pct = round((ag.bid_modifier - 1.0) * 100, 2)
                sign = "+" if delta_pct >= 0 else ""
                modifier_str = f"{sign}{delta_pct}%"
            rows.append({
                "Campaign": campaign.name,
                "Ad Group": ag.name,
                "Status": "Enabled",
                "Max CPC": max_cpc_str,
                "Bid modifier": modifier_str,
                "Ad Group Type": "Standard",
            })
    return rows


def _keyword_rows(campaigns: list[Campaign]) -> list[dict]:
    rows = []
    for campaign in campaigns:
        # When ad groups carry per-row URLs (catalog mode), use each AG's
        # first-ad URL rather than a single campaign-wide default.
        for ag in campaign.ad_groups:
            ag_final_url = ""
            if ag.ads:
                ag_final_url = str(ag.ads[0].final_url)
            for kw in ag.keywords:
                criterion_map = {"BROAD": "Broad", "PHRASE": "Phrase", "EXACT": "Exact"}
                rows.append({
                    "Campaign": campaign.name,
                    "Ad Group": ag.name,
                    "Keyword": kw.text,
                    "Criterion Type": criterion_map.get(kw.match_type, "Broad"),
                    "Status": "Enabled",
                    "Final URL": ag_final_url,
                })
    return rows


def _rsa_rows(campaigns: list[Campaign]) -> list[dict]:
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
                for i, headline in enumerate(ad.headlines, 1):
                    row[f"Headline {i}"] = headline.text
                    if i == 1:
                        row[f"Headline {i} position"] = "1"
                    elif i == 2:
                        row[f"Headline {i} position"] = "2"
                    else:
                        row[f"Headline {i} position"] = ""
                for i, desc in enumerate(ad.descriptions, 1):
                    row[f"Description {i}"] = desc.text
                    if i == 1:
                        row[f"Description {i} position"] = "1"
                    else:
                        row[f"Description {i} position"] = ""
                rows.append(row)
    return rows


def _sitelink_rows(sitelinks: list[Sitelink], campaign_names: list[str]) -> list[dict]:
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


def _promotion_rows(promotions: list[PromotionExtension]) -> list[dict]:
    """Promotion extension rows for Google Ads Editor."""
    rows = []
    for promo in promotions:
        rows.append({
            "Campaign": promo.campaign_name,
            "Ad group": promo.ad_group_name or "",
            "Promotion target": "",
            "Discount modifier": promo.discount_modifier,
            "Percent off": _format_optional_number(promo.percent_off),
            "Money amount off": _format_optional_number(promo.money_amount_off),
            "Money currency": promo.money_currency if promo.money_amount_off is not None else "",
            "Promotion code": promo.promotion_code or "",
            "Orders over amount": _format_optional_number(promo.orders_over_amount),
            "Promotion start date": promo.start_date.isoformat() if promo.start_date else "",
            "Promotion end date": promo.end_date.isoformat() if promo.end_date else "",
            "Final URL": str(promo.final_url),
            "Final URL suffix": promo.final_url_suffix or "",
            "Tracking template": promo.tracking_template or "",
            "Language": promo.language,
            "Occasion": promo.occasion or "",
            "Status": "Enabled",
        })
    return rows


def _lead_form_rows(lead_forms: list[LeadFormExtension]) -> list[dict]:
    """Lead form rows. `Form fields` is emitted as semicolon-separated tokens
    (Google Ads Editor's standard format for repeating asset fields)."""
    rows = []
    for lf in lead_forms:
        rows.append({
            "Campaign": lf.campaign_name,
            "Asset name": lf.asset_name,
            "Form name": lf.form_name,
            "Headline": lf.headline,
            "Description": lf.description,
            "CTA description": lf.cta_description,
            "Business name": lf.business_name,
            "CTA": lf.cta,
            "Privacy URL": str(lf.privacy_url),
            "Form fields": "; ".join(lf.fields),
            "Submit headline": lf.submit_headline,
            "Submit description": lf.submit_description,
            "Submit URL": str(lf.submit_url) if lf.submit_url else "",
            "Status": "Enabled",
        })
    return rows


def _bid_schedule_rows(schedules: list[BidSchedule]) -> list[dict]:
    """Documentation export — Google Ads Editor does NOT import seasonality
    adjustments directly. This file captures the intended schedules so the
    operator (or a future Google Ads script) can apply them."""
    rows = []
    for s in schedules:
        rows.append({
            "Campaign": s.campaign_name,
            "Ad group": s.ad_group_name or "",
            "Start date": s.start_date.isoformat(),
            "End date": s.end_date.isoformat(),
            "Bid modifier": f"{(s.modifier - 1.0) * 100:+.1f}%",
            "Multiplier": f"{s.modifier:.2f}",
            "Reason": s.reason,
        })
    return rows


def _format_optional_number(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
