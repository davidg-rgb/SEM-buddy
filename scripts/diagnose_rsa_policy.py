"""Name the policy topic(s) behind PROHIBITED RSA rejections.

When a resume/initial push drops RSAs with "policy summary includes policy
topics of type PROHIBITED", the `partial_failure` error does NOT carry the
specific topic (Google only populates `policy_finding_details` in a full,
non-partial mutate). This script reproduces a sample of the *rejected* variants
as `validate_only` creates (one op per call, no partial_failure) so the raised
GoogleAdsException carries `policy_finding_details`, then decodes the topic via
`_extract_policy_topics`. Nothing is created — validate_only applies no changes.

Usage:
    python -m scripts.diagnose_rsa_policy <slug> --campaign <id> \
        --name-suffix " [<orig suffix>]" [--sample 12]
"""

from __future__ import annotations

import argparse
import contextlib
import io
from collections import Counter

from google.ads.googleads.errors import GoogleAdsException

from src.apis.campaign_pusher import _build_resume_state, _extract_policy_topics, _extract_text_n
from src.auth.google_ads_auth import get_google_ads_client
from src.cases.config import load_case_config
from src.cases.runner import _load_client_profile, _maybe_clean_catalog, _resolve_case_path
from src.catalog import load_catalog_from_yaml as _load_catalog
from src.generators.campaign_builder import build_campaigns_from_catalog, catalog_row_to_product


def _build_rsa_op(client, ag_rn: str, ad):
    """Replicates the RSA AdGroupAd create op built by CampaignPusher._push_ads."""
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
    return op


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--name-suffix", default="")
    ap.add_argument("--sample", type=int, default=12, help="max rejected variants to probe")
    args = ap.parse_args()

    cust_digits = None
    from src.accounts.manager import get_account
    cust_digits = get_account(args.slug).customer_id.replace("-", "")

    client = get_google_ads_client(customer_id=cust_digits)

    # Build the plan exactly like push (suffix is applied by the pusher, not the
    # builder — so match live ad-group names by prefix).
    case_path = _resolve_case_path(args.slug)
    case = load_case_config(case_path)
    prof = _load_client_profile(args.slug, case)
    catalog = _load_catalog((case_path.parent / case.catalog).resolve())
    catalog, _ = _maybe_clean_catalog(args.slug, catalog)
    products = [catalog_row_to_product(r) for r in catalog]
    with contextlib.redirect_stdout(io.StringIO()):
        plan = build_campaigns_from_catalog(
            prof, products, case.to_build_config(),
            lead_form_config=(case.extensions.lead_form.model_dump() if case.extensions.lead_form else None),
            promotion_start_date=case.extensions.promotions.start_date,
            promotion_end_date=case.extensions.promotions.end_date,
            promotion_occasion=case.extensions.promotions.occasion,
            money_currency=case.extensions.promotions.money_currency,
        )

    state = _build_resume_state(client, cust_digits, args.campaign)
    # Map plan ad-group name -> live rn (live names carry the suffix).
    live_names = list(state.ag_rn_by_name.items())

    def live_rn_for(plan_name: str) -> str | None:
        target = plan_name + args.name_suffix
        rn = state.ag_rn_by_name.get(target)
        if rn:
            return rn
        # Fallback: prefix match (suffix variations).
        for nm, rn in live_names:
            if nm.startswith(plan_name):
                return rn
        return None

    svc = client.get_service("AdGroupAdService")
    topics = Counter()
    probed = 0
    examples: list[str] = []
    for campaign in plan.campaigns:
        for ag in campaign.ad_groups:
            if probed >= args.sample:
                break
            ag_rn = live_rn_for(ag.name)
            if ag_rn is None:
                continue
            for ad in ag.ads:
                text_n = _extract_text_n(str(ad.final_url))
                if text_n is None or (ag_rn, text_n) in state.existing_rsa_text_n:
                    continue  # this variant is already live → wasn't rejected
                # Rejected (missing) variant — validate_only create, no partial_failure.
                op = _build_rsa_op(client, ag_rn, ad)
                try:
                    svc.mutate_ad_group_ads(
                        request={"customer_id": cust_digits, "operations": [op], "validate_only": True}
                    )
                    # Passed validation → would NOT have been rejected for policy.
                except GoogleAdsException as exc:
                    found = []
                    for err in exc.failure.errors:
                        found += _extract_policy_topics(err)
                    for t in found:
                        topics[t] += 1
                    if found and len(examples) < 5:
                        h = ad.headlines[2].text if len(ad.headlines) > 2 else ad.headlines[0].text
                        examples.append(f"{ag.name} text={text_n}: topics={found} | sample headline: {h!r}")
                probed += 1
                break  # one rejected variant per ad group is enough for a sample

    print(f"Probed {probed} rejected RSA variants via validate_only.")
    print("Policy topics found (topic -> count):")
    for t, n in topics.most_common():
        print(f"   {t}: {n}")
    if not topics:
        print("   (none — variants passed validate_only; rejection may be content-review-time only)")
    print("\nExamples:")
    for e in examples:
        print("  -", e)


if __name__ == "__main__":
    main()
