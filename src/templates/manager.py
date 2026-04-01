"""Template CRUD operations for campaign templates.

Templates are stored as JSON files under ~/.sem-master/templates/{name}.json.
Each template captures the campaign structure stripped of client-specific data
so it can be re-applied to a different client via adapter.py.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.models.campaign import CampaignPlan
from src.models.client import ClientProfile
from src.models.template import CampaignTemplate
from src.utils.config_manager import CONFIG_DIR

TEMPLATES_DIR = CONFIG_DIR / "templates"

# Placeholder tokens written into the template (replaced on load)
_PLACEHOLDER_COMPANY = "{Foretag}"
_PLACEHOLDER_WEBSITE = "{website}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_website_host(client: ClientProfile) -> str:
    """Return the hostname of the client's website URL (without scheme)."""
    url_str = str(client.website_url)
    # Remove scheme (http:// or https://)
    host = re.sub(r"^https?://", "", url_str)
    # Remove trailing path/slash
    host = host.split("/")[0]
    return host


def _strip_text(text: str, business_name: str, website_host: str) -> str:
    """Replace client-specific tokens with generic placeholders."""
    text = text.replace(business_name, _PLACEHOLDER_COMPANY)
    text = text.replace(website_host, _PLACEHOLDER_WEBSITE)
    return text


def _strip_dict(data: dict, business_name: str, website_host: str) -> dict:
    """Recursively strip client-specific data from a dict."""
    result: dict = {}
    for key, value in data.items():
        if key == "geo_targets":
            # Clear geo targets — will be populated from target client on load
            result[key] = []
        elif isinstance(value, str):
            result[key] = _strip_text(value, business_name, website_host)
        elif isinstance(value, list):
            result[key] = _strip_list(value, business_name, website_host)
        elif isinstance(value, dict):
            result[key] = _strip_dict(value, business_name, website_host)
        else:
            result[key] = value
    return result


def _strip_list(data: list, business_name: str, website_host: str) -> list:
    """Recursively strip client-specific data from a list."""
    result = []
    for item in data:
        if isinstance(item, str):
            result.append(_strip_text(item, business_name, website_host))
        elif isinstance(item, dict):
            result.append(_strip_dict(item, business_name, website_host))
        elif isinstance(item, list):
            result.append(_strip_list(item, business_name, website_host))
        else:
            result.append(item)
    return result


def _strip_client_specifics(
    campaign_plan: CampaignPlan,
    client: ClientProfile,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Strip client-specific data from all campaign structures.

    Returns:
        Tuple of (campaigns, sitelinks, callouts, snippets, call_extensions)
        as plain dicts with placeholders substituted for client data.
    """
    business_name = client.business_name
    website_host = _get_website_host(client)

    campaigns = [
        _strip_dict(c.model_dump(), business_name, website_host)
        for c in campaign_plan.campaigns
    ]
    sitelinks = [
        _strip_dict(s.model_dump(), business_name, website_host)
        for s in campaign_plan.sitelinks
    ]
    callouts = [
        _strip_dict(co.model_dump(), business_name, website_host)
        for co in campaign_plan.callouts
    ]
    snippets = [
        _strip_dict(sn.model_dump(), business_name, website_host)
        for sn in campaign_plan.snippets
    ]
    call_extensions = [
        _strip_dict(ce.model_dump(), business_name, website_host)
        for ce in campaign_plan.call_extensions
    ]
    return campaigns, sitelinks, callouts, snippets, call_extensions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_template(
    name: str,
    campaign_plan: CampaignPlan,
    client: ClientProfile,
    description: str = "",
) -> Path:
    """Save a campaign plan as a reusable template.

    Client-specific data (business name, website host, geo targets) is replaced
    with generic placeholders so the template can be applied to a different client.

    Args:
        name: Template slug (used as filename, e.g. "dental-basic").
        campaign_plan: The CampaignPlan to save.
        client: The ClientProfile this plan was built for (used for stripping).
        description: Optional human-readable description.

    Returns:
        Path to the written JSON file.
    """
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    campaigns, sitelinks, callouts, snippets, call_extensions = _strip_client_specifics(
        campaign_plan, client
    )

    # Extract ad group patterns from campaigns for reuse
    ad_group_patterns = []
    for camp in campaigns:
        for ag in camp.get("ad_groups", []):
            ad_group_patterns.append({
                "theme": ag.get("theme", ag.get("name", "")),
                "keyword_count": len(ag.get("keywords", [])),
            })

    template = CampaignTemplate(
        name=name,
        description=description,
        created_at=datetime.now(timezone.utc),
        source_client=client.business_name,
        source_industry=client.industry,
        campaign_structures=campaigns,
        ad_group_patterns=ad_group_patterns,
        extension_patterns={
            "sitelinks": sitelinks,
            "callouts": callouts,
            "snippets": snippets,
            "call_extensions": call_extensions,
        },
        budget_strategy={
            "campaign_count": len(campaigns),
            "total_budget_sek": sum(c.get("budget_sek_daily", 0) for c in campaigns) * 30,
            "bid_strategies": list({c.get("bid_strategy", "MANUAL_CPC") for c in campaigns}),
        },
    )

    output_path = TEMPLATES_DIR / f"{name}.json"
    output_path.write_text(
        template.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path


def load_template(name: str) -> CampaignTemplate:
    """Load a template by name.

    Args:
        name: Template slug (without .json extension).

    Returns:
        Validated CampaignTemplate instance.

    Raises:
        FileNotFoundError: If no template with that name exists.
    """
    path = TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template '{name}' not found")
    return CampaignTemplate.model_validate_json(path.read_text(encoding="utf-8"))


def list_templates() -> list[dict]:
    """List all saved templates as summary dicts.

    Returns:
        List of dicts with keys: name, description, created_at, source_client, source_industry.
        Returns an empty list if the templates directory does not exist.
    """
    if not TEMPLATES_DIR.exists():
        return []

    result = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            tmpl = CampaignTemplate.model_validate_json(path.read_text(encoding="utf-8"))
            result.append(
                {
                    "name": tmpl.name,
                    "description": tmpl.description,
                    "created_at": tmpl.created_at,
                    "source_client": tmpl.source_client,
                    "source_industry": tmpl.source_industry,
                }
            )
        except Exception:
            # Skip malformed template files
            continue

    return result


def delete_template(name: str) -> None:
    """Delete a template by name.

    Args:
        name: Template slug (without .json extension).

    Raises:
        FileNotFoundError: If no template with that name exists.
    """
    path = TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template '{name}' not found")
    path.unlink()
