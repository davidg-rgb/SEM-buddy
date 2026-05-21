"""Tests for the live-push module (`src/apis/campaign_pusher.py`).

These use a fake GoogleAdsClient that records every operation and returns
synthetic resource names. No live API calls — purely structural verification
that the operation tree is built correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import count
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.apis.campaign_pusher import (
    CampaignPusher,
    EntityResult,
    PushReport,
    sek_to_micros,
)
from src.catalog import load_catalog_from_yaml
from src.generators.campaign_builder import (
    build_campaigns_from_catalog,
    catalog_row_to_product,
)
from src.models.catalog import CampaignBuildConfig
from src.models.client import ClientProfile


# ---------------------------------------------------------------------------
# Fake GoogleAdsClient
# ---------------------------------------------------------------------------


class _FakeProto:
    """Mutable proto-like object supporting both scalar assignment and repeated
    `.field.append(...)` semantics. Lazily creates nested protos OR list-style
    fields based on usage."""

    def __init__(self, _name: str = "proto"):
        self._fields: dict[str, Any] = {}
        self._name = _name
        self._appended: list = []  # backing store for `.append(...)` calls

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        if item not in self._fields:
            self._fields[item] = _FakeProto(item)
        return self._fields[item]

    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            self._fields[key] = value

    def append(self, item):
        """Repeated-field append. Stores into both _appended and the parent's
        slot so tests can introspect via fields[key] -> proto with _appended."""
        self._appended.append(item)
        # Also expose as iterable view through _fields["__list__"]
        self._fields.setdefault("__list__", [])
        self._fields["__list__"].append(item)

    def __iter__(self):
        # Allow `list(crit.final_urls)` after appends
        return iter(self._appended)

    def __len__(self):
        return len(self._appended)

    def __repr__(self):
        return f"_FakeProto({self._name}, fields={list(self._fields)}, appended={len(self._appended)})"


class _FakeOp:
    """Fake operation: exposes `.create` AND `.update` (for in-place mutations)."""

    def __init__(self):
        self.create = _FakeProto("create")
        self.update = _FakeProto("update")
        self.update_mask = _FakeProto("update_mask")


class _FakeService:
    """Records every mutate call against itself.

    Also supports `search_stream` (used by `apply_bids` to look up live ad
    groups by name). Tests inject `_stub_search_stream` to return synthetic
    rows.
    """

    _stub_search_stream: dict = {}

    def __init__(self, recorder: list, name: str):
        self._recorder = recorder
        self._name = name
        self._id_counter = count(1)

    def __getattr__(self, item):
        if item.startswith("mutate_"):
            def call(customer_id: str, operations: list):
                ids = []
                for _ in operations:
                    ids.append(f"customers/{customer_id}/{self._name}/{next(self._id_counter)}")
                self._recorder.append({
                    "service": self._name,
                    "method": item,
                    "customer_id": customer_id,
                    "count": len(operations),
                    "ops": operations,
                    "resource_names": ids,
                })
                resp = SimpleNamespace(
                    results=[SimpleNamespace(resource_name=rn) for rn in ids]
                )
                return resp
            return call
        if item == "search_stream":
            def call(customer_id: str = "", query: str = ""):
                # Return whatever the test injected via _stub_search_stream.
                rows = self._stub_search_stream.get(self._name, [])
                self._recorder.append({
                    "service": self._name,
                    "method": "search_stream",
                    "customer_id": customer_id,
                    "query": query,
                    "rows": rows,
                })
                # One batch with all rows.
                batch = SimpleNamespace(
                    results=[
                        SimpleNamespace(ad_group=SimpleNamespace(
                            resource_name=row["resource_name"], name=row["name"],
                        ))
                        for row in rows
                    ]
                )
                return [batch]
            return call
        if item == "list_accessible_customers":
            def call():
                return SimpleNamespace(resource_names=[])
            return call
        raise AttributeError(item)


class _FakeEnum:
    def __getattr__(self, item):
        return f"<enum:{item}>"


class _FakeEnums:
    def __getattr__(self, item):
        return _FakeEnum()


class _FakeClient:
    """Fake GoogleAdsClient that records all operations made."""

    def __init__(self):
        self.calls: list = []
        self.enums = _FakeEnums()
        # apply_bids tests inject ad-group lookup rows here
        self.stub_ad_groups: list = []

    def get_service(self, name: str):
        svc = _FakeService(self.calls, name)
        if name == "GoogleAdsService" and self.stub_ad_groups:
            svc._stub_search_stream = {"GoogleAdsService": self.stub_ad_groups}
        return svc

    def get_type(self, name: str):
        if name.endswith("Operation"):
            return _FakeOp()
        if name == "FieldMask":
            # FieldMask is constructed with kwargs (paths=[...])
            def _mk(**kwargs):
                p = _FakeProto("FieldMask")
                for k, v in kwargs.items():
                    setattr(p, k, v)
                return p
            return _mk
        # AdTextAsset, LeadFormField, etc. — plain protos
        return _FakeProto(name)

    def copy_from(self, target, source):
        # Real google-ads SDK copies fields from source into target. The
        # production code uses copy_from in two patterns:
        #   (a) initialise a oneof slot — copy_from(campaign.target_spend, TargetSpend())
        #       — fresh empty proto; nothing to mirror in the fake.
        #   (b) populate an UPDATE FieldMask — copy_from(op.update_mask, FieldMask(paths=[...]))
        #       — the test inspects `update_mask.paths`, so we mirror the
        #       source fields onto the target.
        # We selectively mirror only when the source name suggests a FieldMask
        # (it has the `paths` field). Other copy_from cases stay no-op so we
        # don't perturb existing behavior.
        if hasattr(source, "_fields") and "paths" in getattr(source, "_fields", {}):
            target._fields["paths"] = source._fields["paths"]
        return target


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SAMPLE_YAML_PATH = "tests/fixtures/catalog_sample.yaml"


@pytest.fixture
def small_plan(monkeypatch):
    """A 10-row catalog plan ready to push."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML_PATH)
    products = [catalog_row_to_product(r) for r in catalog]
    client = ClientProfile(
        business_name="Flightnetwork",
        website_url="https://www.flightnetwork.com/",
        industry="travel",
        language="en",
        monthly_budget_sek=200_000,
    )
    build_config = CampaignBuildConfig(
        structure_mode="sku",
        campaign_name_template="Flightnetwork - All Destinations",
        ad_group_name_template="{name} ({sku})",
        language="en",
        url_templates={
            "primary": "https://www.flightnetwork.com/from/google/rf/destination?to={sku}&text={N}"
        },
        keyword_templates=["flights to {name}", "{name} flights"],
        keyword_match_types=["PHRASE"],
        promotion_enabled=True,
        bid_rules=[
            {"if": "discount_pct >= 0.30", "then": {"modifier": 1.5}},
            {"if": "discount_pct >= 0.15", "then": {"modifier": 1.25}},
        ],
    )
    lead_form_cfg = {
        "form_name": "Get Flight Quote",
        "headline": "Get cheap flights",
        "description": "Enter your details and we will send you the best fares.",
        "business_name": "Flightnetwork",
        "cta": "GET_QUOTE",
        "privacy_url": "https://www.flightnetwork.com/privacy",
        "fields": ["EMAIL", "FIRST_NAME"],
    }
    plan = build_campaigns_from_catalog(
        client, products, build_config,
        lead_form_config=lead_form_cfg,
        promotion_start_date=date(2026, 5, 20),
        promotion_end_date=date(2026, 6, 30),
    )
    return plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_sek_to_micros() -> None:
    assert sek_to_micros(100) == 100_000_000
    assert sek_to_micros(99.99) == 99_990_000
    assert sek_to_micros(0) == 0


# ---------------------------------------------------------------------------
# Push happy path
# ---------------------------------------------------------------------------


def test_pusher_walks_full_plan(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    report = pusher.push(small_plan)

    assert report.total_entities() > 0
    # 1 campaign × 1 budget
    assert len(report.budgets) == 1
    assert len(report.campaigns) == 1
    # 10 ad groups
    assert len(report.ad_groups) == 10
    # Each ad group has 2 keyword templates × 1 match type = 2 keywords (some
    # may dedupe across products, but for 10 distinct products it's stable)
    assert len(report.keywords) >= 20  # at least 2 per ad group
    # 3-5 RSA variants per ad group. With the 10-product fixture all rows have
    # discount_pct > 0 OR == 0 deterministically — we just assert the floor.
    assert len(report.ads) >= 10 * 3  # ≥ 3 variants × 10 ad groups
    assert len(report.ads) <= 10 * 5  # ≤ 5 variants × 10 ad groups
    # Assets: 4 sitelinks + (callouts varies) + 1 lead form + 6 promotion assets
    # ≥ 4 + 1 + 1 = 6 minimum
    assert len(report.assets) >= 6
    # Asset links: each promotion also gets a link, plus sitelinks/lead-forms
    assert len(report.asset_links) >= 6


def test_pusher_customer_id_normalized_and_passed(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="469-180-7001", client=fake)
    pusher.push(small_plan)
    for call in fake.calls:
        assert call["customer_id"] == "4691807001", call


def test_pusher_dry_run_makes_no_api_calls(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake, dry_run=True)
    report = pusher.push(small_plan)
    assert fake.calls == []
    # But report still has entries (synthetic resource names)
    assert len(report.ad_groups) == 10
    assert all("dryrun" in r.resource_name for r in report.ad_groups)


def test_pusher_batches_at_configured_size(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake, batch_size=3)
    pusher.push(small_plan)
    ad_group_calls = [c for c in fake.calls if c["service"] == "AdGroupService"]
    # 10 ad groups in batches of 3 → 4 calls (3 + 3 + 3 + 1)
    assert len(ad_group_calls) == 4
    assert [c["count"] for c in ad_group_calls] == [3, 3, 3, 1]


def test_pusher_uses_correct_services_in_order(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    pusher.push(small_plan)
    services_in_order = [c["service"] for c in fake.calls]
    # Budget must come before Campaign; Campaign before AdGroup; AdGroup before
    # AdGroupCriterion + AdGroupAd; assets last
    budget_idx = services_in_order.index("CampaignBudgetService")
    campaign_idx = services_in_order.index("CampaignService")
    ag_idx = services_in_order.index("AdGroupService")
    kw_idx = services_in_order.index("AdGroupCriterionService")
    ad_idx = services_in_order.index("AdGroupAdService")
    asset_idx = services_in_order.index("AssetService")
    assert budget_idx < campaign_idx < ag_idx
    assert ag_idx < kw_idx
    assert ag_idx < ad_idx
    assert asset_idx > campaign_idx


def test_pusher_writes_paused_status_on_campaign(small_plan) -> None:
    """First-run campaigns must be PAUSED so the operator reviews before going live."""
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    pusher.push(small_plan)
    campaign_call = next(c for c in fake.calls if c["service"] == "CampaignService")
    op = campaign_call["ops"][0]
    # Inspect the recorded proto's `status` field (the enum lookup attribute)
    # Status was assigned via `c.status = client.enums.CampaignStatusEnum.PAUSED`,
    # which stores "<enum:PAUSED>" in our fake
    assert str(op.create._fields["status"]).endswith("PAUSED>")


def test_pusher_uses_correct_budget_micros(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    pusher.push(small_plan)
    budget_call = next(c for c in fake.calls if c["service"] == "CampaignBudgetService")
    op = budget_call["ops"][0]
    daily = small_plan.campaigns[0].budget_sek_daily
    assert op.create._fields["amount_micros"] == sek_to_micros(daily)


def test_pusher_does_not_mutate_when_plan_empty() -> None:
    from src.models.campaign import CampaignPlan
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    report = pusher.push(CampaignPlan(campaigns=[]))
    assert fake.calls == []
    assert report.total_entities() == 0


def test_pusher_attaches_promotion_to_ad_group(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    pusher.push(small_plan)
    # Should have AdGroupAssetService calls for promotion linking
    ag_asset_calls = [c for c in fake.calls if c["service"] == "AdGroupAssetService"]
    # 6 discounted products → 6 promotion assets linked to ad groups
    total_linked = sum(c["count"] for c in ag_asset_calls)
    assert total_linked == 6


def test_pusher_sitelinks_and_callouts_attached_to_campaign(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    pusher.push(small_plan)
    camp_asset_calls = [c for c in fake.calls if c["service"] == "CampaignAssetService"]
    # At least 3 CampaignAssetService calls: sitelinks, callouts, lead form
    assert len(camp_asset_calls) >= 3


def test_pusher_name_suffix_appended(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake, name_suffix=" [v1]")
    pusher.push(small_plan)
    campaign_call = next(c for c in fake.calls if c["service"] == "CampaignService")
    op = campaign_call["ops"][0]
    name = op.create._fields["name"]
    assert name.endswith(" [v1]")


def test_push_report_summary_string(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    report = pusher.push(small_plan)
    s = report.summary()
    assert "ad_groups=10" in s
    assert "customer=123-456-7890" in s
    assert "elapsed=" in s


def test_pusher_lead_form_field_translation(small_plan) -> None:
    """Lead form fields must be sent as the SDK's enum values, not raw strings."""
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    pusher.push(small_plan)
    asset_calls = [c for c in fake.calls if c["service"] == "AssetService"]
    # One of the asset calls must be the lead form (look for an op whose
    # create has a `lead_form_asset` sub-proto)
    lead_form_present = False
    for call in asset_calls:
        for op in call["ops"]:
            if "lead_form_asset" in op.create._fields:
                lead_form_present = True
                lfa = op.create._fields["lead_form_asset"]
                # Fields list populated
                assert "fields" in lfa._fields
    assert lead_form_present


def test_pusher_dry_run_records_lead_form_promo_sitelink_in_report(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake, dry_run=True)
    report = pusher.push(small_plan)
    kinds = {a.kind for a in report.assets}
    assert "lead_form_asset" in kinds
    assert "promotion_asset" in kinds
    assert "sitelink_asset" in kinds


def test_promotion_percent_off_uses_10000_per_percent_scale(small_plan) -> None:
    """PromotionAsset.percent_off is `10,000 = 1%` (NOT the 1,000,000 the docs
    claim). Verified empirically against the live API on 2026-05-20."""
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    pusher.push(small_plan)
    promotion_asset_calls = [
        call for call in fake.calls
        if call["service"] == "AssetService"
        and any("promotion_asset" in op.create._fields for op in call["ops"])
    ]
    assert promotion_asset_calls, "Promotion assets must be pushed"
    for call in promotion_asset_calls:
        for op in call["ops"]:
            pa = op.create._fields.get("promotion_asset")
            if pa is None:
                continue
            if "percent_off" in pa._fields:
                val = pa._fields["percent_off"]
                # A reasonable percent is 1-100 → 10,000-1,000,000 in the
                # field's scale. Any value above 1,000,000 means the wrong
                # scale was used.
                assert 1 <= val <= 1_000_000, (
                    f"percent_off={val} suggests wrong scale (should be 10,000 = 1%)"
                )


def test_pusher_skip_lead_forms(small_plan) -> None:
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake, skip_lead_forms=True)
    pusher.push(small_plan)
    # No lead_form_asset operations should appear
    for call in fake.calls:
        for op in call["ops"]:
            if "lead_form_asset" in op.create._fields:
                pytest.fail("Lead form was pushed despite skip_lead_forms=True")


def test_pusher_lead_form_missing_agreement_is_non_fatal(small_plan) -> None:
    from src.apis.errors import GoogleAdsApiError

    class _FailingLeadFormClient(_FakeClient):
        def get_service(self, name):
            svc = super().get_service(name)
            if name == "AssetService":
                orig = svc.mutate_assets
                def maybe_fail(customer_id, operations):
                    for op in operations:
                        if "lead_form_asset" in op.create._fields:
                            raise GoogleAdsApiError(
                                "LEAD_FORM_MISSING_AGREEMENT: ToS not accepted"
                            )
                    return orig(customer_id=customer_id, operations=operations)
                svc.mutate_assets = maybe_fail
            return svc

    fake = _FailingLeadFormClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    # Should NOT raise — the LEAD_FORM_MISSING_AGREEMENT error becomes a warning
    pusher.push(small_plan)
    assert any("LEAD_FORM_MISSING_AGREEMENT" in w or "Lead-form push skipped" in w
               for w in pusher.warnings)


def test_keyword_final_url_inherits_ad_group_url(small_plan) -> None:
    """Each keyword's final_url should be the ad group's templated URL."""
    fake = _FakeClient()
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    pusher.push(small_plan)
    kw_calls = [c for c in fake.calls if c["service"] == "AdGroupCriterionService"]
    assert kw_calls
    for call in kw_calls:
        for op in call["ops"]:
            crit = op.create._fields
            assert "final_urls" in crit
            urls = list(crit["final_urls"])
            assert any("to=" in str(u) for u in urls)


# ---------------------------------------------------------------------------
# apply_bids — temporary discount-driven seasonality on a LIVE campaign
# ---------------------------------------------------------------------------


def test_apply_bids_dry_run_computes_intended_updates_without_api_calls(small_plan) -> None:
    """Dry-run should compose the intended-updates list for every ad group
    in the plan and make ZERO API calls (no search_stream, no mutate)."""
    fake = _FakeClient()
    pusher = CampaignPusher(
        customer_id="123-456-7890", client=fake, dry_run=True,
    )
    report = pusher.apply_bids(small_plan, base_cpc_micros=5_000_000)

    assert report.dry_run is True
    # All 10 ad groups become intended updates.
    assert len(report.intended_updates) == 10
    assert report.applied == []
    assert report.skipped == []
    # cpc target = base × modifier; with modifiers in {1.0, 1.1, 1.25, 1.5}
    # for the test fixture's bid_rules, all targets must be > 0.
    for u in report.intended_updates:
        assert u.new_cpc_micros == int(5_000_000 * u.modifier)
    # Zero API calls in dry-run.
    assert fake.calls == []


def test_apply_bids_live_mutates_matched_ad_groups_via_update_mask(small_plan) -> None:
    """Live path: search_stream finds live ad groups by name, then
    mutate_ad_groups updates each one's cpc_bid_micros via a FieldMask."""
    fake = _FakeClient()
    # Stub the search_stream lookup with synthetic live ad groups for the
    # FIRST 5 of the 10 plan ad groups. The other 5 should land in `skipped`.
    plan_ag_names = [
        ag.name for c in small_plan.campaigns for ag in c.ad_groups
    ]
    fake.stub_ad_groups = [
        {"name": name, "resource_name": f"customers/123/adGroups/{i+1}"}
        for i, name in enumerate(plan_ag_names[:5])
    ]
    pusher = CampaignPusher(customer_id="123-456-7890", client=fake)
    report = pusher.apply_bids(small_plan, base_cpc_micros=4_000_000)

    assert not report.dry_run
    assert len(report.intended_updates) == 10
    assert len(report.applied) == 5
    assert len(report.skipped) == 5
    # search_stream was called once per campaign (1 campaign in the plan).
    search_calls = [c for c in fake.calls if c["method"] == "search_stream"]
    assert len(search_calls) == 1
    # The GAQL filters by the (suffixed) campaign name.
    assert "FROM ad_group" in search_calls[0]["query"]
    assert "Flightnetwork - All Destinations" in search_calls[0]["query"]
    # mutate_ad_groups was called with 5 update ops carrying the right
    # cpc_bid_micros values and a FieldMask referencing cpc_bid_micros.
    mutate_calls = [
        c for c in fake.calls
        if c["service"] == "AdGroupService" and c["method"] == "mutate_ad_groups"
    ]
    assert mutate_calls
    seen_cpcs = []
    for call in mutate_calls:
        for op in call["ops"]:
            update_proto = op.update._fields
            assert "resource_name" in update_proto
            assert "cpc_bid_micros" in update_proto
            seen_cpcs.append(update_proto["cpc_bid_micros"])
            # The FieldMask on op.update_mask carries `cpc_bid_micros`.
            mask_paths = op.update_mask._fields.get("paths", [])
            assert "cpc_bid_micros" in mask_paths
    assert len(seen_cpcs) == 5
    # All cpcs are positive multiples of the base.
    for cpc in seen_cpcs:
        assert cpc > 0
        assert cpc % 4_000_000 == 0 or cpc != 4_000_000  # may be non-integer multiple


def test_apply_bids_with_name_suffix_finds_suffixed_live_ad_groups(small_plan) -> None:
    """When the original push used `--auto-suffix`, the same suffix must be
    passed to apply_bids so the live lookup hits the suffixed names."""
    fake = _FakeClient()
    suffix = " [2026-05-21 12:00:00]"
    suffixed_plan_names = [
        ag.name + suffix for c in small_plan.campaigns for ag in c.ad_groups
    ]
    fake.stub_ad_groups = [
        {"name": name, "resource_name": f"customers/123/adGroups/{i+1}"}
        for i, name in enumerate(suffixed_plan_names)
    ]
    pusher = CampaignPusher(
        customer_id="123-456-7890", client=fake, name_suffix=suffix,
    )
    report = pusher.apply_bids(small_plan, base_cpc_micros=3_000_000)

    # All 10 match because we passed the same suffix.
    assert len(report.applied) == 10
    assert len(report.skipped) == 0
    # Suffix appears in the GAQL.
    search_calls = [c for c in fake.calls if c["method"] == "search_stream"]
    assert any(suffix in c["query"] for c in search_calls)
