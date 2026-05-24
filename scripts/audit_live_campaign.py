"""Complete read-only setup audit of a LIVE Google Ads campaign.

Pulls the full campaign hierarchy from the Google Ads API in a handful of
campaign-filtered GAQL queries (one per resource type — NOT per ad group), then
aggregates counts, statuses, policy/approval signals, ad strength, and extension
links in Python. Produces a structured markdown audit report and a console
summary. Nothing is mutated — every call is a `search`.

Audited dimensions:
  1. Account + campaign settings (status, channel, bid strategy, network,
     EU-political flag, dates, optimization score)
  2. Budget (daily amount, delivery, shared)
  3. Geo + language + campaign-level negative targeting
  4. Ad groups (counts by status/type, default CPC bids, bid distribution)
  5. Keywords (counts by match type/status, negatives, approval/serving status)
  6. RSAs (counts by status, ad-strength distribution, policy approval,
     disapproved/limited topics)
  7. Assets / extensions (campaign-level sitelinks+callouts, ad-group-level
     promotions, link counts)
  8. Health checks — ad groups with 0 keywords / <3 RSAs, disapproved keywords,
     disapproved/limited RSAs, weak ad strength, missing targeting

GAQL rule baked in (v0.3.7 lesson): a SELECT must include every cross-resource
field used in WHERE, so campaign-filtered queries on child resources all
`SELECT campaign.id`.

Usage:
    python -m scripts.audit_live_campaign <slug> [--campaign <id>] [--customer <id>]
                                                 [--out <path.md>] [--no-write]
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from src.apis.google_ads import GoogleAdsService


# --------------------------------------------------------------------------
# Query helpers
# --------------------------------------------------------------------------

def _try_search(svc: GoogleAdsService, query: str, label: str) -> tuple[list, str | None]:
    """Run a GAQL query; return (rows, error_message). Never raises."""
    try:
        return svc._search(query), None
    except Exception as exc:  # noqa: BLE001 - audit must survive any single failure
        return [], f"{label}: {exc}"


def micros_to_sek(micros: int | None) -> float | None:
    return None if micros in (None, 0) else micros / 1_000_000


# Approval statuses that are NOT a problem: either explicitly approved, or
# simply not-yet-reviewed (which is the norm for a PAUSED campaign Google has
# never had a reason to review). Anything else (DISAPPROVED, *LIMITED,
# AREA_OF_INTEREST_ONLY, SITE_SUSPENDED, …) is a real finding.
APPROVAL_OK = {"APPROVED", "UNKNOWN", "UNSPECIFIED", "UNDER_REVIEW"}
# Ad-strength values that mean "not evaluated yet" rather than "weak".
STRENGTH_PENDING = {"PENDING", "UNKNOWN", "UNSPECIFIED", "NO_ADS"}


# --------------------------------------------------------------------------
# Section fetchers
# --------------------------------------------------------------------------

def fetch_account(svc: GoogleAdsService) -> dict:
    rows, err = _try_search(
        svc,
        "SELECT customer.id, customer.descriptive_name, customer.currency_code, "
        "customer.time_zone, customer.test_account FROM customer LIMIT 1",
        "account",
    )
    if err or not rows:
        return {"_error": err}
    c = rows[0].customer
    return {
        "id": str(c.id),
        "name": c.descriptive_name,
        "currency": c.currency_code,
        "timezone": c.time_zone,
        "test_account": bool(c.test_account),
    }


def fetch_campaign(svc: GoogleAdsService, campaign_id: str) -> dict:
    # Curated, known-good field set. Bid-strategy sub-objects return defaults
    # when the active strategy differs, which is harmless.
    query = f"""
        SELECT
          campaign.id, campaign.name, campaign.status, campaign.serving_status,
          campaign.advertising_channel_type, campaign.advertising_channel_sub_type,
          campaign.bidding_strategy_type,
          campaign.target_roas.target_roas,
          campaign.maximize_conversion_value.target_roas,
          campaign.target_cpa.target_cpa_micros,
          campaign.network_settings.target_google_search,
          campaign.network_settings.target_search_network,
          campaign.network_settings.target_content_network,
          campaign.network_settings.target_partner_search_network,
          campaign.contains_eu_political_advertising,
          campaign.optimization_score,
          campaign_budget.amount_micros, campaign_budget.delivery_method,
          campaign_budget.explicitly_shared, campaign_budget.name
        FROM campaign WHERE campaign.id = {campaign_id}
    """
    rows, err = _try_search(svc, query, "campaign")
    if err or not rows:
        return {"_error": err or "campaign not found"}
    r = rows[0]
    c, b = r.campaign, r.campaign_budget
    ns = c.network_settings
    return {
        "id": str(c.id),
        "name": c.name,
        "status": c.status.name,
        "serving_status": c.serving_status.name,
        "channel": c.advertising_channel_type.name,
        "sub_channel": c.advertising_channel_sub_type.name,
        "bid_strategy": c.bidding_strategy_type.name,
        "target_roas": c.target_roas.target_roas or c.maximize_conversion_value.target_roas or None,
        "target_cpa_micros": c.target_cpa.target_cpa_micros or None,
        "net_google_search": ns.target_google_search,
        "net_search_partners": ns.target_search_network,
        "net_content": ns.target_content_network,
        "net_partner_search": ns.target_partner_search_network,
        "eu_political": c.contains_eu_political_advertising.name,
        "optimization_score": c.optimization_score,
        "budget_daily_sek": micros_to_sek(b.amount_micros),
        "budget_delivery": b.delivery_method.name,
        "budget_shared": b.explicitly_shared,
        "budget_name": b.name,
    }


def fetch_criteria(svc: GoogleAdsService, campaign_id: str) -> dict:
    query = f"""
        SELECT campaign.id, campaign_criterion.type, campaign_criterion.status,
               campaign_criterion.negative,
               campaign_criterion.language.language_constant,
               campaign_criterion.location.geo_target_constant,
               campaign_criterion.keyword.text,
               campaign_criterion.keyword.match_type
        FROM campaign_criterion WHERE campaign.id = {campaign_id}
    """
    rows, err = _try_search(svc, query, "campaign_criterion")
    langs, geos, neg_geos, neg_kws = [], [], [], []
    for row in rows:
        cc = row.campaign_criterion
        ctype = cc.type_.name
        if ctype == "LANGUAGE":
            langs.append(cc.language.language_constant.split("/")[-1])
        elif ctype == "LOCATION":
            gid = cc.location.geo_target_constant.split("/")[-1]
            (neg_geos if cc.negative else geos).append(gid)
        elif ctype == "KEYWORD" and cc.negative:
            neg_kws.append(cc.keyword.text)
    return {
        "_error": err,
        "languages": langs,
        "geos": geos,
        "negative_geos": neg_geos,
        "negative_keywords": neg_kws,
    }


def fetch_ad_groups(svc: GoogleAdsService, campaign_id: str) -> dict:
    query = f"""
        SELECT campaign.id, ad_group.id, ad_group.name, ad_group.status,
               ad_group.type, ad_group.cpc_bid_micros
        FROM ad_group WHERE campaign.id = {campaign_id}
    """
    rows, err = _try_search(svc, query, "ad_group")
    groups = {}
    status_ctr, type_ctr = Counter(), Counter()
    bid_ctr = Counter()
    for row in rows:
        ag = row.ad_group
        agid = str(ag.id)
        cpc = micros_to_sek(ag.cpc_bid_micros)
        groups[agid] = {
            "name": ag.name,
            "status": ag.status.name,
            "type": ag.type_.name,
            "cpc_sek": cpc,
        }
        status_ctr[ag.status.name] += 1
        type_ctr[ag.type_.name] += 1
        if cpc is not None:
            bid_ctr[round(cpc, 2)] += 1
    return {
        "_error": err,
        "groups": groups,
        "total": len(groups),
        "by_status": dict(status_ctr),
        "by_type": dict(type_ctr),
        "cpc_distribution": dict(sorted(bid_ctr.items())),
    }


def fetch_keywords(svc: GoogleAdsService, campaign_id: str) -> dict:
    # approval_status / system_serving_status are optional; try the rich query
    # first, fall back to the minimal one if the API rejects a field.
    rich = f"""
        SELECT campaign.id, ad_group.id,
               ad_group_criterion.keyword.text,
               ad_group_criterion.keyword.match_type,
               ad_group_criterion.status,
               ad_group_criterion.negative,
               ad_group_criterion.approval_status,
               ad_group_criterion.system_serving_status
        FROM ad_group_criterion
        WHERE campaign.id = {campaign_id} AND ad_group_criterion.type = 'KEYWORD'
    """
    minimal = f"""
        SELECT campaign.id, ad_group.id,
               ad_group_criterion.keyword.text,
               ad_group_criterion.keyword.match_type,
               ad_group_criterion.status,
               ad_group_criterion.negative
        FROM ad_group_criterion
        WHERE campaign.id = {campaign_id} AND ad_group_criterion.type = 'KEYWORD'
    """
    rows, err = _try_search(svc, rich, "keywords(rich)")
    has_approval = True
    if err:
        rows, err = _try_search(svc, minimal, "keywords")
        has_approval = False

    per_ag = Counter()
    match_ctr, status_ctr, approval_ctr, serving_ctr = Counter(), Counter(), Counter(), Counter()
    neg_per_ag = Counter()
    total_pos = total_neg = 0
    disapproved = []
    for row in rows:
        c = row.ad_group_criterion
        agid = str(row.ad_group.id)
        if c.negative:
            total_neg += 1
            neg_per_ag[agid] += 1
            continue
        total_pos += 1
        per_ag[agid] += 1
        match_ctr[c.keyword.match_type.name] += 1
        status_ctr[c.status.name] += 1
        if has_approval:
            ap = c.approval_status.name
            sv = c.system_serving_status.name
            approval_ctr[ap] += 1
            serving_ctr[sv] += 1
            if ap not in APPROVAL_OK:
                disapproved.append({"ad_group": agid, "text": c.keyword.text,
                                    "match": c.keyword.match_type.name, "approval": ap})
    return {
        "_error": err,
        "total_positive": total_pos,
        "total_negative": total_neg,
        "by_match_type": dict(match_ctr),
        "by_status": dict(status_ctr),
        "by_approval": dict(approval_ctr) if has_approval else None,
        "by_serving": dict(serving_ctr) if has_approval else None,
        "disapproved": disapproved,
        "per_ag": per_ag,
        "neg_per_ag": neg_per_ag,
    }


def _symbol_glyphs(text: str) -> set[str]:
    """Return decorative-symbol glyphs Google's RSA SYMBOLS policy bans.

    Catches Unicode categories So (★ ✓ ✔ emoji …) and Sk. Deliberately allows
    currency ($ = Sc), math (+ = Sm) and punctuation (/ = Po) which the
    catalog copy legitimately uses.
    """
    return {ch for ch in text if unicodedata.category(ch) in ("So", "Sk")}


def fetch_rsas(svc: GoogleAdsService, campaign_id: str) -> dict:
    query = f"""
        SELECT campaign.id, ad_group.id, ad_group.name, ad_group_ad.ad.id,
               ad_group_ad.status, ad_group_ad.ad_strength,
               ad_group_ad.policy_summary.approval_status,
               ad_group_ad.policy_summary.review_status,
               ad_group_ad.policy_summary.policy_topic_entries,
               ad_group_ad.ad.responsive_search_ad.headlines,
               ad_group_ad.ad.responsive_search_ad.descriptions,
               ad_group_ad.ad.final_urls
        FROM ad_group_ad
        WHERE campaign.id = {campaign_id}
          AND ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'
          AND ad_group_ad.status != 'REMOVED'
    """
    rows, err = _try_search(svc, query, "rsas")
    per_ag = Counter()
    status_ctr, strength_ctr, approval_ctr, review_ctr = Counter(), Counter(), Counter(), Counter()
    flagged = []  # disapproved or limited per Google's (lagging) review
    symbol_ads = []  # content actually contains a banned glyph — review-independent
    topic_ctr = Counter()
    for row in rows:
        aga = row.ad_group_ad
        agid = str(row.ad_group.id)
        per_ag[agid] += 1
        status_ctr[aga.status.name] += 1
        strength_ctr[aga.ad_strength.name] += 1
        ps = aga.policy_summary
        ap = ps.approval_status.name
        approval_ctr[ap] += 1
        review_ctr[ps.review_status.name] += 1
        topics = [t.topic for t in ps.policy_topic_entries]
        for t in topics:
            topic_ctr[t] += 1
        if ap not in APPROVAL_OK:
            flagged.append({"ad_group": agid, "ad_id": str(aga.ad.id),
                            "approval": ap, "topics": topics})
        # Review-independent content scan: a banned glyph IS a violation even
        # before Google's review catches up (it lags on PAUSED campaigns).
        rsa = aga.ad.responsive_search_ad
        glyphs: set[str] = set()
        for asset in list(rsa.headlines) + list(rsa.descriptions):
            glyphs |= _symbol_glyphs(asset.text)
        if glyphs:
            urls = list(aga.ad.final_urls)
            text_n = urls[0].split("text=")[-1] if urls and "text=" in urls[0] else "?"
            symbol_ads.append({
                "ad_group": agid,
                "ad_group_name": row.ad_group.name,
                "ad_id": str(aga.ad.id),
                "text_n": text_n,
                "glyphs": "".join(sorted(glyphs)),
            })
    return {
        "_error": err,
        "total": sum(per_ag.values()),
        "by_status": dict(status_ctr),
        "by_strength": dict(strength_ctr),
        "by_approval": dict(approval_ctr),
        "by_review": dict(review_ctr),
        "policy_topics": dict(topic_ctr),
        "flagged": flagged,
        "symbol_ads": symbol_ads,
        "per_ag": per_ag,
    }


def fetch_campaign_assets(svc: GoogleAdsService, campaign_id: str) -> dict:
    query = f"""
        SELECT campaign.id, campaign_asset.field_type, campaign_asset.status,
               asset.type
        FROM campaign_asset WHERE campaign.id = {campaign_id}
    """
    rows, err = _try_search(svc, query, "campaign_asset")
    field_ctr, status_ctr = Counter(), Counter()
    for row in rows:
        ca = row.campaign_asset
        field_ctr[ca.field_type.name] += 1
        status_ctr[ca.status.name] += 1
    return {"_error": err, "total": sum(field_ctr.values()),
            "by_field": dict(field_ctr), "by_status": dict(status_ctr)}


def fetch_ad_group_assets(svc: GoogleAdsService, campaign_id: str) -> dict:
    query = f"""
        SELECT campaign.id, ad_group.id, ad_group_asset.field_type,
               ad_group_asset.status, asset.type
        FROM ad_group_asset WHERE campaign.id = {campaign_id}
    """
    rows, err = _try_search(svc, query, "ad_group_asset")
    field_ctr, status_ctr = Counter(), Counter()
    per_ag = Counter()          # all links (incl. REMOVED)
    enabled_per_ag = Counter()  # ENABLED links only — the live, serving extensions
    for row in rows:
        aga = row.ad_group_asset
        status = aga.status.name
        field_ctr[aga.field_type.name] += 1
        status_ctr[status] += 1
        per_ag[str(row.ad_group.id)] += 1
        if status == "ENABLED":
            enabled_per_ag[str(row.ad_group.id)] += 1
    return {"_error": err, "total": sum(field_ctr.values()),
            "by_field": dict(field_ctr), "by_status": dict(status_ctr),
            "per_ag": per_ag, "enabled_per_ag": enabled_per_ag}


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------

def build_report(slug, customer_id, campaign_id, account, campaign, criteria,
                 ad_groups, keywords, rsas, camp_assets, ag_assets) -> tuple[str, list[str], list[str]]:
    """Return (markdown, issues, notes).

    `issues`  = real problems that block or degrade the campaign.
    `notes`   = expected/informational observations (paused, pending review,
                placeholder bid strategy, dedupe residue, optimization signals).
    """
    issues: list[str] = []
    notes: list[str] = []
    L: list[str] = []
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    def h(s): L.append(s)

    h(f"# Live Setup Audit — {slug}")
    h("")
    h(f"**Generated:** {today}  ")
    h(f"**Customer:** {customer_id}  ")
    h(f"**Campaign:** `{campaign_id}` — {campaign.get('name','?')}  ")
    h(f"**Account:** {account.get('name','?')} "
      f"({account.get('currency','?')}, {account.get('timezone','?')}"
      f"{', TEST' if account.get('test_account') else ''})")
    h("")
    h("> Read-only audit. Counts of *ENABLED* entities are the live, serving "
      "state; *REMOVED* rows are historical (e.g. dedupe residue) and never serve.")
    h("")
    h("---")
    h("")

    if campaign.get("_error"):
        issues.append(f"Campaign settings query failed: {campaign['_error']}")

    # ---- 1. Campaign settings ----
    h("## 1. Campaign settings")
    h("")
    h("| Field | Live value |")
    h("|---|---|")
    rows = [
        ("Status", campaign.get("status")),
        ("Serving status", campaign.get("serving_status")),
        ("Channel", f"{campaign.get('channel')} / {campaign.get('sub_channel')}"),
        ("Bid strategy", campaign.get("bid_strategy")),
        ("Target ROAS", campaign.get("target_roas")),
        ("Budget (SEK/day)", campaign.get("budget_daily_sek")),
        ("Budget delivery", campaign.get("budget_delivery")),
        ("Budget shared", campaign.get("budget_shared")),
        ("Network: Google Search", campaign.get("net_google_search")),
        ("Network: Search partners", campaign.get("net_search_partners")),
        ("Network: Display/content", campaign.get("net_content")),
        ("Network: Partner search", campaign.get("net_partner_search")),
        ("EU political ads", campaign.get("eu_political")),
        ("Optimization score", campaign.get("optimization_score")),
    ]
    for k, v in rows:
        h(f"| {k} | {v} |")
    h("")

    # Settings classification
    status = campaign.get("status")
    if status == "PAUSED":
        notes.append("Campaign is PAUSED — expected; operator flips to ENABLED after review.")
    elif status and status != "ENABLED":
        issues.append(f"Campaign status is {status}.")
    if campaign.get("net_content"):
        issues.append("Display/content network is ON — a Search campaign should have it OFF.")
    if campaign.get("net_partner_search"):
        issues.append("Partner search network is ON (unusual for a fresh SEM campaign).")
    if campaign.get("net_google_search") is False:
        issues.append("Google Search network is OFF — the campaign cannot serve on Search.")
    eu = campaign.get("eu_political") or ""
    if eu and "DOES_NOT_CONTAIN" not in eu:
        issues.append(f"EU political advertising flag = {eu} (expected DOES_NOT_CONTAIN).")
    bs = campaign.get("bid_strategy")
    # TARGET_SPEND is the bidding_strategy_type the API reports for "Maximize
    # clicks" — the test-account placeholder the pusher applies.
    if bs in ("MAXIMIZE_CLICKS", "TARGET_SPEND"):
        notes.append(f"Bid strategy = {bs} (= Maximize Clicks, test-account placeholder). "
                     "Switch to TARGET_ROAS 4.0 once conversion tracking is live (per case.yaml).")
    elif bs in ("TARGET_ROAS", "MAXIMIZE_CONVERSION_VALUE", "MAXIMIZE_CONVERSIONS", "TARGET_CPA"):
        notes.append(f"Bid strategy = {bs} (smart) — confirm conversion tracking is enabled before ENABLE.")

    # ---- 2. Targeting ----
    h("## 2. Targeting (geo + language)")
    h("")
    geos = criteria.get("geos") or []
    langs = criteria.get("languages") or []
    LANG_NAMES = {"1000": "English", "1053": "Swedish"}
    lang_disp = ", ".join(f"{l} ({LANG_NAMES.get(l, '?')})" for l in langs) or "*(none — all languages)*"
    geo_disp = ", ".join(geos) if geos else "*(none — all locations / unrestricted)*"
    h(f"- **Languages:** {lang_disp}")
    h(f"- **Locations:** {geo_disp}")
    h(f"- **Negative locations:** {criteria.get('negative_geos') or '*(none)*'}")
    h(f"- **Campaign negative keywords:** {len(criteria.get('negative_keywords') or [])}")
    h("")
    if not langs:
        issues.append("No language targeting — ads serve to all languages.")
    if not geos:
        notes.append("No geo targeting — campaign reaches ALL locations (global). "
                     "Confirm this is intended for Flightnetwork; otherwise add geo criteria.")
    if criteria.get("_error"):
        issues.append(f"Targeting query error: {criteria['_error']}")

    # ---- 3. Ad groups ----
    h("## 3. Ad groups")
    h("")
    h(f"- **Total:** {ad_groups.get('total')}")
    h(f"- **By status:** {ad_groups.get('by_status')}")
    h(f"- **By type:** {ad_groups.get('by_type')}")
    h("")
    cpc_dist = ad_groups.get("cpc_distribution") or {}
    if cpc_dist:
        h(f"**Default CPC bid distribution (SEK)** — {len(cpc_dist)} distinct value(s):")
        h("")
        h("| CPC (SEK) | Ad groups |")
        h("|---|---|")
        for cpc, n in cpc_dist.items():
            h(f"| {cpc:.2f} | {n} |")
        h("")
        # The discount/seasonality bid ladder lives in each ad group's
        # bid_modifier; the INITIAL push only writes cpc_bid_micros when an
        # absolute max_cpc_sek is set. So a uniform floor CPC means the ladder
        # was never materialized on the live campaign (apply-bids not run).
        total_ag = ad_groups.get("total") or 0
        floor = min(cpc_dist) if cpc_dist else None
        at_floor = cpc_dist.get(floor, 0)
        uniform_floor = (len(cpc_dist) == 1 and floor is not None and floor <= 0.05)
        if uniform_floor and total_ag:
            notes.append(
                f"All {at_floor} ad groups sit at the {floor:.2f} SEK CPC floor — the "
                "discount/seasonality bid ladder (case.yaml bid_rules) is NOT materialized "
                "on the live campaign. Under Maximize Clicks the per-ad-group CPC is largely "
                "ignored, so delivery isn't blocked; but before switching to a manual/target "
                "strategy run `sem case apply-bids etraveli --name-suffix \" [2026-05-22 22:19:35]\" "
                "--base-cpc-sek <X> --yes` to push the ladder."
            )

    # ---- 4. Keywords ----
    h("## 4. Keywords")
    h("")
    h(f"- **Positive keywords:** {keywords.get('total_positive')}")
    h(f"- **Negative keywords (ad-group level):** {keywords.get('total_negative')}")
    h(f"- **By match type:** {keywords.get('by_match_type')}")
    h(f"- **By status:** {keywords.get('by_status')}")
    if keywords.get("by_approval") is not None:
        h(f"- **By approval status:** {keywords.get('by_approval')}")
        h(f"- **By serving status:** {keywords.get('by_serving')}")
    h("")
    # Pending review (UNDER_REVIEW) is expected on a paused campaign.
    appr = keywords.get("by_approval") or {}
    pending_kw = appr.get("UNDER_REVIEW", 0)
    if pending_kw:
        notes.append(f"{pending_kw} keywords UNDER_REVIEW — normal; Google reviews on ENABLE.")
    serving = keywords.get("by_serving") or {}
    rarely = serving.get("RARELY_SERVED", 0)
    if rarely:
        notes.append(f"{rarely} keywords RARELY_SERVED (low search volume) — candidates to prune "
                     "or consolidate after launch.")
    disK = keywords.get("disapproved") or []
    if disK:
        issues.append(f"{len(disK)} keywords are DISAPPROVED/LIMITED (real policy block).")
        h(f"**Disapproved / limited keywords ({len(disK)}):**")
        h("")
        h("| Ad group | Keyword | Match | Approval |")
        h("|---|---|---|---|")
        for d in disK[:50]:
            h(f"| {d['ad_group']} | {d['text']} | {d['match']} | {d['approval']} |")
        if len(disK) > 50:
            h(f"| … | *+{len(disK) - 50} more* | | |")
        h("")

    # ---- 5. RSAs ----
    h("## 5. Responsive search ads")
    h("")
    h(f"- **Total RSAs:** {rsas.get('total')}")
    h(f"- **By status:** {rsas.get('by_status')}")
    h(f"- **Ad strength:** {rsas.get('by_strength')}")
    h(f"- **By approval:** {rsas.get('by_approval')}")
    h(f"- **By review status:** {rsas.get('by_review')}")
    if rsas.get("policy_topics"):
        h(f"- **Policy topics:** {rsas.get('policy_topics')}")
    h("")
    strength = rsas.get("by_strength") or {}
    pending_strength = sum(v for k, v in strength.items() if k in STRENGTH_PENDING)
    if pending_strength:
        notes.append(f"{pending_strength} RSAs at PENDING ad strength — strength is only computed "
                     "after review; expected while PAUSED.")
    poor = strength.get("POOR", 0)
    if poor:
        issues.append(f"{poor} RSAs at POOR ad strength — improve headline/description diversity.")
    topics = rsas.get("policy_topics") or {}
    if topics:
        notes.append(f"RSA policy-topic entries present (per Google's review so far): {topics}. "
                     "Review is incomplete on a PAUSED campaign, so this undercounts — see the "
                     "content scan below for the true figure.")
    # Review-independent banned-glyph scan — the authoritative SYMBOLS check.
    symbol_ads = rsas.get("symbol_ads") or []
    if symbol_ads:
        glyphset = "".join(sorted({s["glyphs"] for s in symbol_ads}))
        seen_by_google = (rsas.get("policy_topics") or {}).get("SYMBOLS", 0)
        issues.append(
            f"{len(symbol_ads)} RSAs still contain banned decorative symbol(s) "
            f"({glyphset}) in headline/description — Google's RSA SYMBOLS policy. "
            "These predate the v0.3.7 fix and were skipped by the resume push. "
            f"Google has surfaced the SYMBOLS topic on {seen_by_google} so far "
            "(review lags on PAUSED); the rest will be limited once reviewed. "
            "Fix: remove + recreate with star-free copy."
        )
        h(f"**RSAs containing banned symbols ({len(symbol_ads)}) — content scan, "
          "review-independent:**")
        h("")
        h("| Ad group | Ad ID | text=N | Glyph |")
        h("|---|---|---|---|")
        for s in symbol_ads[:60]:
            h(f"| {s['ad_group_name']} | {s['ad_id']} | {s['text_n']} | `{s['glyphs']}` |")
        if len(symbol_ads) > 60:
            h(f"| … | *+{len(symbol_ads) - 60} more* | | |")
        h("")
    flagged = rsas.get("flagged") or []
    if flagged:
        issues.append(f"{len(flagged)} RSAs are DISAPPROVED/LIMITED (real policy block).")
        h(f"**Flagged RSAs ({len(flagged)}):**")
        h("")
        h("| Ad group | Ad ID | Approval | Topics |")
        h("|---|---|---|---|")
        for f in flagged[:50]:
            h(f"| {f['ad_group']} | {f['ad_id']} | {f['approval']} | {', '.join(f['topics']) or '—'} |")
        if len(flagged) > 50:
            h(f"| … | *+{len(flagged) - 50} more* | | |")
        h("")

    # ---- 6. Assets / extensions ----
    h("## 6. Assets & extensions")
    h("")
    ca_status = camp_assets.get("by_status") or {}
    ag_status = ag_assets.get("by_status") or {}
    ca_enabled = ca_status.get("ENABLED", 0)
    ca_removed = ca_status.get("REMOVED", 0)
    promo_enabled = ag_status.get("ENABLED", 0)
    promo_removed = ag_status.get("REMOVED", 0)
    h("**Campaign-level assets (sitelinks, callouts):**")
    h("")
    h(f"- ENABLED links: **{ca_enabled}**  ·  REMOVED (residue): {ca_removed}")
    h(f"- By field type (all statuses): {camp_assets.get('by_field')}")
    h(f"- By status: {ca_status}")
    h("")
    h("**Ad-group-level assets (promotions):**")
    h("")
    h(f"- ENABLED links: **{promo_enabled}**  ·  REMOVED (residue): {promo_removed}")
    h(f"- By status: {ag_status}")
    h("")
    if ca_removed or promo_removed:
        notes.append(f"{ca_removed} campaign-asset + {promo_removed} promotion links are REMOVED "
                     "(dedupe residue from the resume push). Harmless — they never serve.")

    # ---- 7. Health checks ----
    h("## 7. Health checks")
    h("")
    groups = ad_groups.get("groups") or {}
    kw_per = keywords.get("per_ag") or Counter()
    rsa_per = rsas.get("per_ag") or Counter()
    promo_per = ag_assets.get("enabled_per_ag") or Counter()

    active_ids = [agid for agid, g in groups.items() if g["status"] != "REMOVED"]
    no_kw = [agid for agid in active_ids if kw_per.get(agid, 0) == 0]
    no_rsa = [agid for agid in active_ids if rsa_per.get(agid, 0) == 0]
    low_rsa = [agid for agid in active_ids if 0 < rsa_per.get(agid, 0) < 3]
    no_promo = [agid for agid in active_ids if promo_per.get(agid, 0) == 0]

    # 0 keywords / 0 RSAs / <3 RSAs are structural problems.
    structural = [
        ("Ad groups with 0 keywords", no_kw, True),
        ("Ad groups with 0 RSAs", no_rsa, True),
        ("Ad groups with <3 RSAs (Google recommends 3+)", low_rsa, True),
        # 0 ENABLED promotions is expected for zero-discount destinations.
        ("Ad groups with 0 ENABLED promotion assets", no_promo, False),
    ]
    h("| Check | Count | Verdict |")
    h("|---|---|---|")
    for label, lst, is_issue in structural:
        verdict = "✅ OK" if not lst else ("⚠️ ISSUE" if is_issue else "ℹ️ expected")
        h(f"| {label} | {len(lst)} | {verdict} |")
    h("")
    for label, lst, is_issue in structural:
        if not lst:
            continue
        if is_issue:
            issues.append(f"{len(lst)} {label.lower()}.")
        else:
            notes.append(f"{len(lst)} {label.lower()} — expected (destinations with discount_pct = 0 "
                         "generate no promotion).")
        if len(lst) <= 25:
            named = ", ".join(f"{a} ({groups[a]['name']})" for a in lst)
            h(f"- **{label}:** {named}")
        else:
            h(f"- **{label}:** {len(lst)} ad groups (first 25): {', '.join(lst[:25])} …")
    h("")

    # ---- Findings summary ----
    h("## Findings summary")
    h("")
    h("### ⚠️ Issues (action needed)")
    h("")
    if issues:
        for f in issues:
            h(f"- {f}")
    else:
        h("- ✅ None. No blocking problems detected.")
    h("")
    h("### ℹ️ Notes (expected / informational)")
    h("")
    if notes:
        for f in notes:
            h(f"- {f}")
    else:
        h("- (none)")
    h("")
    h("---")
    h(f"*Read-only audit — no entities mutated. Generated by SEM Master {today}.*")

    return "\n".join(L), issues, notes


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only setup audit of a live Google Ads campaign.")
    ap.add_argument("slug", nargs="?", default="etraveli")
    ap.add_argument("--customer", default="469-180-7001")
    ap.add_argument("--campaign", default="23867614686")
    ap.add_argument("--out", default=None, help="Markdown output path")
    ap.add_argument("--no-write", action="store_true", help="Console only; don't write the .md file")
    args = ap.parse_args()

    # Windows consoles default to cp1252 and choke on the arrows/checkmarks.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    print(f"Auditing campaign {args.campaign} on {args.customer} (slug={args.slug}) …", flush=True)
    svc = GoogleAdsService(args.customer)

    print("  → account info", flush=True)
    account = fetch_account(svc)
    print("  → campaign settings + budget", flush=True)
    campaign = fetch_campaign(svc, args.campaign)
    print("  → targeting (geo/language/negatives)", flush=True)
    criteria = fetch_criteria(svc, args.campaign)
    print("  → ad groups", flush=True)
    ad_groups = fetch_ad_groups(svc, args.campaign)
    print(f"  → keywords (this is the big one, ~10k rows)", flush=True)
    keywords = fetch_keywords(svc, args.campaign)
    print(f"  → RSAs (~4.6k rows)", flush=True)
    rsas = fetch_rsas(svc, args.campaign)
    print("  → campaign-level assets", flush=True)
    camp_assets = fetch_campaign_assets(svc, args.campaign)
    print("  → ad-group-level assets (promotions)", flush=True)
    ag_assets = fetch_ad_group_assets(svc, args.campaign)

    md, issues, notes = build_report(
        args.slug, args.customer, args.campaign, account, campaign, criteria,
        ad_groups, keywords, rsas, camp_assets, ag_assets,
    )

    # Console summary
    ca_status = camp_assets.get("by_status") or {}
    ag_status = ag_assets.get("by_status") or {}
    print("\n" + "=" * 70)
    print(f"AUDIT COMPLETE — {args.slug} / campaign {args.campaign}")
    print("=" * 70)
    print(f"Status: {campaign.get('status')} | Bid: {campaign.get('bid_strategy')} | "
          f"Budget: {campaign.get('budget_daily_sek')} SEK/day")
    print(f"Targeting: lang={criteria.get('languages')} geo={criteria.get('geos') or 'ALL'}")
    print(f"Ad groups: {ad_groups.get('total')} | "
          f"Keywords: {keywords.get('total_positive')} (+{keywords.get('total_negative')} neg) | "
          f"RSAs: {rsas.get('total')}")
    print(f"RSA strength: {rsas.get('by_strength')}")
    print(f"RSA approval: {rsas.get('by_approval')} | review: {rsas.get('by_review')}")
    print(f"KW approval: {keywords.get('by_approval')} | serving: {keywords.get('by_serving')}")
    print(f"Campaign assets ENABLED: {ca_status.get('ENABLED', 0)} (+{ca_status.get('REMOVED', 0)} removed) | "
          f"Promo assets ENABLED: {ag_status.get('ENABLED', 0)} (+{ag_status.get('REMOVED', 0)} removed)")
    print("-" * 70)
    print(f"ISSUES ({len(issues)}):")
    if issues:
        for f in issues:
            print(f"  ⚠️  {f}")
    else:
        print("  ✅ None — no blocking problems detected.")
    print(f"\nNOTES ({len(notes)}):")
    for f in notes:
        print(f"  •  {f}")
    print("=" * 70)

    # Report errors from any failed query
    errs = [d.get("_error") for d in (account, criteria, ad_groups, keywords, rsas,
                                      camp_assets, ag_assets) if isinstance(d, dict) and d.get("_error")]
    if errs:
        print("\nQuery warnings (non-fatal):")
        for e in errs:
            print(f"  ! {e}")

    if not args.no_write:
        out = Path(args.out) if args.out else (
            Path("clients") / args.slug / "audits" /
            f"SETUP-AUDIT-{datetime.now().strftime('%Y-%m-%d')}.md"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"\nReport written: {out}")


if __name__ == "__main__":
    main()
