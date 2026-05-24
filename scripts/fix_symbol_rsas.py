"""Repair live RSAs that still carry Google-prohibited decorative symbols (★).

Background. The v0.3.7 fix replaced '4.5★' with '4.5/5' in the pattern pack and
recovered the 991 RSAs Google had REJECTED at create time. But ads created in an
earlier push wave — before that fix — and already live were skipped by the
resume push (it skips existing (ad_group, text=N) slots), so a handful of
star-bearing social_proof variants survived in the account. Google's review
lags on a PAUSED campaign, so only some are flagged yet; the rest will go
LIMITED once reviewed. `scripts/audit_live_campaign.py` finds them via a
review-independent content scan.

This script fixes them faithfully: for each affected RSA it creates a corrected
duplicate (status PAUSED, '4.5★'→'4.5/5', everything else — pins, paths, final
URL — byte-identical) and then removes the original. The replacement text is
identical to what every other social_proof ad now ships (pattern pack v4.2).

Default is DRY-RUN (prints old→new for every ad, makes no changes). Pass --yes
to actually mutate.

Usage:
    python -m scripts.fix_symbol_rsas etraveli --campaign 23867614686            # preview
    python -m scripts.fix_symbol_rsas etraveli --campaign 23867614686 --yes      # apply
"""

from __future__ import annotations

import argparse
import sys
import unicodedata

from src.accounts.manager import get_account
from src.auth.google_ads_auth import get_google_ads_client

HEADLINE_MAX = 30
DESCRIPTION_MAX = 90


def _banned_glyphs(text: str) -> set[str]:
    """Decorative symbols banned by Google's RSA SYMBOLS policy (Unicode So/Sk)."""
    return {ch for ch in text if unicodedata.category(ch) in ("So", "Sk")}


def fix_text(text: str) -> str:
    """Apply the shipped v0.3.7 fix: '4.5★' → '4.5/5'; strip any stray glyph.

    Mirrors data/en/ad_copy_patterns.json (the rating token became '4.5/5').
    A defensive strip + whitespace collapse handles any other stray symbol so
    the output is guaranteed glyph-free.
    """
    fixed = text.replace("4.5★", "4.5/5")
    if _banned_glyphs(fixed):
        fixed = "".join(ch for ch in fixed if unicodedata.category(ch) not in ("So", "Sk"))
        fixed = " ".join(fixed.split())  # collapse any double space left behind
    return fixed


def _collect_targets(client, customer_id: str, campaign_id: str) -> list[dict]:
    """Return every RSA in the campaign whose copy contains a banned glyph."""
    ga = client.get_service("GoogleAdsService")
    query = f"""
        SELECT ad_group.id, ad_group.name,
               ad_group_ad.resource_name, ad_group_ad.ad.id,
               ad_group_ad.ad.responsive_search_ad.headlines,
               ad_group_ad.ad.responsive_search_ad.descriptions,
               ad_group_ad.ad.responsive_search_ad.path1,
               ad_group_ad.ad.responsive_search_ad.path2,
               ad_group_ad.ad.final_urls
        FROM ad_group_ad
        WHERE campaign.id = {campaign_id}
          AND ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'
    """
    targets: list[dict] = []
    for batch in ga.search_stream(customer_id=customer_id, query=query):
        for row in batch.results:
            aga = row.ad_group_ad
            rsa = aga.ad.responsive_search_ad
            heads = [(h.text, int(h.pinned_field)) for h in rsa.headlines]
            descs = [(d.text, int(d.pinned_field)) for d in rsa.descriptions]
            has_symbol = any(_banned_glyphs(t) for t, _ in heads + descs)
            if not has_symbol:
                continue
            urls = list(aga.ad.final_urls)
            text_n = urls[0].split("text=")[-1] if urls and "text=" in urls[0] else "?"
            targets.append({
                "ag_id": str(row.ad_group.id),
                "ag_name": row.ad_group.name,
                "ag_rn": f"customers/{customer_id}/adGroups/{row.ad_group.id}",
                "old_ad_rn": aga.resource_name,
                "old_ad_id": str(aga.ad.id),
                "text_n": text_n,
                "final_urls": urls,
                "path1": rsa.path1,
                "path2": rsa.path2,
                "headlines": heads,
                "descriptions": descs,
            })
    return targets


def _build_corrected_op(client, t: dict) -> tuple[object, list[str]]:
    """Build an AdGroupAdOperation.create for the corrected RSA.

    Returns (operation, warnings). Warnings flag any over-limit text (the ad is
    still built; the caller decides whether to push).
    """
    warnings: list[str] = []
    op = client.get_type("AdGroupAdOperation")
    ag_ad = op.create
    ag_ad.ad_group = t["ag_rn"]
    ag_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
    ad = ag_ad.ad
    for u in t["final_urls"]:
        ad.final_urls.append(u)
    rsa = ad.responsive_search_ad
    if t["path1"]:
        rsa.path1 = t["path1"]
    if t["path2"]:
        rsa.path2 = t["path2"]
    for text, pinned in t["headlines"]:
        new_text = fix_text(text)
        if len(new_text) > HEADLINE_MAX:
            warnings.append(f"headline over {HEADLINE_MAX}: {new_text!r} ({len(new_text)})")
        asset = client.get_type("AdTextAsset")
        asset.text = new_text
        asset.pinned_field = pinned  # 0 (UNSPECIFIED) = unpinned; copies live pin
        rsa.headlines.append(asset)
    for text, pinned in t["descriptions"]:
        new_text = fix_text(text)
        if len(new_text) > DESCRIPTION_MAX:
            warnings.append(f"description over {DESCRIPTION_MAX}: {new_text!r} ({len(new_text)})")
        asset = client.get_type("AdTextAsset")
        asset.text = new_text
        asset.pinned_field = pinned
        rsa.descriptions.append(asset)
    return op, warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", nargs="?", default="etraveli")
    ap.add_argument("--campaign", default="23867614686")
    ap.add_argument("--dry-run", action="store_true", help="Preview only (forces no mutation)")
    ap.add_argument("--yes", action="store_true", help="Actually create+remove ads")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    live = args.yes and not args.dry_run
    customer_id = get_account(args.slug).customer_id.replace("-", "")
    client = get_google_ads_client(customer_id=customer_id)

    print(f"Scanning campaign {args.campaign} on {args.slug} for banned-symbol RSAs …\n")
    targets = _collect_targets(client, customer_id, args.campaign)
    if not targets:
        print("✅ No RSAs contain banned symbols. Nothing to fix.")
        return

    print(f"Found {len(targets)} RSA(s) to repair "
          f"({'LIVE — will mutate' if live else 'DRY-RUN — no changes'}):\n")

    all_warnings = 0
    svc = client.get_service("AdGroupAdService") if live else None
    fixed = 0
    for i, t in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {t['ag_name']}  (ad {t['old_ad_id']}, text={t['text_n']})")
        for text, _ in t["headlines"] + t["descriptions"]:
            if _banned_glyphs(text):
                print(f"     OLD: {text!r}")
                print(f"     NEW: {fix_text(text)!r}")
        op, warnings = _build_corrected_op(client, t)
        for w in warnings:
            all_warnings += 1
            print(f"     ⚠️  {w}")

        if not live:
            continue

        # 1) create corrected ad, 2) remove the starred original
        create_resp = svc.mutate_ad_group_ads(
            request={"customer_id": customer_id, "operations": [op]}
        )
        new_rn = create_resp.results[0].resource_name
        rm = client.get_type("AdGroupAdOperation")
        rm.remove = t["old_ad_rn"]
        svc.mutate_ad_group_ads(
            request={"customer_id": customer_id, "operations": [rm]}
        )
        print(f"     ✓ created {new_rn.split('/')[-1]} (PAUSED), removed {t['old_ad_id']}")
        fixed += 1

    print()
    if live:
        print(f"Done. Repaired {fixed}/{len(targets)} RSAs. "
              f"Re-run: python -m scripts.audit_live_campaign {args.slug}")
    else:
        print(f"DRY-RUN complete. {len(targets)} RSAs would be repaired"
              + (f" ({all_warnings} length warning(s) — review before applying)." if all_warnings
                 else ". No length issues.")
              + "\nApply with: python -m scripts.fix_symbol_rsas "
              f"{args.slug} --campaign {args.campaign} --yes")


if __name__ == "__main__":
    main()
