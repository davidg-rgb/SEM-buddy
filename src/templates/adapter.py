"""Template adaptation — apply a saved template to a new client context.

Replaces placeholder tokens written by manager.py with the new client's data,
updates geo targets, and regenerates ad copy via ad_copy_generator so the
output is tailored to the new client rather than the original source.
"""

from __future__ import annotations

import copy

from src.models.campaign import (
    AdGroup,
    Campaign,
    CampaignPlan,
    Callout,
    CallExtension,
    Keyword,
    ResponsiveSearchAd,
    Sitelink,
    StructuredSnippet,
)
from src.models.client import ClientProfile
from src.templates.manager import CampaignTemplate

_PLACEHOLDER_COMPANY = "{Foretag}"
_PLACEHOLDER_WEBSITE = "{website}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _replace_placeholders_str(text: str, business_name: str, website_url: str) -> str:
    """Replace template placeholders with new client values."""
    text = text.replace(_PLACEHOLDER_COMPANY, business_name)
    text = text.replace(_PLACEHOLDER_WEBSITE, website_url)
    return text


def _replace_placeholders_dict(data: dict, business_name: str, website_url: str) -> dict:
    """Recursively replace placeholder tokens in a dict."""
    result: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = _replace_placeholders_str(value, business_name, website_url)
        elif isinstance(value, list):
            result[key] = _replace_placeholders_list(value, business_name, website_url)
        elif isinstance(value, dict):
            result[key] = _replace_placeholders_dict(value, business_name, website_url)
        else:
            result[key] = value
    return result


def _replace_placeholders_list(data: list, business_name: str, website_url: str) -> list:
    """Recursively replace placeholder tokens in a list."""
    result = []
    for item in data:
        if isinstance(item, str):
            result.append(_replace_placeholders_str(item, business_name, website_url))
        elif isinstance(item, dict):
            result.append(_replace_placeholders_dict(item, business_name, website_url))
        elif isinstance(item, list):
            result.append(_replace_placeholders_list(item, business_name, website_url))
        else:
            result.append(item)
    return result


def _adapt_campaign(
    campaign_dict: dict,
    client: ClientProfile,
    keyword_groups: dict | None,
) -> Campaign:
    """Adapt a single campaign dict for the new client.

    - Replaces placeholder tokens in all text fields.
    - Sets geo_targets from client.geographic_targets.
    - Regenerates ad copy for each ad group via ad_copy_generator.
    - Optionally updates keywords from keyword_groups if theme matches.

    Args:
        campaign_dict: Raw campaign dict (from a CampaignTemplate).
        client: The target ClientProfile.
        keyword_groups: Optional dict mapping theme -> list[str] keyword texts.

    Returns:
        A fully constructed Campaign instance.
    """
    from src.generators.ad_copy_generator import generate_rsa

    business_name = client.business_name
    website_url = str(client.website_url)

    adapted = _replace_placeholders_dict(campaign_dict, business_name, website_url)

    # Apply client geo targets (overrides stripped value)
    adapted["geo_targets"] = [gt.model_dump() for gt in client.geographic_targets]

    # Re-adapt ad groups
    adapted_ad_groups: list[dict] = []
    for ag_dict in adapted.get("ad_groups", []):
        theme = ag_dict.get("theme", "")

        # Optionally update keyword list from keyword_groups
        if keyword_groups and theme in keyword_groups:
            new_keywords = [
                {"text": kw, "match_type": "PHRASE"}
                for kw in keyword_groups[theme]
            ]
            ag_dict["keywords"] = new_keywords

        # Collect keyword texts for ad copy generation
        kw_texts = [k["text"] for k in ag_dict.get("keywords", [])]

        # Determine final URL (use campaign-level or client website)
        final_url = website_url

        # Regenerate RSAs for this ad group
        rsa = generate_rsa(theme, client, kw_texts, final_url)
        ag_dict["ads"] = [rsa.model_dump()]

        adapted_ad_groups.append(ag_dict)

    adapted["ad_groups"] = adapted_ad_groups

    return Campaign.model_validate(adapted)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_template(
    template: CampaignTemplate,
    client: ClientProfile,
    keyword_groups: dict | None = None,
) -> CampaignPlan:
    """Apply a saved template to a new client, producing a ready-to-use CampaignPlan.

    For each campaign in the template:
    - Placeholder tokens ({Foretag}, {website}) are replaced with the new client's data.
    - geo_targets are set from client.geographic_targets.
    - Ad copy (headlines, descriptions) is regenerated via generate_rsa() so the
      copy is tailored to the new client rather than copied verbatim.
    - If keyword_groups is provided and an ad group theme matches a key, the
      keywords for that group are updated from the provided lists.

    Sitelinks, callouts, snippets, and call_extensions from the template are
    included with placeholder substitution applied.

    Args:
        template: The CampaignTemplate to apply.
        client: The target ClientProfile.
        keyword_groups: Optional mapping of theme -> list[str] keyword texts.

    Returns:
        Adapted CampaignPlan ready for export or further editing.
    """
    business_name = client.business_name
    website_url = str(client.website_url)

    # Adapt each campaign
    campaigns: list[Campaign] = []
    for campaign_dict in template.campaigns:
        campaign_copy = copy.deepcopy(campaign_dict)
        adapted_campaign = _adapt_campaign(campaign_copy, client, keyword_groups)
        campaigns.append(adapted_campaign)

    # Adapt extensions — replace placeholders only (geo not applicable)
    sitelinks: list[Sitelink] = []
    for sl_dict in template.sitelinks:
        adapted = _replace_placeholders_dict(sl_dict, business_name, website_url)
        sitelinks.append(Sitelink.model_validate(adapted))

    callouts: list[Callout] = []
    for co_dict in template.callouts:
        adapted = _replace_placeholders_dict(co_dict, business_name, website_url)
        callouts.append(Callout.model_validate(adapted))

    snippets: list[StructuredSnippet] = []
    for sn_dict in template.snippets:
        adapted = _replace_placeholders_dict(sn_dict, business_name, website_url)
        snippets.append(StructuredSnippet.model_validate(adapted))

    call_extensions: list[CallExtension] = []
    for ce_dict in template.call_extensions:
        adapted = _replace_placeholders_dict(ce_dict, business_name, website_url)
        call_extensions.append(CallExtension.model_validate(adapted))

    return CampaignPlan(
        campaigns=campaigns,
        sitelinks=sitelinks,
        callouts=callouts,
        snippets=snippets,
        call_extensions=call_extensions,
    )
