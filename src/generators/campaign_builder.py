"""Full campaign structure builder for Google Ads.

Three structuring modes:
  - `_structure_by_service`: one campaign per service / keyword group
  - `_structure_by_geo`: one campaign per geographic target
  - `_structure_by_sku`: one campaign (optionally partitioned) per catalog
    row — drives the catalog-engine workflow added in v0.3.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Iterable, Literal

from src.catalog.bid_rules import apply_rules, parse_rules
from src.catalog.url_templating import expand_url_template
from src.generators.ad_copy_generator import generate_rsa, generate_rsa_variants
from src.generators.keyword_generator import (
    assign_match_types,
    generate_keywords_for_product,
    generate_negative_keywords,
)
from src.generators.lead_form_generator import generate_lead_forms_for_campaigns
from src.generators.promotion_extension_generator import generate_promotions_from_products
from src.models.campaign import (
    AdGroup,
    BidSchedule,
    Callout,
    Campaign,
    CampaignPlan,
    CallExtension,
    Keyword,
    LeadFormExtension,
    PromotionExtension,
    ResponsiveSearchAd,
    Sitelink,
    StructuredSnippet,
)
from src.models.catalog import CampaignBuildConfig, Product
from src.models.client import ClientProfile
from src.models.research import DigitalPresence

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
        geo_structured = True
    else:
        campaigns = _structure_by_service(client, keyword_groups)
        geo_structured = False

    # Allocate budget
    campaigns = _allocate_budget(campaigns, client.monthly_budget_sek)

    # Apply ad schedule and bid strategy
    for campaign in campaigns:
        campaign.ad_schedule = _generate_ad_schedule()
        campaign.bid_strategy = _select_bid_strategy(
            int(campaign.budget_sek_daily * 30),
            client.campaign_goals[0].goal_type if client.campaign_goals else "traffic",
        )
        # Geo-structured campaigns own their own single-geo target set already.
        # Service-structured campaigns inherit the full client geo list.
        if not geo_structured:
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
                target_geo=geo,
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
    """Generate ad extensions based on client profile.

    Language-aware: English clients get English defaults, Swedish gets the
    legacy ROT-aware set. Future locales can be added without breaking either.
    """
    website_url = str(client.website_url).rstrip("/")
    industry_lower = client.industry.lower().replace(" ", "_")
    language = client.language

    if language == "en":
        sitelinks = [
            Sitelink(
                text="About Us",
                desc1=f"Learn more about {client.business_name}",
                desc2="Our story and team",
                final_url=f"{website_url}/about",
            ),
            Sitelink(
                text="Our Services",
                desc1="Browse our full offering",
                desc2="Professional solutions",
                final_url=f"{website_url}/services",
            ),
            Sitelink(
                text="Contact Us",
                desc1="Call or message us anytime",
                desc2="Fast response",
                final_url=f"{website_url}/contact",
            ),
            Sitelink(
                text="Get a Quote",
                desc1="Free price estimate",
                desc2="Reply within 24 hours",
                final_url=f"{website_url}/quote",
            ),
        ]
        callout_texts = [
            "Free Quote",
            "Fast Service",
            "Trusted Local Company",
            "Satisfaction Guaranteed",
        ]
        snippets_header_services = "Services"
        snippets_header_locations = "Locations"
    else:
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
        callout_texts = [
            "Fri Offert",
            "Snabb Service",
            "Lokalt Företag",
            "Nöjd Kund-Garanti",
        ]
        # Add ROT-avdrag callout for Swedish home-service industries
        if any(rot in industry_lower for rot in ROT_INDUSTRIES):
            callout_texts.append("ROT-avdrag")
        snippets_header_services = "Tjänster"
        snippets_header_locations = "Platser"

    callouts = [Callout(text=t) for t in callout_texts]

    snippets = []
    if client.products_services:
        snippets.append(
            StructuredSnippet(
                header=snippets_header_services,
                values=client.products_services[:10],
            )
        )

    if client.geographic_targets:
        snippets.append(
            StructuredSnippet(
                header=snippets_header_locations,
                values=[g.name for g in client.geographic_targets[:10]],
            )
        )

    call_extensions: list[CallExtension] = []

    logger.info(
        "Generated extensions: %d sitelinks, %d callouts, %d snippets, %d call ext",
        len(sitelinks), len(callouts), len(snippets), len(call_extensions),
    )
    return sitelinks, callouts, snippets, call_extensions


# =============================================================================
# Catalog-driven structuring (v0.3 — C3)
# =============================================================================


def _format_ad_group_name(template: str, product: Product, max_len: int = 90) -> str:
    """Format an ad group name; clip to Google's 90-char limit."""
    # Start with attributes, then overlay name/sku so top-level fields win
    # (defensive: even if the loader leaves name/sku in attributes, the
    # Product's canonical name takes precedence here).
    fills: dict[str, str] = {}
    for k, v in product.attributes.items():
        if v is None:
            continue
        fills[k] = str(v)
    fills["name"] = product.name
    fills["sku"] = product.sku
    out = template
    for k, v in fills.items():
        out = out.replace("{" + k + "}", v)
    if len(out) > max_len:
        out = out[: max_len - 1] + "…"
    return out


def _format_campaign_name(template: str, client: ClientProfile, **extra) -> str:
    fills = {
        "business_name": client.business_name,
        "industry": client.industry,
    }
    fills.update({k: str(v) for k, v in extra.items() if v is not None})
    out = template
    for k, v in fills.items():
        out = out.replace("{" + k + "}", v)
    return out.strip()


def catalog_row_to_product(row, *, sku_field: str | None = None) -> Product:
    """Adapt a `CatalogRow` into a `Product`.

    Carries the row's `key` as `sku`, `name` as `name`, the row's harvested
    `aliases` as the product's alternate-name list, and all remaining
    attributes through. The optional `sku_field` argument is reserved for
    callers that want to pull the SKU from a different attribute.
    """
    sku = row.attributes.get(sku_field) if sku_field else row.key
    sku = str(sku) if sku is not None else row.key
    name = row.name or sku
    # Strip the primary-key column from attributes if it bled through
    attrs = {k: v for k, v in row.attributes.items() if k != sku_field}
    aliases = list(getattr(row, "aliases", []) or [])
    return Product(sku=sku, name=name, aliases=aliases, attributes=attrs)


def _build_ad_group_for_product(
    product: Product,
    client: ClientProfile,
    build_config: CampaignBuildConfig,
    primary_url_template: str | None,
    parsed_rule_set,  # BidRuleSet | None — kept loose to dodge circular typing
    campaign_name: str,
    *,
    today: date | None = None,
) -> tuple[AdGroup, list[BidSchedule]]:
    """Build one AdGroup (with keywords, RSA, bid rules) for one product.

    v0.3.4 URL behavior: when `primary_url_template` is set, each RSA variant
    inside this ad group gets its own `text=N` value (variant slot → N). The
    ad-group-level fallback URL (used by keywords + Path1/Path2 derivation)
    uses N = `text_n_range[0]` (typically 1), matching the first variant.
    """
    text_n_low, text_n_high = build_config.text_n_range

    # 1. Ad-group-level fallback URL (text=N_low). Used by keyword final_url
    # in the CSV/live push and as the fallback when no template is set.
    if primary_url_template:
        final_url = expand_url_template(primary_url_template, product, n=text_n_low)
    else:
        final_url = str(client.website_url)
    product = product.model_copy(update={"url": final_url})

    # 2. Keywords from templates
    keyword_objs: list[Keyword] = []
    if build_config.keyword_templates:
        keyword_objs = generate_keywords_for_product(
            product,
            build_config.keyword_templates,
            match_types=list(build_config.keyword_match_types),
        )
    keyword_texts = [k.text for k in keyword_objs] or [product.name, product.sku]

    # 3. Negative keywords (industry-level, deduped against this product's terms)
    negatives = generate_negative_keywords(keyword_texts, client.industry)

    # 4. RSA variants (3-5 per ad group, one per lever) — each variant gets
    # its own `text=N` (variant slot → N) per v0.3.4 operator brief.
    rsa_variants = generate_rsa_variants(
        ad_group_theme=product.name,
        client=client,
        keywords=keyword_texts[:5],
        final_url=final_url,
        final_url_template=primary_url_template,
        text_n_range=(text_n_low, text_n_high),
        product=product,
    )

    # 5. Ad group name + bid modifier + schedules
    ag_name = _format_ad_group_name(build_config.ad_group_name_template, product)
    immediate_modifier = 1.0
    schedules: list[BidSchedule] = []
    if parsed_rule_set is not None:
        rule_result = apply_rules(
            product, parsed_rule_set, campaign_name, ag_name, today=today,
        )
        immediate_modifier = rule_result.immediate_modifier
        schedules = list(rule_result.schedules)

    ag = AdGroup(
        name=ag_name,
        theme=product.name,
        keywords=keyword_objs,
        negative_keywords=negatives[:50],
        ads=rsa_variants,
        bid_modifier=immediate_modifier,
    )
    return ag, schedules


def _structure_by_sku(
    client: ClientProfile,
    products: Iterable[Product],
    build_config: CampaignBuildConfig,
    *,
    today: date | None = None,
) -> tuple[list[Campaign], list[BidSchedule]]:
    """Catalog-driven campaign structuring.

    Produces:
      - one parent campaign by default
      - or N campaigns if `partition_by_attribute` is set (one per distinct
        value of that attribute)
    Each Product becomes one AdGroup.
    """
    products = list(products)
    primary_url_template = build_config.url_templates.get("primary")
    # v0.3.4: the ad-group-level NCycler is gone — each variant in an ad
    # group now owns its own `text=N` value (variant slot → N). Keywords
    # inherit the ad-group fallback URL (text=N_low), which lines up with
    # variant 1 for analytics tidiness.

    parsed_rule_set = parse_rules(build_config.bid_rules) if build_config.bid_rules else None

    # Partition products into campaign buckets
    if build_config.partition_by_attribute:
        attr = build_config.partition_by_attribute
        buckets: dict[Any, list[Product]] = {}
        for p in products:
            buckets.setdefault(p.attributes.get(attr), []).append(p)
        # Stable, sorted, with None last
        bucket_keys = sorted(buckets.keys(), key=lambda x: (x is None, str(x)))
    else:
        buckets = {None: products}
        bucket_keys = [None]

    campaigns: list[Campaign] = []
    all_schedules: list[BidSchedule] = []
    for bucket_key in bucket_keys:
        bucket_products = buckets[bucket_key]
        if not bucket_products:
            continue
        partition_label = "" if bucket_key is None else str(bucket_key)
        campaign_name = _format_campaign_name(
            build_config.campaign_name_template,
            client,
            partition=partition_label,
        )
        if partition_label and "{partition}" not in build_config.campaign_name_template:
            campaign_name = f"{campaign_name} - {partition_label}"

        ad_groups: list[AdGroup] = []
        for product in bucket_products:
            ag, ag_schedules = _build_ad_group_for_product(
                product, client, build_config, primary_url_template,
                parsed_rule_set, campaign_name, today=today,
            )
            ad_groups.append(ag)
            all_schedules.extend(ag_schedules)

        campaign = Campaign(
            name=campaign_name,
            campaign_type="SEARCH",
            status="PAUSED",
            budget_sek_daily=0,  # set by _allocate_budget downstream
            language_codes=[client.language],
            ad_groups=ad_groups,
        )
        campaigns.append(campaign)

    logger.info(
        "Catalog build: %d products → %d campaigns, %d ad groups, %d schedules",
        len(products), len(campaigns),
        sum(len(c.ad_groups) for c in campaigns), len(all_schedules),
    )
    return campaigns, all_schedules


def build_campaigns_from_catalog(
    client: ClientProfile,
    products: Iterable[Product],
    build_config: CampaignBuildConfig,
    *,
    lead_form_config: dict | None = None,
    promotion_start_date: date | None = None,
    promotion_end_date: date | None = None,
    promotion_occasion: str | None = None,
    money_currency: str = "SEK",
    today: date | None = None,
) -> CampaignPlan:
    """End-to-end catalog build: structure → bid rules → promotions → lead forms → extensions.

    `today` is forwarded to the bid-rules engine and determines whether any
    `during:` overlay rules fire immediately or fall through to the base
    ladder. Defaults to `date.today()` — production callers can leave this
    unset; tests pass an explicit date to deterministically exercise the
    in-window / out-of-window branches.
    """
    products = list(products)
    campaigns, bid_schedules = _structure_by_sku(
        client, products, build_config, today=today,
    )

    # Budget + bid strategy + schedule
    campaigns = _allocate_budget(campaigns, client.monthly_budget_sek)
    for campaign in campaigns:
        campaign.ad_schedule = _generate_ad_schedule()
        campaign.bid_strategy = _select_bid_strategy(
            int(campaign.budget_sek_daily * 30),
            client.campaign_goals[0].goal_type if client.campaign_goals else "traffic",
        )
        # Catalog campaigns inherit the client's geo list (no geo partitioning)
        campaign.geo_targets = client.geographic_targets

    # Extensions
    sitelinks, callouts, snippets, call_extensions = _generate_extensions(client)

    promotions: list[PromotionExtension] = []
    if build_config.promotion_enabled and build_config.url_templates.get("primary"):
        for campaign in campaigns:
            # Sub-set of products that belong to this campaign — for partitioned
            # builds, only the products that ended up in this bucket
            ag_names = {ag.name for ag in campaign.ad_groups}
            campaign_products = [
                p for p in products
                if _format_ad_group_name(build_config.ad_group_name_template, p) in ag_names
            ]
            promotions.extend(
                generate_promotions_from_products(
                    campaign_products,
                    campaign_name=campaign.name,
                    url_template=build_config.url_templates["primary"],
                    discount_attribute=build_config.promotion_attribute or "discount_pct",
                    ad_group_name_template=build_config.ad_group_name_template,
                    language=client.language,
                    start_date=promotion_start_date,
                    end_date=promotion_end_date,
                    occasion=promotion_occasion,
                    money_currency=money_currency,
                    text_n_range=build_config.text_n_range,
                )
            )

    lead_forms: list[LeadFormExtension] = []
    if lead_form_config:
        rep_product = products[0] if products else None
        lead_forms = generate_lead_forms_for_campaigns(
            [c.name for c in campaigns],
            lead_form_config,
            representative_product=rep_product,
        )

    plan = CampaignPlan(
        campaigns=campaigns,
        sitelinks=sitelinks,
        callouts=callouts,
        snippets=snippets,
        call_extensions=call_extensions,
        promotions=promotions,
        lead_forms=lead_forms,
        bid_schedules=bid_schedules,
    )
    logger.info(
        "Catalog plan complete: %d campaigns, %d ad groups, %d promotions, %d lead forms, %d schedules",
        len(plan.campaigns),
        sum(len(c.ad_groups) for c in plan.campaigns),
        len(plan.promotions),
        len(plan.lead_forms),
        len(plan.bid_schedules),
    )
    return plan
