"""Tests for the live-campaign setup audit's classification logic.

`build_report` consumes plain dicts (not live protos), so the whole
issue-vs-note classifier is unit-testable offline. These guard the core
correctness rule discovered during the etraveli audit: a PAUSED campaign's
"awaiting review" state (UNDER_REVIEW keywords, PENDING RSA strength) is NOT a
disapproval and must surface as an informational note, never a blocking issue —
while genuine DISAPPROVED entities and a Display network on a Search campaign
must surface as issues.
"""

from __future__ import annotations

from collections import Counter

from scripts.audit_live_campaign import build_report, micros_to_sek, _symbol_glyphs


def _healthy_inputs():
    """A clean, freshly-pushed PAUSED campaign mirroring the etraveli state."""
    account = {"name": "Test", "currency": "SEK", "timezone": "Europe/Stockholm",
               "test_account": True}
    campaign = {
        "status": "PAUSED", "serving_status": "SERVING", "channel": "SEARCH",
        "sub_channel": "UNSPECIFIED", "bid_strategy": "TARGET_SPEND",
        "target_roas": None, "budget_daily_sek": 66666.67, "budget_delivery": "STANDARD",
        "budget_shared": False, "net_google_search": True, "net_search_partners": True,
        "net_content": False, "net_partner_search": False,
        "eu_political": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        "optimization_score": 0.0,
    }
    criteria = {"_error": None, "languages": ["1000"], "geos": [],
                "negative_geos": [], "negative_keywords": []}
    groups = {f"ag{i}": {"name": f"Dest {i}", "status": "PAUSED",
                         "type": "SEARCH_STANDARD", "cpc_sek": 0.01} for i in range(3)}
    ad_groups = {"_error": None, "groups": groups, "total": 3,
                 "by_status": {"PAUSED": 3}, "by_type": {"SEARCH_STANDARD": 3},
                 "cpc_distribution": {0.01: 3}}
    kw_per = Counter({"ag0": 10, "ag1": 10, "ag2": 10})
    keywords = {"_error": None, "total_positive": 30, "total_negative": 0,
                "by_match_type": {"EXACT": 15, "PHRASE": 15},
                "by_status": {"ENABLED": 30},
                "by_approval": {"UNDER_REVIEW": 30},
                "by_serving": {"ELIGIBLE": 24, "RARELY_SERVED": 6},
                "disapproved": [], "per_ag": kw_per, "neg_per_ag": Counter()}
    rsa_per = Counter({"ag0": 5, "ag1": 5, "ag2": 5})
    rsas = {"_error": None, "total": 15, "by_status": {"PAUSED": 15},
            "by_strength": {"PENDING": 15}, "by_approval": {"UNKNOWN": 15},
            "by_review": {"REVIEW_IN_PROGRESS": 15}, "policy_topics": {},
            "flagged": [], "per_ag": rsa_per}
    camp_assets = {"_error": None, "total": 16, "by_field": {"SITELINK": 8, "CALLOUT": 8},
                   "by_status": {"ENABLED": 8, "REMOVED": 8}}
    ag_assets = {"_error": None, "total": 6, "by_field": {"PROMOTION": 6},
                 "by_status": {"ENABLED": 3, "REMOVED": 3},
                 "per_ag": Counter({"ag0": 1, "ag1": 1, "ag2": 1}),
                 "enabled_per_ag": Counter({"ag0": 1, "ag1": 1, "ag2": 1})}
    return (account, campaign, criteria, ad_groups, keywords, rsas, camp_assets, ag_assets)


def test_symbol_glyphs_flags_decorative_symbols_only():
    # ★ (U+2605, category So) is banned by Google's RSA SYMBOLS policy.
    assert _symbol_glyphs("4.5★ on Trustpilot") == {"★"}
    assert _symbol_glyphs("Save ✓ now ✔") == {"✓", "✔"}
    # Legitimate catalog characters must NOT be flagged.
    assert _symbol_glyphs("Fares from $304") == set()       # $ = Sc
    assert _symbol_glyphs("Compare 800+ airlines") == set()  # + = Sm
    assert _symbol_glyphs("4.5/5 on Trustpilot") == set()    # / = Po
    assert _symbol_glyphs("Voos para São Paulo") == set()    # accents are letters


def test_symbol_ads_surface_as_issue():
    inputs = list(_healthy_inputs())
    rsas = dict(inputs[5])
    rsas["symbol_ads"] = [
        {"ad_group": "ag0", "ad_group_name": "Lima (LIM)", "ad_id": "810058035806",
         "text_n": "3", "glyphs": "★"},
    ]
    inputs[5] = rsas
    _, issues, _ = build_report("etraveli", "x", "1", *inputs)
    assert any("banned decorative symbol" in i for i in issues)


def test_no_symbol_ads_means_no_symbol_issue():
    _, issues, _ = build_report("etraveli", "x", "1", *_healthy_inputs())
    assert not any("banned decorative symbol" in i for i in issues)


def test_micros_to_sek():
    assert micros_to_sek(66_666_670_000) == 66666.67
    assert micros_to_sek(0) is None
    assert micros_to_sek(None) is None
    assert micros_to_sek(1_000_000) == 1.0


def test_healthy_paused_campaign_has_no_issues():
    md, issues, notes = build_report("etraveli", "469-180-7001", "1", *_healthy_inputs())
    assert issues == [], f"healthy campaign should raise no blocking issues, got: {issues}"
    assert md.startswith("# Live Setup Audit")


def test_pending_review_is_a_note_not_an_issue():
    """UNDER_REVIEW keywords and PENDING RSA strength are expected, not problems."""
    _, issues, notes = build_report("etraveli", "x", "1", *_healthy_inputs())
    joined_notes = " ".join(notes)
    assert "UNDER_REVIEW" in joined_notes
    assert "PENDING ad strength" in joined_notes
    # And they must NOT appear as issues.
    joined_issues = " ".join(issues)
    assert "UNDER_REVIEW" not in joined_issues
    assert "POOR" not in joined_issues


def test_rarely_served_surfaces_as_note():
    _, _, notes = build_report("etraveli", "x", "1", *_healthy_inputs())
    assert any("RARELY_SERVED" in n for n in notes)


def test_uniform_floor_cpc_flags_inactive_bid_ladder():
    _, _, notes = build_report("etraveli", "x", "1", *_healthy_inputs())
    assert any("bid ladder" in n and "floor" in n for n in notes)


def test_removed_links_reported_as_residue_note():
    _, _, notes = build_report("etraveli", "x", "1", *_healthy_inputs())
    assert any("REMOVED" in n and "residue" in n.lower() for n in notes)


def test_disapproved_keyword_is_an_issue():
    inputs = list(_healthy_inputs())
    keywords = dict(inputs[4])
    keywords["disapproved"] = [{"ad_group": "ag0", "text": "bad kw",
                                "match": "EXACT", "approval": "DISAPPROVED"}]
    keywords["by_approval"] = {"UNDER_REVIEW": 29, "DISAPPROVED": 1}
    inputs[4] = keywords
    _, issues, _ = build_report("etraveli", "x", "1", *inputs)
    assert any("DISAPPROVED" in i and "keyword" in i.lower() for i in issues)


def test_disapproved_rsa_is_an_issue():
    inputs = list(_healthy_inputs())
    rsas = dict(inputs[5])
    rsas["flagged"] = [{"ad_group": "ag0", "ad_id": "999",
                        "approval": "DISAPPROVED", "topics": ["SYMBOLS"]}]
    inputs[5] = rsas
    _, issues, _ = build_report("etraveli", "x", "1", *inputs)
    assert any("RSA" in i and "DISAPPROVED" in i for i in issues)


def test_display_network_on_search_campaign_is_an_issue():
    inputs = list(_healthy_inputs())
    campaign = dict(inputs[1])
    campaign["net_content"] = True
    inputs[1] = campaign
    _, issues, _ = build_report("etraveli", "x", "1", *inputs)
    assert any("content network" in i.lower() for i in issues)


def test_ad_group_with_zero_keywords_is_an_issue():
    inputs = list(_healthy_inputs())
    keywords = dict(inputs[4])
    keywords["per_ag"] = Counter({"ag0": 10, "ag1": 10})  # ag2 has none
    inputs[4] = keywords
    _, issues, _ = build_report("etraveli", "x", "1", *inputs)
    assert any("0 keywords" in i for i in issues)


def test_poor_ad_strength_is_an_issue():
    inputs = list(_healthy_inputs())
    rsas = dict(inputs[5])
    rsas["by_strength"] = {"PENDING": 13, "POOR": 2}
    inputs[5] = rsas
    _, issues, _ = build_report("etraveli", "x", "1", *inputs)
    assert any("POOR ad strength" in i for i in issues)


def test_zero_discount_promo_gap_is_a_note_not_issue():
    """Ad groups with no ENABLED promotion are expected (zero-discount destinations)."""
    inputs = list(_healthy_inputs())
    ag_assets = dict(inputs[7])
    ag_assets["enabled_per_ag"] = Counter({"ag0": 1, "ag1": 1})  # ag2 has no promo
    inputs[7] = ag_assets
    _, issues, notes = build_report("etraveli", "x", "1", *inputs)
    assert not any("promotion" in i.lower() for i in issues)
    assert any("promotion" in n.lower() for n in notes)
