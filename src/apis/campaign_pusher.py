"""Live Google Ads push: turn a `CampaignPlan` into real entities via the API.

Walks the plan in dependency order (budget → campaign → targeting → ad groups →
keywords → RSAs → assets → asset links) and issues batched `mutate_*` calls
against the live API. Designed to be re-runnable (each push creates *new*
entities with timestamped names so we don't accidentally collide with prior
test runs).

The classic SEM Master flow stops at the Google Ads Editor CSV; this module
is the final mile that takes the CSV-equivalent data and posts it through the
SDK.

Failure mode: every batched operation is wrapped so any GoogleAdsException
bubbles up with the failing operation index — partial pushes leave a clear
trail of what got created (logged via `PushReport`) so the operator can
either re-run or manually clean up.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, Iterable

from src.apis.errors import GoogleAdsApiError
from src.apis.google_ads import _normalize_customer_id, _wrap_google_ads_error
from src.models.campaign import (
    Campaign,
    CampaignPlan,
    LeadFormExtension,
    PromotionExtension,
    Sitelink,
    Callout,
)

if TYPE_CHECKING:  # pragma: no cover
    from google.ads.googleads.client import GoogleAdsClient

logger = logging.getLogger(__name__)


# Google Ads geo target constant IDs we use
SWEDEN_GEO_ID = 2752
US_GEO_ID = 2840  # for english travel campaigns we typically also include this
ENGLISH_LANG_ID = 1000
SWEDISH_LANG_ID = 1053

# Default batch size — Google Ads supports up to 5,000 operations per mutate
# call, but smaller batches give faster failure feedback and clearer logs.
DEFAULT_BATCH_SIZE = 200


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class EntityResult:
    """One created entity with its resource name + optional source label."""

    kind: str
    resource_name: str
    label: str = ""


@dataclass
class PushReport:
    """Summary of what got pushed."""

    customer_id: str
    budgets: list[EntityResult] = field(default_factory=list)
    campaigns: list[EntityResult] = field(default_factory=list)
    campaign_criteria: list[EntityResult] = field(default_factory=list)
    ad_groups: list[EntityResult] = field(default_factory=list)
    keywords: list[EntityResult] = field(default_factory=list)
    ads: list[EntityResult] = field(default_factory=list)
    assets: list[EntityResult] = field(default_factory=list)
    asset_links: list[EntityResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    dry_run: bool = False

    def total_entities(self) -> int:
        return (
            len(self.budgets)
            + len(self.campaigns)
            + len(self.campaign_criteria)
            + len(self.ad_groups)
            + len(self.keywords)
            + len(self.ads)
            + len(self.assets)
            + len(self.asset_links)
        )

    def summary(self) -> str:
        return (
            f"customer={self.customer_id} elapsed={self.elapsed_seconds:.1f}s "
            f"{'(DRY RUN) ' if self.dry_run else ''}"
            f"budgets={len(self.budgets)} campaigns={len(self.campaigns)} "
            f"criteria={len(self.campaign_criteria)} ad_groups={len(self.ad_groups)} "
            f"keywords={len(self.keywords)} ads={len(self.ads)} "
            f"assets={len(self.assets)} asset_links={len(self.asset_links)}"
        )


@dataclass
class BidUpdate:
    """One intended ad-group bid update (built from today's bid_rules eval)."""

    campaign_name: str
    ad_group_name: str
    modifier: float
    new_cpc_micros: int


@dataclass
class BidApplyReport:
    """Summary of an `apply_bids` run.

    - `intended_updates` is what the bid-rules engine computed for TODAY
       given the current `case.yaml` (one per ad group in the plan).
    - `applied` is the subset that actually mutated live (intended ∩ live ads).
    - `skipped` is the subset that had no live counterpart by name (typical
       cause: pusher was run with a different `name_suffix`).
    """

    customer_id: str
    intended_updates: list[BidUpdate] = field(default_factory=list)
    applied: list[BidUpdate] = field(default_factory=list)
    skipped: list[BidUpdate] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    dry_run: bool = False

    def summary(self) -> str:
        mode = "DRY RUN" if self.dry_run else "applied"
        return (
            f"customer={self.customer_id} {mode}: "
            f"intended={len(self.intended_updates)} "
            f"applied={len(self.applied)} skipped={len(self.skipped)} "
            f"elapsed={self.elapsed_seconds:.1f}s"
        )


# ---------------------------------------------------------------------------
# Helpers — micros, batching, error wrapping
# ---------------------------------------------------------------------------


def sek_to_micros(value: float) -> int:
    """Convert SEK (or any currency) value to micros (×1,000,000)."""
    return int(round(value * 1_000_000))


def _batched(iterable: Iterable, size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _safe_mutate(call, customer_id: str, operations: list, *, label: str):
    """Wrap a mutate call so SDK errors come back as GoogleAdsApiError with context."""
    try:
        return call(customer_id=customer_id, operations=operations)
    except Exception as exc:
        wrapped = _wrap_google_ads_error(exc)
        raise GoogleAdsApiError(
            f"{label} mutate failed ({len(operations)} ops): {wrapped}",
            hint=getattr(wrapped, "hint", ""),
        ) from exc


# ---------------------------------------------------------------------------
# Bid strategy mapping
# ---------------------------------------------------------------------------


def _apply_bid_strategy(client: "GoogleAdsClient", campaign, strategy: str) -> None:
    """Set the appropriate one-of bid-strategy field on a Campaign proto.

    Google Ads API field names (v20):
      - manual_cpc           → "Manual CPC"
      - target_spend         → "Maximize Clicks"  (NOT `maximize_clicks` — that
                                                   field does not exist on Campaign)
      - maximize_conversions → "Maximize Conversions"
      - maximize_conversion_value → "Maximize Conversion Value"
      - target_cpa, target_roas, target_impression_share, etc. require
        additional inputs (target value), so we set them as empty + let the
        operator fill in via the UI when going live.

    Falls back to manual CPC for any unknown strategy.
    """
    s = strategy.upper()
    if s == "MANUAL_CPC":
        campaign.manual_cpc.enhanced_cpc_enabled = False
    elif s == "MAXIMIZE_CLICKS":
        client.copy_from(campaign.target_spend, client.get_type("TargetSpend"))
    elif s == "MAXIMIZE_CONVERSIONS":
        client.copy_from(
            campaign.maximize_conversions, client.get_type("MaximizeConversions"),
        )
    elif s == "MAXIMIZE_CONVERSION_VALUE":
        client.copy_from(
            campaign.maximize_conversion_value,
            client.get_type("MaximizeConversionValue"),
        )
    elif s == "TARGET_CPA":
        # Falls back to Maximize Conversions — the operator must set the
        # target CPA value in the UI before flipping to ENABLED.
        client.copy_from(
            campaign.maximize_conversions, client.get_type("MaximizeConversions"),
        )
    elif s == "TARGET_ROAS":
        client.copy_from(
            campaign.maximize_conversion_value,
            client.get_type("MaximizeConversionValue"),
        )
    elif s == "TARGET_IMPRESSION_SHARE":
        campaign.manual_cpc.enhanced_cpc_enabled = False
    else:
        campaign.manual_cpc.enhanced_cpc_enabled = False


# ---------------------------------------------------------------------------
# The pusher
# ---------------------------------------------------------------------------


@dataclass
class CampaignPusher:
    """Pushes a `CampaignPlan` into a real Google Ads account.

    Construct with a `customer_id` and either an explicit `client` or rely on
    the lazy `_get_client()` factory. Call `push(plan)` to execute.

    Lead-form behavior: Google requires a one-time manual ToS acceptance in
    the Google Ads UI before lead-form assets can be created via the API.
    `skip_lead_forms=True` skips them entirely; otherwise the push attempts
    them but treats `LEAD_FORM_MISSING_AGREEMENT` as a non-fatal warning so
    the rest of the plan still lands.
    """

    customer_id: str
    client: Any | None = None
    dry_run: bool = False
    batch_size: int = DEFAULT_BATCH_SIZE
    name_suffix: str = ""  # appended to entity names for uniqueness / re-runs
    skip_lead_forms: bool = False
    warnings: list[str] = field(default_factory=list)

    def _get_client(self):
        if self.client is None:
            from src.auth.google_ads_auth import get_google_ads_client
            self.client = get_google_ads_client(customer_id=self.customer_id)
        return self.client

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def push(self, plan: CampaignPlan) -> PushReport:
        """Push the entire plan. Returns a `PushReport` with every resource name."""
        clean_id = _normalize_customer_id(self.customer_id)
        report = PushReport(customer_id=self.customer_id, dry_run=self.dry_run)
        if not plan.campaigns:
            return report

        start = time.perf_counter()

        client = self._get_client()
        logger.info(
            "Pushing plan to %s (%d campaigns, %d ad groups, dry_run=%s)",
            self.customer_id,
            len(plan.campaigns),
            sum(len(c.ad_groups) for c in plan.campaigns),
            self.dry_run,
        )

        for campaign in plan.campaigns:
            budget_rn = self._push_budget(client, clean_id, campaign, report)
            campaign_rn = self._push_campaign(client, clean_id, campaign, budget_rn, report)
            self._push_campaign_targeting(client, clean_id, campaign, campaign_rn, report)
            ag_rn_by_name = self._push_ad_groups(client, clean_id, campaign, campaign_rn, report)
            self._push_keywords(client, clean_id, campaign, ag_rn_by_name, report)
            self._push_ads(client, clean_id, campaign, ag_rn_by_name, report)

            # Plan-level assets (the same plan-level sitelinks / callouts / lead-
            # forms are reused across every campaign).
            self._push_sitelinks(client, clean_id, plan.sitelinks, campaign_rn, report)
            self._push_callouts(client, clean_id, plan.callouts, campaign_rn, report)
            if not self.skip_lead_forms:
                try:
                    self._push_lead_forms(client, clean_id, plan.lead_forms, campaign.name, campaign_rn, report)
                except GoogleAdsApiError as exc:
                    if "LEAD_FORM_MISSING_AGREEMENT" in str(exc):
                        warn = (
                            "Lead-form push skipped: Google requires manual ToS "
                            "acceptance in the Ads UI before lead forms can be "
                            "created via the API. Re-run with --skip-lead-forms "
                            "after the operator clicks accept once. (campaign="
                            + campaign.name + ")"
                        )
                        logger.warning(warn)
                        self.warnings.append(warn)
                    else:
                        raise

            # Promotion extensions targeted at this campaign's ad groups
            campaign_promotions = [p for p in plan.promotions if p.campaign_name == campaign.name]
            self._push_promotions(client, clean_id, campaign_promotions, ag_rn_by_name, campaign_rn, report)

        report.elapsed_seconds = time.perf_counter() - start
        logger.info("Push complete: %s", report.summary())
        return report

    # ------------------------------------------------------------------
    # Seasonality: apply today's bid plan to an EXISTING live campaign
    # ------------------------------------------------------------------

    def apply_bids(
        self,
        plan: CampaignPlan,
        *,
        base_cpc_micros: int = 5_000_000,
    ) -> "BidApplyReport":
        """Apply today's bid_modifier plan to the LIVE campaign in-place.

        Use case: a campaign was pushed weeks ago; today the SUMMER_SALE
        window flipped open. Instead of creating a new campaign (`sem case
        push --auto-suffix`), this command walks the live ad groups and
        updates each one's `cpc_bid_micros` to `base_cpc_micros * modifier`.

        Match strategy: by ad-group NAME. The pusher must have created the
        campaign with the same names this plan uses — which it does, since
        both flow from the same case.yaml. If `name_suffix` was used on
        creation, pass the same suffix here so the lookup hits.

        Returns a `BidApplyReport` listing which ad groups would be
        updated, by how much. In `dry_run` mode no API calls are made.

        Note on bid strategy compatibility: this updates `cpc_bid_micros`,
        which Google Ads honours under MANUAL_CPC and MAXIMIZE_CLICKS.
        Under Smart Bidding (TARGET_ROAS / MAXIMIZE_CONVERSION_VALUE), the
        CPC is ignored and the same intent must be expressed via
        `ad_group.effective_target_roas` overrides — see the docstring for
        `apply_target_roas_overrides` (future work).
        """
        clean_id = _normalize_customer_id(self.customer_id)
        report = BidApplyReport(customer_id=self.customer_id, dry_run=self.dry_run)
        start = time.perf_counter()

        for campaign in plan.campaigns:
            campaign_name = self._unique_name(campaign.name)
            for ag in campaign.ad_groups:
                ag_name = self._unique_name(ag.name)
                target_cpc = int(base_cpc_micros * ag.bid_modifier)
                report.intended_updates.append(
                    BidUpdate(
                        campaign_name=campaign_name,
                        ad_group_name=ag_name,
                        modifier=ag.bid_modifier,
                        new_cpc_micros=target_cpc,
                    )
                )

        if self.dry_run:
            report.elapsed_seconds = time.perf_counter() - start
            return report

        client = self._get_client()
        ad_group_service = client.get_service("AdGroupService")
        ga_service = client.get_service("GoogleAdsService")

        # 1. Look up live ad-group resource names by name (one query per
        # campaign — cheap, but batchable if scale grows).
        rn_by_name: dict[str, str] = {}
        for campaign in plan.campaigns:
            campaign_name = self._unique_name(campaign.name)
            # Escape single quotes for safety in the GAQL string literal.
            escaped = campaign_name.replace("'", "\\'")
            query = (
                "SELECT ad_group.resource_name, ad_group.name "
                "FROM ad_group "
                f"WHERE campaign.name = '{escaped}'"
            )
            stream = ga_service.search_stream(customer_id=clean_id, query=query)
            for batch in stream:
                for row in batch.results:
                    rn_by_name[row.ad_group.name] = row.ad_group.resource_name

        # 2. Compose mutate operations, skipping ad groups not found.
        ops = []
        applied: list[BidUpdate] = []
        for update in report.intended_updates:
            rn = rn_by_name.get(update.ad_group_name)
            if rn is None:
                report.skipped.append(update)
                continue
            op = client.get_type("AdGroupOperation")
            ag_proto = op.update
            ag_proto.resource_name = rn
            ag_proto.cpc_bid_micros = update.new_cpc_micros
            # FieldMask: cpc_bid_micros only — leave everything else alone.
            client.copy_from(
                op.update_mask,
                client.get_type("FieldMask")(paths=["cpc_bid_micros"]),
            )
            ops.append(op)
            applied.append(update)

        # 3. Batch and mutate.
        if ops:
            for chunk in _batched(ops, self.batch_size):
                _safe_mutate(
                    ad_group_service.mutate_ad_groups, clean_id, chunk,
                    label="AdGroup (apply_bids)",
                )
        report.applied = applied
        report.elapsed_seconds = time.perf_counter() - start
        logger.info(
            "apply_bids: %d intended, %d applied, %d skipped (no live match), %.1fs",
            len(report.intended_updates), len(report.applied), len(report.skipped),
            report.elapsed_seconds,
        )
        return report

    # ------------------------------------------------------------------
    # Budget
    # ------------------------------------------------------------------

    def _push_budget(self, client, customer_id, campaign: Campaign, report: PushReport) -> str:
        if self.dry_run:
            rn = f"customers/{customer_id}/campaignBudgets/dryrun-{campaign.name}"
            report.budgets.append(EntityResult("budget", rn, campaign.name))
            return rn

        op = client.get_type("CampaignBudgetOperation")
        budget = op.create
        budget.name = self._unique_name(f"{campaign.name} budget")
        budget.amount_micros = sek_to_micros(campaign.budget_sek_daily)
        budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget.explicitly_shared = False

        service = client.get_service("CampaignBudgetService")
        resp = _safe_mutate(
            service.mutate_campaign_budgets, customer_id, [op],
            label="CampaignBudget",
        )
        rn = resp.results[0].resource_name
        report.budgets.append(EntityResult("budget", rn, campaign.name))
        return rn

    # ------------------------------------------------------------------
    # Campaign
    # ------------------------------------------------------------------

    def _push_campaign(self, client, customer_id, campaign: Campaign, budget_rn: str, report: PushReport) -> str:
        if self.dry_run:
            rn = f"customers/{customer_id}/campaigns/dryrun-{campaign.name}"
            report.campaigns.append(EntityResult("campaign", rn, campaign.name))
            return rn

        op = client.get_type("CampaignOperation")
        c = op.create
        c.name = self._unique_name(campaign.name)
        c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
        c.status = client.enums.CampaignStatusEnum.PAUSED  # always paused on first push
        c.campaign_budget = budget_rn
        _apply_bid_strategy(client, c, campaign.bid_strategy)
        # Make sure search network only (no display partners on a brand-new
        # SEM campaign — caller can flip later in the UI).
        c.network_settings.target_google_search = True
        c.network_settings.target_search_network = True
        c.network_settings.target_content_network = False
        c.network_settings.target_partner_search_network = False
        # EU political advertising declaration — REQUIRED by Google as of 2024.
        # The catalog engine is for commercial travel, not political ads.
        c.contains_eu_political_advertising = (
            client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
        )

        service = client.get_service("CampaignService")
        resp = _safe_mutate(
            service.mutate_campaigns, customer_id, [op],
            label="Campaign",
        )
        rn = resp.results[0].resource_name
        report.campaigns.append(EntityResult("campaign", rn, campaign.name))
        return rn

    # ------------------------------------------------------------------
    # Campaign targeting (geo + language)
    # ------------------------------------------------------------------

    def _push_campaign_targeting(self, client, customer_id, campaign: Campaign, campaign_rn: str, report: PushReport) -> None:
        if self.dry_run:
            return
        ops = []
        # Language(s)
        for lang_code in campaign.language_codes or ["en"]:
            lang_id = SWEDISH_LANG_ID if lang_code == "sv" else ENGLISH_LANG_ID
            op = client.get_type("CampaignCriterionOperation")
            crit = op.create
            crit.campaign = campaign_rn
            crit.language.language_constant = f"languageConstants/{lang_id}"
            ops.append(op)

        # Geo targets — fall back to Sweden if not specified
        geos_to_add = list(campaign.geo_targets) if campaign.geo_targets else []
        if not geos_to_add:
            # Default to "all locations / no restriction" → skip geo criteria
            pass
        for g in geos_to_add:
            geo_id = g.google_geo_id
            if geo_id is None:
                continue
            op = client.get_type("CampaignCriterionOperation")
            crit = op.create
            crit.campaign = campaign_rn
            crit.location.geo_target_constant = f"geoTargetConstants/{geo_id}"
            ops.append(op)

        if not ops:
            return
        service = client.get_service("CampaignCriterionService")
        resp = _safe_mutate(
            service.mutate_campaign_criteria, customer_id, ops,
            label="CampaignCriterion",
        )
        for r in resp.results:
            report.campaign_criteria.append(EntityResult("campaign_criterion", r.resource_name))

    # ------------------------------------------------------------------
    # Ad groups (batched)
    # ------------------------------------------------------------------

    def _push_ad_groups(
        self, client, customer_id, campaign: Campaign, campaign_rn: str, report: PushReport
    ) -> dict[str, str]:
        ag_rn_by_name: dict[str, str] = {}
        # Pre-build all operations so we can batch
        all_ops: list[tuple[str, Any]] = []
        for ag in campaign.ad_groups:
            if self.dry_run:
                ag_rn_by_name[ag.name] = (
                    f"customers/{customer_id}/adGroups/dryrun-{ag.name}"
                )
                report.ad_groups.append(EntityResult("ad_group", ag_rn_by_name[ag.name], ag.name))
                continue
            op = client.get_type("AdGroupOperation")
            ag_proto = op.create
            ag_proto.name = self._unique_name(ag.name)
            ag_proto.campaign = campaign_rn
            ag_proto.status = client.enums.AdGroupStatusEnum.PAUSED
            ag_proto.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
            if ag.max_cpc_sek is not None:
                ag_proto.cpc_bid_micros = sek_to_micros(ag.max_cpc_sek)
            # Ad-group-level bid modifier (relative to base) is applied via
            # campaign_criterion if needed; for now we let the cpc_bid_micros
            # cover the absolute lever.
            all_ops.append((ag.name, op))

        if self.dry_run:
            return ag_rn_by_name

        service = client.get_service("AdGroupService")
        for chunk in _batched(all_ops, self.batch_size):
            ops = [o for _, o in chunk]
            names = [n for n, _ in chunk]
            resp = _safe_mutate(
                service.mutate_ad_groups, customer_id, ops,
                label="AdGroup",
            )
            for name, result in zip(names, resp.results):
                ag_rn_by_name[name] = result.resource_name
                report.ad_groups.append(EntityResult("ad_group", result.resource_name, name))
        return ag_rn_by_name

    # ------------------------------------------------------------------
    # Keywords (batched)
    # ------------------------------------------------------------------

    def _push_keywords(self, client, customer_id, campaign: Campaign, ag_rn_by_name: dict[str, str], report: PushReport) -> None:
        match_type_enum = client.enums.KeywordMatchTypeEnum
        match_map = {
            "BROAD": match_type_enum.BROAD,
            "PHRASE": match_type_enum.PHRASE,
            "EXACT": match_type_enum.EXACT,
        }
        all_ops: list[Any] = []
        for ag in campaign.ad_groups:
            ag_rn = ag_rn_by_name.get(ag.name)
            if ag_rn is None:
                continue
            ag_final_url = str(ag.ads[0].final_url) if ag.ads else None
            for kw in ag.keywords:
                if self.dry_run:
                    report.keywords.append(EntityResult(
                        "keyword",
                        f"customers/{customer_id}/adGroupCriteria/dryrun-{ag.name}-{kw.text}",
                        f"{ag.name}/{kw.text}",
                    ))
                    continue
                op = client.get_type("AdGroupCriterionOperation")
                crit = op.create
                crit.ad_group = ag_rn
                crit.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
                crit.keyword.text = kw.text
                crit.keyword.match_type = match_map.get(kw.match_type, match_type_enum.PHRASE)
                if ag_final_url:
                    crit.final_urls.append(ag_final_url)
                all_ops.append(op)

        if self.dry_run or not all_ops:
            return

        service = client.get_service("AdGroupCriterionService")
        for chunk in _batched(all_ops, self.batch_size):
            resp = _safe_mutate(
                service.mutate_ad_group_criteria, customer_id, chunk,
                label="Keyword",
            )
            for r in resp.results:
                report.keywords.append(EntityResult("keyword", r.resource_name))

    # ------------------------------------------------------------------
    # RSAs (batched)
    # ------------------------------------------------------------------

    def _push_ads(self, client, customer_id, campaign: Campaign, ag_rn_by_name: dict[str, str], report: PushReport) -> None:
        all_ops: list[Any] = []
        for ag in campaign.ad_groups:
            ag_rn = ag_rn_by_name.get(ag.name)
            if ag_rn is None:
                continue
            for ad in ag.ads:
                if self.dry_run:
                    report.ads.append(EntityResult(
                        "rsa",
                        f"customers/{customer_id}/adGroupAds/dryrun-{ag.name}",
                        ag.name,
                    ))
                    continue
                op = client.get_type("AdGroupAdOperation")
                ag_ad = op.create
                ag_ad.ad_group = ag_rn
                ag_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
                ad_proto = ag_ad.ad
                ad_proto.final_urls.append(str(ad.final_url))
                if ad.path1:
                    ad_proto.responsive_search_ad.path1 = ad.path1
                if ad.path2:
                    ad_proto.responsive_search_ad.path2 = ad.path2
                for i, headline in enumerate(ad.headlines):
                    asset = client.get_type("AdTextAsset")
                    asset.text = headline.text
                    if i == 0:
                        asset.pinned_field = client.enums.ServedAssetFieldTypeEnum.HEADLINE_1
                    elif i == 1:
                        asset.pinned_field = client.enums.ServedAssetFieldTypeEnum.HEADLINE_2
                    ad_proto.responsive_search_ad.headlines.append(asset)
                for i, desc in enumerate(ad.descriptions):
                    asset = client.get_type("AdTextAsset")
                    asset.text = desc.text
                    if i == 0:
                        asset.pinned_field = client.enums.ServedAssetFieldTypeEnum.DESCRIPTION_1
                    ad_proto.responsive_search_ad.descriptions.append(asset)
                all_ops.append(op)

        if self.dry_run or not all_ops:
            return

        service = client.get_service("AdGroupAdService")
        for chunk in _batched(all_ops, self.batch_size):
            resp = _safe_mutate(
                service.mutate_ad_group_ads, customer_id, chunk,
                label="AdGroupAd",
            )
            for r in resp.results:
                report.ads.append(EntityResult("rsa", r.resource_name))

    # ------------------------------------------------------------------
    # Sitelink assets
    # ------------------------------------------------------------------

    def _push_sitelinks(
        self, client, customer_id, sitelinks: list[Sitelink], campaign_rn: str, report: PushReport
    ) -> None:
        if not sitelinks or self.dry_run:
            if self.dry_run:
                for sl in sitelinks:
                    report.assets.append(EntityResult("sitelink_asset", f"dryrun:{sl.text}", sl.text))
            return

        # 1. Create assets
        asset_ops = []
        for sl in sitelinks:
            op = client.get_type("AssetOperation")
            a = op.create
            a.sitelink_asset.link_text = sl.text
            a.sitelink_asset.description1 = sl.desc1
            a.sitelink_asset.description2 = sl.desc2
            a.final_urls.append(str(sl.final_url))
            asset_ops.append(op)
        asset_service = client.get_service("AssetService")
        asset_resp = _safe_mutate(asset_service.mutate_assets, customer_id, asset_ops, label="SitelinkAsset")
        asset_rns = [r.resource_name for r in asset_resp.results]
        for rn in asset_rns:
            report.assets.append(EntityResult("sitelink_asset", rn))

        # 2. Link to campaign
        link_ops = []
        for rn in asset_rns:
            link_op = client.get_type("CampaignAssetOperation")
            link = link_op.create
            link.campaign = campaign_rn
            link.asset = rn
            link.field_type = client.enums.AssetFieldTypeEnum.SITELINK
            link_ops.append(link_op)
        link_service = client.get_service("CampaignAssetService")
        link_resp = _safe_mutate(
            link_service.mutate_campaign_assets, customer_id, link_ops,
            label="CampaignAsset(Sitelink)",
        )
        for r in link_resp.results:
            report.asset_links.append(EntityResult("campaign_asset", r.resource_name))

    # ------------------------------------------------------------------
    # Callout assets
    # ------------------------------------------------------------------

    def _push_callouts(self, client, customer_id, callouts: list[Callout], campaign_rn: str, report: PushReport) -> None:
        if not callouts or self.dry_run:
            if self.dry_run:
                for co in callouts:
                    report.assets.append(EntityResult("callout_asset", f"dryrun:{co.text}", co.text))
            return

        asset_ops = []
        for co in callouts:
            op = client.get_type("AssetOperation")
            op.create.callout_asset.callout_text = co.text
            asset_ops.append(op)
        asset_service = client.get_service("AssetService")
        asset_resp = _safe_mutate(asset_service.mutate_assets, customer_id, asset_ops, label="CalloutAsset")
        asset_rns = [r.resource_name for r in asset_resp.results]
        for rn in asset_rns:
            report.assets.append(EntityResult("callout_asset", rn))

        link_ops = []
        for rn in asset_rns:
            link_op = client.get_type("CampaignAssetOperation")
            link = link_op.create
            link.campaign = campaign_rn
            link.asset = rn
            link.field_type = client.enums.AssetFieldTypeEnum.CALLOUT
            link_ops.append(link_op)
        link_service = client.get_service("CampaignAssetService")
        link_resp = _safe_mutate(
            link_service.mutate_campaign_assets, customer_id, link_ops,
            label="CampaignAsset(Callout)",
        )
        for r in link_resp.results:
            report.asset_links.append(EntityResult("campaign_asset", r.resource_name))

    # ------------------------------------------------------------------
    # Lead form assets
    # ------------------------------------------------------------------

    def _push_lead_forms(
        self,
        client,
        customer_id,
        lead_forms: list[LeadFormExtension],
        campaign_name: str,
        campaign_rn: str,
        report: PushReport,
    ) -> None:
        forms = [lf for lf in lead_forms if lf.campaign_name == campaign_name]
        if not forms:
            return
        if self.dry_run:
            for lf in forms:
                report.assets.append(EntityResult("lead_form_asset", f"dryrun:{lf.form_name}", lf.form_name))
            return

        cta_enum = client.enums.LeadFormCallToActionTypeEnum
        field_enum = client.enums.LeadFormFieldUserInputTypeEnum

        def _enum_lookup(enum_cls, name: str, fallback_name: str):
            """Best-effort enum resolver: try the exact name, then a fallback,
            then the enum's UNKNOWN value. Lets the case author pass any name
            the SDK accepts without the pusher hard-coding the full set."""
            for candidate in (name, fallback_name):
                if candidate is None:
                    continue
                try:
                    return getattr(enum_cls, candidate)
                except AttributeError:
                    continue
            try:
                return enum_cls.UNKNOWN
            except AttributeError:
                return None

        # Common aliases: SDK calls "WORK_PHONE" what other docs call
        # "WORK_PHONE_NUMBER", and so on.
        _FIELD_ALIASES = {
            "WORK_PHONE_NUMBER": "WORK_PHONE",
            "GIVEN_NAME": "FIRST_NAME",
            "FAMILY_NAME": "LAST_NAME",
            "ZIP_CODE": "POSTAL_CODE",
        }
        _CTA_ALIASES = {
            "GET_OFFER": "GET_QUOTE",  # GET_OFFER doesn't exist on newer SDKs
        }

        asset_ops = []
        for lf in forms:
            op = client.get_type("AssetOperation")
            a = op.create
            a.name = lf.asset_name or lf.form_name
            lfa = a.lead_form_asset
            lfa.business_name = lf.business_name
            lfa.headline = lf.headline
            lfa.description = lf.description
            lfa.privacy_policy_url = str(lf.privacy_url)
            lfa.call_to_action_type = _enum_lookup(
                cta_enum, lf.cta, _CTA_ALIASES.get(lf.cta, "GET_QUOTE"),
            )
            lfa.call_to_action_description = lf.cta_description
            lfa.post_submit_headline = lf.submit_headline
            lfa.post_submit_description = lf.submit_description
            for fld in lf.fields:
                inp = client.get_type("LeadFormField")
                inp.input_type = _enum_lookup(
                    field_enum, fld, _FIELD_ALIASES.get(fld, "EMAIL"),
                )
                lfa.fields.append(inp)
            asset_ops.append(op)
        asset_service = client.get_service("AssetService")
        asset_resp = _safe_mutate(asset_service.mutate_assets, customer_id, asset_ops, label="LeadFormAsset")
        asset_rns = [r.resource_name for r in asset_resp.results]
        for rn in asset_rns:
            report.assets.append(EntityResult("lead_form_asset", rn))

        link_ops = []
        for rn in asset_rns:
            link_op = client.get_type("CampaignAssetOperation")
            link = link_op.create
            link.campaign = campaign_rn
            link.asset = rn
            link.field_type = client.enums.AssetFieldTypeEnum.LEAD_FORM
            link_ops.append(link_op)
        link_service = client.get_service("CampaignAssetService")
        link_resp = _safe_mutate(
            link_service.mutate_campaign_assets, customer_id, link_ops,
            label="CampaignAsset(LeadForm)",
        )
        for r in link_resp.results:
            report.asset_links.append(EntityResult("campaign_asset", r.resource_name))

    # ------------------------------------------------------------------
    # Promotion assets — link to ad groups
    # ------------------------------------------------------------------

    def _push_promotions(
        self,
        client,
        customer_id,
        promotions: list[PromotionExtension],
        ag_rn_by_name: dict[str, str],
        campaign_rn: str,
        report: PushReport,
    ) -> None:
        if not promotions:
            return
        if self.dry_run:
            for promo in promotions:
                report.assets.append(EntityResult(
                    "promotion_asset", f"dryrun:{promo.ad_group_name}", promo.ad_group_name or "",
                ))
            return

        discount_enum = client.enums.PromotionExtensionDiscountModifierEnum
        occasion_enum = client.enums.PromotionExtensionOccasionEnum

        asset_ops = []
        link_targets: list[tuple[str, str | None]] = []  # (ad_group_rn or None, label)
        for promo in promotions:
            op = client.get_type("AssetOperation")
            a = op.create
            pa = a.promotion_asset
            if promo.percent_off is not None:
                # PromotionAsset.percent_off uses 10,000 = 1% (NOT 1,000,000
                # as the legacy docs claim — empirically verified against the
                # live API). 38% → 380,000.
                pa.percent_off = int(round(promo.percent_off * 10_000))
            elif promo.money_amount_off is not None:
                pa.money_amount_off.currency_code = promo.money_currency
                pa.money_amount_off.amount_micros = sek_to_micros(promo.money_amount_off)
            if promo.discount_modifier == "UP_TO":
                pa.discount_modifier = discount_enum.UP_TO
            # `promotion_target` is required by Google and capped at 20
            # characters. We use a trimmed version of the ad group name —
            # which is the product/destination name + SKU. Drop the SKU
            # suffix in parentheses if present, then truncate.
            target_label = (promo.ad_group_name or "Offer").split(" (")[0]
            pa.promotion_target = target_label[:20]
            if promo.occasion:
                try:
                    pa.occasion = getattr(occasion_enum, promo.occasion)
                except (AttributeError, TypeError):
                    pass
            if promo.start_date:
                pa.start_date = promo.start_date.isoformat()
            if promo.end_date:
                pa.end_date = promo.end_date.isoformat()
            a.final_urls.append(str(promo.final_url))
            # Asset names accept ~80 chars; trim defensively
            promo_label = f"Promo {promo.ad_group_name or ''} {promo.percent_off or promo.money_amount_off or ''}"
            a.name = promo_label[:78]
            pa.language_code = promo.language
            if promo.promotion_code:
                pa.promotion_code = promo.promotion_code
            if promo.orders_over_amount is not None:
                pa.orders_over_amount.currency_code = promo.money_currency
                pa.orders_over_amount.amount_micros = sek_to_micros(promo.orders_over_amount)
            asset_ops.append(op)
            ag_rn = ag_rn_by_name.get(promo.ad_group_name) if promo.ad_group_name else None
            link_targets.append((ag_rn, promo.ad_group_name))

        if not asset_ops:
            return

        asset_service = client.get_service("AssetService")
        asset_rns: list[str] = []
        # Batch through promotions
        for chunk_ops, chunk_targets in _zip_batches(asset_ops, link_targets, self.batch_size):
            resp = _safe_mutate(
                asset_service.mutate_assets, customer_id, chunk_ops,
                label="PromotionAsset",
            )
            for r in resp.results:
                asset_rns.append(r.resource_name)
                report.assets.append(EntityResult("promotion_asset", r.resource_name))

        # Now link each to its ad group (or campaign if no ad-group target)
        ag_link_service = client.get_service("AdGroupAssetService")
        camp_link_service = client.get_service("CampaignAssetService")
        ag_link_ops = []
        camp_link_ops = []
        for rn, (ag_rn, label) in zip(asset_rns, link_targets):
            if ag_rn is not None:
                op = client.get_type("AdGroupAssetOperation")
                link = op.create
                link.ad_group = ag_rn
                link.asset = rn
                link.field_type = client.enums.AssetFieldTypeEnum.PROMOTION
                ag_link_ops.append(op)
            else:
                op = client.get_type("CampaignAssetOperation")
                link = op.create
                link.campaign = campaign_rn
                link.asset = rn
                link.field_type = client.enums.AssetFieldTypeEnum.PROMOTION
                camp_link_ops.append(op)

        for chunk in _batched(ag_link_ops, self.batch_size):
            resp = _safe_mutate(
                ag_link_service.mutate_ad_group_assets, customer_id, chunk,
                label="AdGroupAsset(Promotion)",
            )
            for r in resp.results:
                report.asset_links.append(EntityResult("ad_group_asset", r.resource_name))
        for chunk in _batched(camp_link_ops, self.batch_size):
            resp = _safe_mutate(
                camp_link_service.mutate_campaign_assets, customer_id, chunk,
                label="CampaignAsset(Promotion)",
            )
            for r in resp.results:
                report.asset_links.append(EntityResult("campaign_asset", r.resource_name))

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _unique_name(self, base: str) -> str:
        return f"{base}{self.name_suffix}" if self.name_suffix else base


def _zip_batches(a: list, b: list, size: int):
    """Yield matched (chunk_of_a, chunk_of_b) batches."""
    for start in range(0, len(a), size):
        yield a[start : start + size], b[start : start + size]


__all__ = [
    "CampaignPusher",
    "PushReport",
    "EntityResult",
    "sek_to_micros",
]
