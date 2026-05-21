"""Lead Form extension generator — one per campaign from a config-driven template.

The template lives in `clients/<slug>/case.yaml` under `lead_form:`. We
materialize it once per campaign in the plan. If the template's `headline`
contains `{destination}` or other placeholders, we leave them as-is for
campaign-level forms or resolve them when given a `Product`.
"""

from __future__ import annotations

import logging
from typing import Iterable

from src.models.campaign import LeadFormExtension
from src.models.catalog import Product

logger = logging.getLogger(__name__)


_REQUIRED_KEYS = ("form_name", "headline", "description", "privacy_url", "fields")


def _fill_placeholder(text: str, **subs: str) -> str:
    out = text
    for k, v in subs.items():
        out = out.replace("{" + k + "}", v)
    return out


def generate_lead_forms_for_campaigns(
    campaign_names: Iterable[str],
    lead_form_config: dict,
    *,
    representative_product: Product | None = None,
) -> list[LeadFormExtension]:
    """Materialize one LeadFormExtension per campaign from `lead_form_config`.

    Required keys in `lead_form_config`: form_name, headline, description,
    privacy_url, fields. Optional: business_name, cta, submit_headline,
    submit_description, submit_url, asset_name.
    """
    missing = [k for k in _REQUIRED_KEYS if k not in lead_form_config]
    if missing:
        raise ValueError(
            f"lead_form config missing required keys: {missing}. "
            f"Required: {list(_REQUIRED_KEYS)}"
        )

    headline = lead_form_config["headline"]
    description = lead_form_config["description"]
    if representative_product is not None:
        subs = {
            "destination": representative_product.name,
            "name": representative_product.name,
            "sku": representative_product.sku,
        }
        headline = _fill_placeholder(headline, **subs)
        description = _fill_placeholder(description, **subs)

    forms: list[LeadFormExtension] = []
    for campaign in campaign_names:
        forms.append(
            LeadFormExtension(
                campaign_name=campaign,
                asset_name=lead_form_config.get("asset_name", "") or lead_form_config["form_name"],
                form_name=lead_form_config["form_name"],
                headline=headline,
                description=description,
                cta_description=lead_form_config.get("cta_description", ""),
                business_name=lead_form_config.get("business_name", ""),
                cta=lead_form_config.get("cta", "GET_QUOTE"),
                privacy_url=lead_form_config["privacy_url"],
                fields=lead_form_config["fields"],
                submit_headline=lead_form_config.get("submit_headline", "Thanks!"),
                submit_description=lead_form_config.get("submit_description", ""),
                submit_url=lead_form_config.get("submit_url"),
            )
        )
    logger.info("Generated %d lead form extensions", len(forms))
    return forms


__all__ = ["generate_lead_forms_for_campaigns"]
