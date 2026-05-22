"""Bulk-REMOVE the partial campaigns sitting on the test account.

The 2026-05-21 push session left 17 PAUSED campaigns on `469-180-7001`
from three failure modes (bid-strategy, partial_failure kwarg shape,
RESOURCE_EXHAUSTED). All PAUSED, zero serving impact, but they clutter
the operator's review surface and inflate the entity count when running
GAQL diagnostics.

Discovery query: name LIKE 'Flightnetwork - All Destinations%' AND
status = PAUSED. Removed in a single mutate batch.

Usage:
    python -m scripts.cleanup_test_account            # interactive confirm
    python -m scripts.cleanup_test_account --yes      # skip confirm
    python -m scripts.cleanup_test_account --dry-run  # report only

Idempotent — running twice removes 0 campaigns the second time.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable


CUSTOMER_ID = "4691807001"
NAME_PATTERN = "Flightnetwork - All Destinations%"

# Known IDs from the 2026-05-21 session — used as a fallback if the
# discovery query returns 0 (unlikely but cheap insurance).
FALLBACK_IDS = [
    "23860336215", "23860343253", "23860353003", "23860369383",
    "23860395288", "23860402014", "23863840980", "23863890696",
    "23865589133", "23865617183", "23865645974", "23869105844",
    "23870034697", "23870040121", "23870041123", "23870062483",
    "23870065114",
]


def discover_campaigns(client) -> list[tuple[str, str, str]]:
    """Return [(campaign_id, name, status)] for partial test campaigns."""
    ga = client.get_service("GoogleAdsService")
    query = (
        "SELECT campaign.id, campaign.name, campaign.status "
        "FROM campaign "
        f"WHERE campaign.name LIKE '{NAME_PATTERN}' "
        "AND campaign.status = 'PAUSED'"
    )
    rows = []
    for row in ga.search(customer_id=CUSTOMER_ID, query=query):
        rows.append((
            str(row.campaign.id),
            row.campaign.name,
            str(row.campaign.status),
        ))
    return rows


def remove_campaigns(client, campaign_ids: Iterable[str]) -> list[str]:
    """Single batch REMOVE. Returns the resource names of removed campaigns."""
    service = client.get_service("CampaignService")
    ops = []
    for cid in campaign_ids:
        op = client.get_type("CampaignOperation")
        op.remove = f"customers/{CUSTOMER_ID}/campaigns/{cid}"
        ops.append(op)
    if not ops:
        return []
    resp = service.mutate_campaigns(customer_id=CUSTOMER_ID, operations=ops)
    return [r.resource_name for r in resp.results]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be removed; make no API mutations.",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip the confirmation prompt.",
    )
    parser.add_argument(
        "--use-fallback-ids", action="store_true",
        help="Skip discovery; remove the hard-coded fallback IDs directly.",
    )
    args = parser.parse_args()

    from src.auth.google_ads_auth import get_google_ads_client
    client = get_google_ads_client(customer_id=CUSTOMER_ID)

    if args.use_fallback_ids:
        ids = FALLBACK_IDS
        print(f"Using {len(ids)} fallback IDs from the 2026-05-21 handoff.")
    else:
        print(f"Discovering campaigns matching '{NAME_PATTERN}'…")
        found = discover_campaigns(client)
        if not found:
            print("No matching campaigns found. (Already cleaned up?)")
            print("Re-run with --use-fallback-ids to force-remove the known list.")
            return 0
        for cid, name, status in found:
            print(f"  {cid}  {status:10}  {name}")
        ids = [cid for cid, _, _ in found]
        print(f"\nFound {len(ids)} campaigns to remove.")

    if args.dry_run:
        print("\nDry-run: no API mutations.")
        return 0

    if not args.yes:
        ans = input(f"\nRemove these {len(ids)} campaigns from {CUSTOMER_ID}? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted.")
            return 1

    print("\nRemoving…")
    removed = remove_campaigns(client, ids)
    for rn in removed:
        print(f"  removed: {rn}")
    print(f"\nDone. {len(removed)} campaigns removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
