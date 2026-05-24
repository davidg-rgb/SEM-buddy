"""Replace a live campaign's sitelinks + callouts with the case.yaml ones, and
optionally drop a machine name-suffix from the campaign.

Why this exists: the initial push attached the builder's GENERIC per-language
default extensions (`About Us` / `Our Services` / `Free Quote` / `Trusted Local
Company` …) because case.yaml had no extension override at the time. Those are
service-business boilerplate — wrong for a travel client and, worse, the
default sitelink URLs (`/services`, `/quote`) 404. case.yaml now carries
travel-specific sitelinks/callouts with REAL flightnetwork.com URLs; this
script swaps them onto the live campaign without re-pushing the whole thing.

Order of operations (so the campaign is never left without extensions):
  1. create the new sitelink/callout assets + links  (reuses CampaignPusher)
  2. remove the old ENABLED sitelink/callout links
  3. rename the campaign to `structure.campaign_name_template` (drop suffix),
     with a collision check.

Default is DRY-RUN; pass --yes to mutate.

Usage:
    python -m scripts.replace_campaign_extensions etraveli --campaign 23867614686
    python -m scripts.replace_campaign_extensions etraveli --campaign 23867614686 --yes
    python -m scripts.replace_campaign_extensions etraveli --campaign 23867614686 --yes --no-rename
"""

from __future__ import annotations

import argparse
import sys

from google.protobuf import field_mask_pb2

from src.accounts.manager import get_account
from src.apis.campaign_pusher import CampaignPusher, PushReport
from src.auth.google_ads_auth import get_google_ads_client
from src.cases.config import load_case_config
from src.cases.runner import _resolve_case_path
from src.models.campaign import Callout, Sitelink


def _existing_ext_links(client, customer_id: str, campaign_id: str) -> list[dict]:
    """ENABLED campaign-level SITELINK/CALLOUT links (the ones to replace)."""
    ga = client.get_service("GoogleAdsService")
    q = f"""
        SELECT campaign.id, campaign_asset.resource_name, campaign_asset.field_type,
               campaign_asset.status, asset.sitelink_asset.link_text,
               asset.callout_asset.callout_text
        FROM campaign_asset
        WHERE campaign.id = {campaign_id}
          AND campaign_asset.status = 'ENABLED'
          AND campaign_asset.field_type IN ('SITELINK', 'CALLOUT')
    """
    out = []
    for r in ga.search(customer_id=customer_id, query=q):
        ca = r.campaign_asset
        ft = ca.field_type.name
        label = (r.asset.sitelink_asset.link_text if ft == "SITELINK"
                 else r.asset.callout_asset.callout_text)
        out.append({"rn": ca.resource_name, "field_type": ft, "label": label})
    return out


def _campaign_name(client, customer_id: str, campaign_id: str) -> str:
    ga = client.get_service("GoogleAdsService")
    rows = list(ga.search(
        customer_id=customer_id,
        query=f"SELECT campaign.id, campaign.name FROM campaign WHERE campaign.id = {campaign_id}",
    ))
    return rows[0].campaign.name if rows else ""


def _name_collision(client, customer_id: str, new_name: str, this_id: str) -> bool:
    ga = client.get_service("GoogleAdsService")
    esc = new_name.replace("'", "\\'")
    q = (f"SELECT campaign.id, campaign.name FROM campaign "
         f"WHERE campaign.name = '{esc}' AND campaign.status != 'REMOVED'")
    for r in ga.search(customer_id=customer_id, query=q):
        if str(r.campaign.id) != str(this_id):
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", nargs="?", default="etraveli")
    ap.add_argument("--campaign", default="23867614686")
    ap.add_argument("--yes", action="store_true", help="Actually mutate")
    ap.add_argument("--dry-run", action="store_true", help="Force preview (default)")
    ap.add_argument("--no-rename", action="store_true", help="Skip the campaign rename")
    ap.add_argument("--rename-only", action="store_true",
                    help="Only rename the campaign; don't touch extensions (idempotent re-run)")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    live = args.yes and not args.dry_run
    customer_id = get_account(args.slug).customer_id.replace("-", "")
    client = get_google_ads_client(customer_id=customer_id)
    campaign_rn = f"customers/{customer_id}/campaigns/{args.campaign}"

    case = load_case_config(_resolve_case_path(args.slug))
    new_sitelinks = [
        Sitelink(text=s.text, desc1=s.desc1, desc2=s.desc2, final_url=str(s.final_url))
        for s in case.extensions.sitelinks
    ]
    new_callouts = [Callout(text=c) for c in case.extensions.callouts]
    if not new_sitelinks and not new_callouts:
        print("case.yaml has no sitelinks/callouts to push. Nothing to do.")
        return

    old_links = _existing_ext_links(client, customer_id, args.campaign)
    live_name = _campaign_name(client, customer_id, args.campaign)
    new_name = case.structure.campaign_name_template

    mode = "LIVE — will mutate" if live else "DRY-RUN — no changes"
    print(f"Replace extensions on campaign {args.campaign} ({args.slug}) [{mode}]\n")

    print(f"NEW sitelinks ({len(new_sitelinks)}):")
    for s in new_sitelinks:
        print(f"  + {s.text!r}  | {s.desc1} / {s.desc2}  | {s.final_url}")
    print(f"NEW callouts ({len(new_callouts)}):")
    for c in new_callouts:
        print(f"  + {c.text!r}")
    print(f"\nOLD ENABLED links to remove ({len(old_links)}):")
    for l in old_links:
        print(f"  - [{l['field_type']}] {l['label']!r}")
    print(f"\nRename: {live_name!r}")
    if args.no_rename:
        print("  → (skipped, --no-rename)")
    elif live_name == new_name:
        print("  → already clean, no rename needed")
    else:
        print(f"  → {new_name!r}")

    if not live:
        print("\nDRY-RUN complete. Apply with --yes.")
        return

    if not args.rename_only:
        # --- 1. create new assets + links (reuse the pusher's proven methods) ---
        pusher = CampaignPusher(customer_id=customer_id, client=client)
        report = PushReport(customer_id=customer_id)
        pusher._push_sitelinks(client, customer_id, new_sitelinks, campaign_rn, report)
        pusher._push_callouts(client, customer_id, new_callouts, campaign_rn, report)
        print(f"\n✓ Created {len(new_sitelinks)} sitelinks + {len(new_callouts)} callouts and linked them.")

        # --- 2. remove the old generic links ---
        if old_links:
            svc = client.get_service("CampaignAssetService")
            ops = []
            for l in old_links:
                op = client.get_type("CampaignAssetOperation")
                op.remove = l["rn"]
                ops.append(op)
            resp = svc.mutate_campaign_assets(customer_id=customer_id, operations=ops)
            print(f"✓ Removed {len(resp.results)} old generic links.")

    # --- 3. rename the campaign ---
    if not args.no_rename and live_name != new_name:
        if _name_collision(client, customer_id, new_name, args.campaign):
            print(f"⚠️  Skipped rename — another active campaign is already named {new_name!r}.")
        else:
            csvc = client.get_service("CampaignService")
            cop = client.get_type("CampaignOperation")
            cop.update.resource_name = campaign_rn
            cop.update.name = new_name
            # google-ads v23 has no get_type("FieldMask") — use the protobuf type.
            client.copy_from(cop.update_mask, field_mask_pb2.FieldMask(paths=["name"]))
            csvc.mutate_campaigns(customer_id=customer_id, operations=[cop])
            print(f"✓ Renamed campaign → {new_name!r}")

    print("\nDone. Verify: python -m scripts.audit_live_campaign etraveli")


if __name__ == "__main__":
    main()
