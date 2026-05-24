"""Remove duplicate asset *links* from a live campaign.

Why this exists: before the 2026-05-24 resume-asset-skip fix, the resume path
re-created every sitelink / callout / promotion on each run because asset-type
detection matched the enum NAME against `str(field_type)` (the numeric value).
A double resume therefore left two identical links per asset. This script
restores exactly one link per unique campaign asset (by content) and one
promotion per ad group (by ad-group id).

It is content/structure-based, NOT creation-time-based, so it is safe to run
repeatedly: it always collapses each duplicate group down to a single link and
leaves the underlying Asset entities untouched (orphaned assets don't serve and
can't always be deleted via the API — harmless).

Usage:
    python -m scripts.dedupe_campaign_assets --customer 4691807001 \
        --campaign 23867614686 [--dry-run] [--yes]
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from src.auth.google_ads_auth import get_google_ads_client


def _campaign_asset_dupes(ga, customer_id: str, campaign_id: str) -> list[str]:
    """Return campaign_asset resource names to REMOVE (all but one per unique
    (field_type, content) group). Covers sitelinks + callouts."""
    q = (
        "SELECT campaign.id, campaign_asset.resource_name, campaign_asset.field_type, "
        "asset.sitelink_asset.link_text, asset.callout_asset.callout_text "
        f"FROM campaign_asset WHERE campaign.id = {campaign_id}"
    )
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in ga.search(customer_id=customer_id, query=q):
        ft = r.campaign_asset.field_type.name
        content = r.asset.sitelink_asset.link_text or r.asset.callout_asset.callout_text
        groups[(ft, content)].append(r.campaign_asset.resource_name)
    remove: list[str] = []
    for links in groups.values():
        remove.extend(sorted(links)[1:])  # keep one (deterministic), drop the rest
    return remove


def _ad_group_promo_dupes(ga, customer_id: str, campaign_id: str) -> list[str]:
    """Return ad_group_asset resource names to REMOVE (all but one PROMOTION per
    ad group)."""
    q = (
        "SELECT campaign.id, ad_group.id, ad_group_asset.resource_name "
        f"FROM ad_group_asset WHERE campaign.id = {campaign_id} "
        "AND ad_group_asset.field_type = 'PROMOTION'"
    )
    groups: dict[str, list[str]] = defaultdict(list)
    for r in ga.search(customer_id=customer_id, query=q):
        groups[r.ad_group.id].append(r.ad_group_asset.resource_name)
    remove: list[str] = []
    for links in groups.values():
        remove.extend(sorted(links)[1:])
    return remove


def _remove_batched(client, service_name: str, op_type: str, customer_id: str,
                    resource_names: list[str], *, batch: int = 1000) -> int:
    """Remove links in batches, tallying the TRUE count from `response.results`.

    Important operational lesson (2026-05-24): never trust GAQL `search` to
    confirm an asset-link removal — its reporting layer lags the mutate layer by
    many minutes, so a *successful* removal still shows the link as present.
    Re-running dedup off that stale view then re-targets already-removed links
    and fails with RESOURCE_NOT_FOUND. The mutate layer is strongly consistent;
    use a `validate_only` remove (succeeds=exists, RESOURCE_NOT_FOUND=gone) for
    authoritative existence checks. Counting `response.results` here means this
    script reports what Google actually removed, not what we asked it to."""
    if not resource_names:
        return 0
    svc = client.get_service(service_name)
    mutate = getattr(svc, f"mutate_{op_type}s")  # mutate_campaign_assets / mutate_ad_group_assets
    op_proto = {
        "campaign_asset": "CampaignAssetOperation",
        "ad_group_asset": "AdGroupAssetOperation",
    }[op_type]
    removed = 0
    for i in range(0, len(resource_names), batch):
        chunk = resource_names[i:i + batch]
        ops = []
        for rn in chunk:
            op = client.get_type(op_proto)
            op.remove = rn
            ops.append(op)
        resp = mutate(request={"customer_id": customer_id, "operations": ops})
        removed += len(resp.results)
    return removed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--customer", required=True, help="customer id, digits only")
    ap.add_argument("--campaign", required=True, help="campaign id")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    client = get_google_ads_client(customer_id=args.customer)
    ga = client.get_service("GoogleAdsService")

    camp_remove = _campaign_asset_dupes(ga, args.customer, args.campaign)
    promo_remove = _ad_group_promo_dupes(ga, args.customer, args.campaign)

    print(f"Duplicate campaign-asset links to remove: {len(camp_remove)}")
    print(f"Duplicate ad-group promotion links to remove: {len(promo_remove)}")

    if args.dry_run:
        print("Dry run — no mutations.")
        return
    if not args.yes:
        resp = input("Proceed with removal? [y/N] ").strip().lower()
        if resp != "y":
            print("Aborted.")
            return

    n1 = _remove_batched(client, "CampaignAssetService", "campaign_asset",
                         args.customer, camp_remove)
    n2 = _remove_batched(client, "AdGroupAssetService", "ad_group_asset",
                         args.customer, promo_remove)
    print(f"Removed {n1} campaign-asset links + {n2} ad-group promotion links.")


if __name__ == "__main__":
    main()
