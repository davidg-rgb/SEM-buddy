"""Variant generation contract tests.

Covers the v0.3.2 multi-RSA path: each ad group must produce 3-5 distinct
RSAs with separate lever stacks, and at least one variant must surface the
discount percent when the product carries `discount_pct > 0`.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.generators.ad_copy_generator import (
    MAX_VARIANTS,
    MIN_VARIANTS,
    NON_DISCOUNT_VARIANTS,
    VARIANT_ORDER,
    _product_has_discount,
    generate_rsa_variants,
)
from src.generators.campaign_builder import (
    build_campaigns_from_catalog,
    catalog_row_to_product,
)
from src.generators.csv_exporter import export_campaign_plan
from src.catalog import load_catalog_from_yaml
from src.models.catalog import CampaignBuildConfig, Product
from src.models.client import ClientProfile


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_YAML = FIXTURE_DIR / "catalog_sample.yaml"


def _en_client() -> ClientProfile:
    return ClientProfile(
        business_name="Flightnetwork",
        website_url="https://www.flightnetwork.com/",
        industry="travel",
        products_services=["cheap flights"],
        language="en",
        monthly_budget_sek=2_000_000,
    )


def _build_config() -> CampaignBuildConfig:
    return CampaignBuildConfig(
        structure_mode="sku",
        campaign_name_template="Flightnetwork - All Destinations",
        ad_group_name_template="{name} ({sku})",
        language="en",
        url_templates={
            "primary": "https://www.flightnetwork.com/from/google/rf/destination?to={sku}&text={N}"
        },
        text_n_range=(1, 5),
        keyword_templates=[
            "flights to {name}",
            "cheap flights to {name}",
            "{name} flights",
        ],
        keyword_match_types=["PHRASE", "EXACT"],
        promotion_enabled=True,
        promotion_attribute="discount_pct",
        bid_rules=[
            {"if": "discount_pct >= 0.50", "then": {"modifier": 2.25}},
            {"if": "discount_pct >= 0.40", "then": {"modifier": 2.00}},
            {"if": "discount_pct >= 0.30", "then": {"modifier": 1.80}},
            {"if": "discount_pct >= 0.25", "then": {"modifier": 1.60}},
            {"if": "discount_pct >= 0.20", "then": {"modifier": 1.45}},
            {"if": "discount_pct >= 0.15", "then": {"modifier": 1.30}},
            {"if": "discount_pct >= 0.10", "then": {"modifier": 1.15}},
            {"if": "discount_pct >= 0.05", "then": {"modifier": 1.05}},
            {"if": "from_price < 100", "then": {"modifier": 1.10}},
        ],
    )


# ---------------------------------------------------------------------------
# Variant count contracts
# ---------------------------------------------------------------------------


def test_discount_product_emits_five_variants(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="BKK", name="Bangkok",
        attributes={"from_price": 299.0, "discount_pct": 0.38},
    )
    variants = generate_rsa_variants(
        "Bangkok", client, ["flights to Bangkok"],
        "https://www.flightnetwork.com/?to=BKK&text=1",
        product=p,
    )
    assert len(variants) == 5
    # Bounded
    assert MIN_VARIANTS <= len(variants) <= MAX_VARIANTS


def test_zero_discount_product_emits_four_variants(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="NYC", name="New York City",
        attributes={"from_price": 450.0, "discount_pct": 0.0},
    )
    variants = generate_rsa_variants(
        "New York City", client, ["flights to New York"],
        "https://www.flightnetwork.com/?to=NYC&text=1",
        product=p,
    )
    assert len(variants) == 4
    assert len(variants) >= MIN_VARIANTS


def test_missing_discount_attribute_treats_as_zero(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="SFO", name="San Francisco",
        attributes={"from_price": 350.0},  # no discount_pct key at all
    )
    variants = generate_rsa_variants(
        "San Francisco", client, ["flights to SFO"],
        "https://www.flightnetwork.com/?to=SFO&text=1",
        product=p,
    )
    assert len(variants) == 4
    assert not _product_has_discount(p)


# ---------------------------------------------------------------------------
# Discount mention contract
# ---------------------------------------------------------------------------


def test_discount_variant_surfaces_discount_pct_in_headlines(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="BKK", name="Bangkok",
        attributes={"from_price": 299.0, "discount_pct": 0.38},
    )
    variants = generate_rsa_variants(
        "Bangkok", client, ["flights to Bangkok"],
        "https://www.flightnetwork.com/?to=BKK&text=1",
        product=p,
    )
    # The second variant in VARIANT_ORDER is `discount_led`; it must mention "38"
    discount_variant = variants[VARIANT_ORDER.index("discount_led")]
    headline_text = " | ".join(h.text for h in discount_variant.headlines)
    assert "38" in headline_text, (
        f"discount_led variant missing '38' in headlines: {headline_text}"
    )


def test_discount_variant_surfaces_discount_pct_in_descriptions(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="WMI", name="Warsaw",
        attributes={"from_price": 178.0, "discount_pct": 0.44},
    )
    variants = generate_rsa_variants(
        "Warsaw", client, ["flights to Warsaw"],
        "https://www.flightnetwork.com/?to=WMI&text=1",
        product=p,
    )
    discount_variant = variants[VARIANT_ORDER.index("discount_led")]
    desc_text = " | ".join(d.text for d in discount_variant.descriptions)
    assert "44" in desc_text, (
        f"discount_led variant missing '44' in descriptions: {desc_text}"
    )


def test_non_discount_variants_do_not_lead_with_discount(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="BKK", name="Bangkok",
        attributes={"from_price": 299.0, "discount_pct": 0.38},
    )
    variants = generate_rsa_variants(
        "Bangkok", client, ["flights to Bangkok"],
        "https://www.flightnetwork.com/?to=BKK&text=1",
        product=p,
    )
    # The price_led / social_proof / urgency / loss_aversion variants should
    # carry distinct levers — they may incidentally mention the percent via
    # universal patterns, but the pinned H3 must NOT be the discount CTA.
    for role in ("price_led", "social_proof", "urgency", "loss_aversion"):
        v = variants[VARIANT_ORDER.index(role)]
        h3 = v.headlines[2].text
        assert "%" not in h3, f"Variant {role} H3 should not lead with discount: {h3!r}"


# ---------------------------------------------------------------------------
# Variant fingerprint uniqueness
# ---------------------------------------------------------------------------


def test_all_variants_have_distinct_headline_lists(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="LIS", name="Lisbon",
        attributes={"from_price": 199.0, "discount_pct": 0.25},
    )
    variants = generate_rsa_variants(
        "Lisbon", client, ["flights to Lisbon"],
        "https://www.flightnetwork.com/?to=LIS&text=1",
        product=p,
    )
    fingerprints = [tuple(h.text for h in v.headlines) for v in variants]
    assert len(set(fingerprints)) == len(fingerprints), (
        f"Two variants share identical headlines: {fingerprints}"
    )


def test_all_variants_use_distinct_pinned_h3(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="MAD", name="Madrid",
        attributes={"from_price": 215.0, "discount_pct": 0.32},
    )
    variants = generate_rsa_variants(
        "Madrid", client, ["flights to Madrid"],
        "https://www.flightnetwork.com/?to=MAD&text=1",
        product=p,
    )
    h3s = [v.headlines[2].text for v in variants]
    assert len(set(h3s)) == len(h3s), f"Two variants share H3 CTA: {h3s}"


def test_every_variant_reaches_excellent_headline_count(monkeypatch) -> None:
    """All variants should fill 15 headlines (=> 'Excellent' Ad Strength)."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    p = Product(
        sku="LHR", name="London",
        attributes={"from_price": 250.0, "discount_pct": 0.28},
    )
    variants = generate_rsa_variants(
        "London", client, ["flights to London"],
        "https://www.flightnetwork.com/?to=LHR&text=1",
        product=p,
    )
    for v in variants:
        assert len(v.headlines) >= 10, (
            f"Variant has only {len(v.headlines)} headlines — won't earn Excellent"
        )
        assert len(v.descriptions) == 4, (
            f"Variant should fill all 4 descriptions, got {len(v.descriptions)}"
        )


# ---------------------------------------------------------------------------
# Catalog → CSV with variants
# ---------------------------------------------------------------------------


def test_full_catalog_emits_three_to_five_variants_per_ag(monkeypatch) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    for ag in plan.campaigns[0].ad_groups:
        assert MIN_VARIANTS <= len(ag.ads) <= MAX_VARIANTS, (
            f"Ad group {ag.name} has {len(ag.ads)} variants — "
            f"expected {MIN_VARIANTS}-{MAX_VARIANTS}"
        )


# ---------------------------------------------------------------------------
# Prohibited-symbol guard — Google RSA SYMBOLS policy
# ---------------------------------------------------------------------------
#
# The BLACK STAR (U+2605) in the Trustpilot social-proof lines ("4.5* on
# Trustpilot") tripped Google's SYMBOLS prohibition and got the social_proof
# variant of all 963 etraveli ad groups rejected at create time (2026-05-24).
# Google bans DECORATIVE symbols (Unicode category "So": stars, checkmarks,
# emoji) but allows currency ($ = Sc), math (+ = Sm), punctuation (/ % = Po),
# and accented / non-Latin letters in destination names. So the rule is:
# no character of category "So" (or modifier-symbol "Sk") may appear in copy.


def _prohibited_symbol(text: str) -> str | None:
    import unicodedata
    for ch in text:
        if unicodedata.category(ch) in ("So", "Sk"):
            return ch
    return None


def test_no_duplicate_headlines_in_long_name_discount_variant(monkeypatch) -> None:
    """Google rejects an RSA whose headlines aren't all distinct ("Assets are
    duplicated across operations"). The discount force-injection stored its
    dedup key raw while `_add` stored it casefolded, so a pattern headline like
    "Save 28% on Thiruvananthapuram" slipped past the forced line and duplicated
    it — on 44 long-name destinations (2026-05-24). Headlines must be unique
    case-insensitively across every variant."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    # Long names + discounts — the exact shape that produced duplicates.
    products = [
        Product(sku="TRV", name="Thiruvananthapuram", attributes={"from_price": 410.0, "discount_pct": 0.28}),
        Product(sku="UUS", name="Yuzhno-Sakhalinsk", attributes={"from_price": 380.0, "discount_pct": 0.25}),
        Product(sku="GPS", name="Galapagos Islands", attributes={"from_price": 690.0, "discount_pct": 0.44}),
    ]
    for p in products:
        variants = generate_rsa_variants(
            p.name, client, [f"flights to {p.name}"],
            f"https://www.flightnetwork.com/?to={p.sku}&text=1",
            product=p,
        )
        for v in variants:
            texts = [h.text.casefold() for h in v.headlines]
            assert len(texts) == len(set(texts)), (
                f"Duplicate headline in {p.name} {v.role}: "
                f"{[t for t, n in __import__('collections').Counter(texts).items() if n > 1]}"
            )


def test_pattern_pool_has_no_prohibited_symbols() -> None:
    """The raw English pattern pool must not embed decorative symbols — the
    direct source of the 2026-05-24 SYMBOLS rejection."""
    import json
    pack = Path(__file__).parent.parent / "data" / "en" / "ad_copy_patterns.json"
    data = json.loads(pack.read_text(encoding="utf-8"))

    offenders: list[str] = []

    def walk(node):
        if isinstance(node, str):
            bad = _prohibited_symbol(node)
            if bad:
                offenders.append(f"U+{ord(bad):04X} in {node!r}")
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    assert not offenders, "Prohibited symbols in ad_copy_patterns.json:\n" + "\n".join(offenders)


def test_generated_rsa_copy_has_no_prohibited_symbols(monkeypatch) -> None:
    """Generated headlines + descriptions (incl. the Trustpilot social_proof
    variant) must be free of decorative symbols. Currency/punctuation/accented
    destination names are fine — only category So/Sk is rejected."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    # Cover a discount + a zero-discount product (the latter still emits the
    # social_proof variant that carried the star), plus an accented name to
    # prove legitimate non-ASCII letters are NOT flagged.
    products = [
        Product(sku="BKK", name="Bangkok", attributes={"from_price": 299.0, "discount_pct": 0.38}),
        Product(sku="NYC", name="New York City", attributes={"from_price": 450.0, "discount_pct": 0.0}),
        Product(sku="GRU", name="São Paulo", attributes={"from_price": 510.0, "discount_pct": 0.12}),
    ]
    for p in products:
        variants = generate_rsa_variants(
            p.name, client, [f"flights to {p.name}"],
            f"https://www.flightnetwork.com/?to={p.sku}&text=1",
            product=p,
        )
        for v in variants:
            for asset in list(v.headlines) + list(v.descriptions):
                bad = _prohibited_symbol(asset.text)
                assert bad is None, (
                    f"Prohibited symbol U+{ord(bad):04X} in {p.name} "
                    f"{v.role} copy: {asset.text!r}"
                )


def test_every_discounted_destination_has_discount_variant(monkeypatch) -> None:
    """Contract: every product with discount_pct>0 must have ≥1 RSA whose text
    contains the discount percent. The user's brief is explicit: at least one
    ad variant per destination must surface the discount.
    """
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    by_sku = {p.sku: p for p in products}
    failures: list[str] = []
    for ag in plan.campaigns[0].ad_groups:
        sku = ag.name.rsplit("(", 1)[-1].rstrip(")")
        product = by_sku.get(sku)
        if product is None:
            continue
        dp = product.attributes.get("discount_pct")
        if not dp or float(dp) <= 0:
            continue
        pct_int = int(round(float(dp) * 100 if dp <= 1 else dp))
        pct_str = str(pct_int)
        # Search all variants' headlines + descriptions for the pct
        found = False
        for ad in ag.ads:
            blob = " | ".join(h.text for h in ad.headlines) + " | " + \
                   " | ".join(d.text for d in ad.descriptions)
            if pct_str in blob:
                found = True
                break
        if not found:
            failures.append(f"{ag.name} (discount={dp}) lacks {pct_str}% in any RSA")
    assert not failures, "Missing discount surface for:\n" + "\n".join(failures)


def test_csv_exporter_emits_all_variant_rows(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())
    export_dir = Path(export_campaign_plan(plan, str(tmp_path)))

    rsa_path = export_dir / "04_responsive_search_ads.csv"
    with rsa_path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # Total variant rows = sum of len(ag.ads) across all ad groups
    expected = sum(len(ag.ads) for ag in plan.campaigns[0].ad_groups)
    assert len(rows) == expected, (
        f"CSV has {len(rows)} RSA rows; plan has {expected}"
    )

    # Group rows by ad group; each group should have 3-5 rows
    by_ag: dict[str, int] = {}
    for r in rows:
        by_ag[r["Ad Group"]] = by_ag.get(r["Ad Group"], 0) + 1
    for ag_name, count in by_ag.items():
        assert MIN_VARIANTS <= count <= MAX_VARIANTS, (
            f"Ad group {ag_name} has {count} RSA rows in CSV"
        )


# ---------------------------------------------------------------------------
# Bid-rule ladder coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "discount_pct,expected_modifier",
    [
        (0.00, 1.00),  # No rule fires
        (0.01, 1.00),  # Below 5% threshold
        (0.05, 1.05),
        (0.09, 1.05),
        (0.10, 1.15),
        (0.14, 1.15),
        (0.15, 1.30),
        (0.19, 1.30),
        (0.20, 1.45),
        (0.24, 1.45),
        (0.25, 1.60),
        (0.29, 1.60),
        (0.30, 1.80),
        (0.39, 1.80),
        (0.40, 2.00),
        (0.49, 2.00),
        (0.50, 2.25),
        (0.60, 2.25),
    ],
)
def test_bid_ladder_for_each_discount_band(
    monkeypatch, discount_pct: float, expected_modifier: float,
) -> None:
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    from src.catalog.bid_rules import apply_rules, parse_rules
    rules = parse_rules(_build_config().bid_rules)
    # Use a high from_price so the price-based rule doesn't fire
    p = Product(
        sku="TEST", name="Test City",
        attributes={"from_price": 500.0, "discount_pct": discount_pct},
    )
    result = apply_rules(p, rules, "Campaign", "AG")
    assert result.immediate_modifier == expected_modifier, (
        f"discount_pct={discount_pct}: expected x{expected_modifier}, "
        f"got x{result.immediate_modifier}"
    )


def test_low_price_rule_fires_for_zero_discount_cheap_destinations(monkeypatch) -> None:
    """Sub-$100 destinations with no discount get the price-based boost."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    from src.catalog.bid_rules import apply_rules, parse_rules
    rules = parse_rules(_build_config().bid_rules)
    p = Product(
        sku="CHEAP", name="Cheap City",
        attributes={"from_price": 75.0, "discount_pct": 0.0},
    )
    result = apply_rules(p, rules, "Campaign", "AG")
    assert result.immediate_modifier == 1.10


# ---------------------------------------------------------------------------
# Variant role registry sanity
# ---------------------------------------------------------------------------


def test_variant_order_contains_all_five_roles() -> None:
    assert set(VARIANT_ORDER) == {
        "price_led", "discount_led", "social_proof", "urgency", "loss_aversion"
    }
    assert NON_DISCOUNT_VARIANTS == tuple(
        r for r in VARIANT_ORDER if r != "discount_led"
    )


# ---------------------------------------------------------------------------
# v0.3.4 contracts — Mission 2 / 3 / 4
# ---------------------------------------------------------------------------


import re as _re


def _extract_text_n(url: str) -> int | None:
    m = _re.search(r"[?&]text=(\d+)", url)
    return int(m.group(1)) if m else None


# Mission 3 ------------------------------------------------------------------


def test_variants_have_distinct_text_n_urls(monkeypatch) -> None:
    """Each variant in an ad group must carry a different text=N URL."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    for ag in plan.campaigns[0].ad_groups:
        ns = []
        for ad in ag.ads:
            n = _extract_text_n(str(ad.final_url))
            assert n is not None, f"Ad group {ag.name} ad lacks text=N: {ad.final_url}"
            ns.append(n)
        assert len(set(ns)) == len(ns), (
            f"Ad group {ag.name} has duplicate text=N values: {ns}"
        )


def test_variants_text_n_starts_at_one_and_increments(monkeypatch) -> None:
    """With default range (1,5), variant slot i (0-indexed) → text={i+1}."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    for ag in plan.campaigns[0].ad_groups:
        for i, ad in enumerate(ag.ads):
            n = _extract_text_n(str(ad.final_url))
            assert n == i + 1, (
                f"Ad group {ag.name} variant {i} expected text={i+1}, got text={n}"
            )


def test_keyword_url_inherits_first_variant_text(monkeypatch) -> None:
    """Keyword-level URLs (used by the live pusher as fallback) should match
    variant 1's URL — keeps the keyword and the first variant aligned in
    analytics so the keyword fallback never shows a different text=N."""
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    for ag in plan.campaigns[0].ad_groups:
        if not ag.ads:
            continue
        first_variant_url = str(ag.ads[0].final_url)
        # The ad group's first variant carries text=1.
        assert "text=1" in first_variant_url, (
            f"Ad group {ag.name} variant[0] URL missing text=1: {first_variant_url}"
        )


# Mission 2 ------------------------------------------------------------------


_SAVE_UP_TO_RE = _re.compile(r"^Save up to \d+%", _re.IGNORECASE)


def test_every_discounted_destination_surfaces_save_up_to_pct_to_name(monkeypatch) -> None:
    """Every product with discount_pct >= 0.15 must have ≥1 headline that:
      (a) starts with 'Save up to {pct}%', OR
      (b) carries the {pct}% AND a name token AND the word 'Save' (fit-aware
          fallback for long-name destinations where the canonical pattern
          doesn't fit 30 chars).
    SKU/IATA must NEVER appear in the matched headline (Mission 4 contract).
    """
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    by_sku = {p.sku: p for p in products}
    failures: list[str] = []
    for ag in plan.campaigns[0].ad_groups:
        sku = ag.name.rsplit("(", 1)[-1].rstrip(")")
        product = by_sku.get(sku)
        if product is None:
            continue
        dp = product.attributes.get("discount_pct")
        if dp is None:
            continue
        dp_val = float(dp)
        if dp_val > 1:
            dp_val /= 100.0
        if dp_val < 0.15:
            continue  # below floor — discount_led variant not emitted
        pct_int = int(round(dp_val * 100))
        pct_str = str(pct_int)
        name_tokens = product.name.split()
        primary_token = (name_tokens[0] if name_tokens else "").lower()
        matched: str | None = None
        for ad in ag.ads:
            for h in ad.headlines:
                t = h.text
                # SKU must NOT appear in this headline
                if product.sku and product.sku in t:
                    continue
                # Canonical: 'Save up to X%'
                if t.lower().startswith(f"save up to {pct_str}%"):
                    matched = t
                    break
                # Acceptable fallback: contains 'Save' + pct + name indicator
                if (
                    "save" in t.lower()
                    and pct_str in t
                    and (primary_token in t.lower() or any(
                        tok.lower() in t.lower() for tok in name_tokens[:3] if len(tok) >= 4
                    ))
                ):
                    matched = t
                    break
            if matched:
                break
        if not matched:
            failures.append(
                f"{ag.name} (discount={dp_val:.2f}) lacks 'Save up to {pct_str}% to/on {product.name}' headline"
            )
    assert not failures, (
        "Missing mandatory Save-up-to-pct headline for:\n" + "\n".join(failures)
    )


# Mission 4: no-SKU policy ---------------------------------------------------


def _is_iata_3letter(s: str) -> bool:
    return bool(_re.fullmatch(r"[A-Z]{3}", s))


def test_no_sku_token_in_headlines_or_descriptions(monkeypatch) -> None:
    """Operator constraint: customer copy NEVER contains the SKU/IATA code.

    Walks every headline and description across every RSA and asserts the
    product SKU does NOT appear as a stand-alone token.
    """
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    by_sku = {p.sku: p for p in products}
    violations: list[str] = []
    for ag in plan.campaigns[0].ad_groups:
        sku = ag.name.rsplit("(", 1)[-1].rstrip(")")
        product = by_sku.get(sku)
        if product is None or not _is_iata_3letter(product.sku):
            continue
        pattern = _re.compile(rf"\b{_re.escape(product.sku)}\b")
        for i, ad in enumerate(ag.ads):
            for h in ad.headlines:
                if pattern.search(h.text):
                    violations.append(
                        f"{ag.name} variant {i}: headline {h.text!r} contains SKU {product.sku!r}"
                    )
            for d in ad.descriptions:
                if pattern.search(d.text):
                    violations.append(
                        f"{ag.name} variant {i}: description {d.text!r} contains SKU {product.sku!r}"
                    )
    assert not violations, (
        "SKU/IATA leaked into customer copy:\n" + "\n".join(violations[:30])
    )


# Mission 4: from_price guarantee --------------------------------------------


def test_every_priced_destination_surfaces_from_price(monkeypatch) -> None:
    """Operator brief: include the from_price in at least one version of the
    ad copy. Contract: every ad group whose product has a known positive
    from_price must surface that price token (e.g. '$450') in at least one
    headline OR description across all variants.
    """
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    by_sku = {p.sku: p for p in products}
    failures: list[str] = []
    for ag in plan.campaigns[0].ad_groups:
        sku = ag.name.rsplit("(", 1)[-1].rstrip(")")
        product = by_sku.get(sku)
        if product is None:
            continue
        fp = product.attributes.get("from_price")
        if fp is None:
            continue
        try:
            fp_val = float(fp)
        except (TypeError, ValueError):
            continue
        if fp_val <= 0:
            continue
        # Format matching what _format_number / _fill_pattern produce.
        price_str = f"${int(fp_val):,}" if float(fp_val).is_integer() else f"${fp_val:,.2f}"
        found = False
        for ad in ag.ads:
            blob = " | ".join(h.text for h in ad.headlines) + " | " + \
                   " | ".join(d.text for d in ad.descriptions)
            if price_str in blob:
                found = True
                break
        if not found:
            failures.append(
                f"{ag.name} (from_price={fp_val}) lacks '{price_str}' in any variant"
            )
    assert not failures, "Missing from_price for:\n" + "\n".join(failures)


def test_resolver_never_returns_sku() -> None:
    """`_resolve_customer_display_name` must never return the SKU."""
    from src.generators.ad_copy_generator import _resolve_customer_display_name
    # Genuinely-long name with no comma and no parens — even at tiny budget
    # the resolver still returns the name (truncation is the caller's
    # responsibility), never the SKU.
    p = Product(
        sku="PKC",
        name="Petropavlovsk-Kamchats, Russian Federation",
        attributes={},
    )
    for budget in (8, 15, 25, 30, 90):
        out = _resolve_customer_display_name(p, budget)
        assert "PKC" not in out, (
            f"Resolver returned SKU at budget={budget}: {out!r}"
        )

    # West Palm Beach (Florida) → 'West Palm Beach' at budget 18+
    p2 = Product(sku="PBI", name="West Palm Beach (Florida)", attributes={})
    out = _resolve_customer_display_name(p2, 18)
    assert "PBI" not in out
    assert "West Palm Beach" in out


def test_long_name_fallback_uses_name_not_sku(monkeypatch) -> None:
    """Pattern pack v4: long_name_fallback patterns must compose with the
    resolved name (never {sku}). Verifies no patterns substitute the SKU.
    """
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()
    # Long-name destination → triggers the long_name_fallback path.
    p = Product(
        sku="PKC",
        name="Petropavlovsk-Kamchats, Russian Federation",
        attributes={"from_price": 380.0, "discount_pct": 0.20},
    )
    variants = generate_rsa_variants(
        "Petropavlovsk", client, ["flights"],
        "https://www.flightnetwork.com/?to=PKC&text=1",
        product=p,
    )
    sku_uses = []
    for v in variants:
        for h in v.headlines:
            if "PKC" in h.text:
                sku_uses.append(f"H: {h.text!r}")
        for d in v.descriptions:
            if "PKC" in d.text:
                sku_uses.append(f"D: {d.text!r}")
    assert not sku_uses, (
        f"Long-name fallback leaked SKU 'PKC' into copy: {sku_uses}"
    )


# v0.3.4 fix 3.1: orphan first-name truncations -----------------------------


def test_no_orphan_first_name_in_long_destinations(monkeypatch) -> None:
    """For every product with a 3+ word destination name, no headline may be
    a strict prefix of the name that loses 2+ trailing words.

    Catches the v0.3.4 reviewer-flagged 'Save up to 46% to Fernando',
    'Lock today's Fernando', 'Stop overpaying Fernando' pathology where
    `_fit_to_limit` chopped 'Fernando De Noronha' to its first word.
    """
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    client = _en_client()

    # Multi-word destinations covering the three orphan patterns:
    #   - internal Romance particle ('Fernando De Noronha')
    #   - 3+ word, no particle ('Bandar Seri Begawan')
    #   - 4 word with internal particle ('San Carlos De Bariloche')
    cases = [
        Product(
            sku="FEN", name="Fernando De Noronha",
            attributes={"from_price": 412.0, "discount_pct": 0.46},
        ),
        Product(
            sku="BWN", name="Bandar Seri Begawan",
            attributes={"from_price": 680.0, "discount_pct": 0.22},
        ),
        Product(
            sku="BRC", name="San Carlos De Bariloche",
            attributes={"from_price": 320.0, "discount_pct": 0.38},
        ),
    ]

    violations: list[str] = []
    for product in cases:
        tokens = product.name.split()
        if len(tokens) < 3:
            continue
        # Strict-prefix orphans: words[:k] for 1 <= k <= len-2 (loses 2+ words).
        orphan_prefixes = [" ".join(tokens[:k]) for k in range(1, len(tokens) - 1)]
        variants = generate_rsa_variants(
            product.name, client, [f"flights to {product.name}"],
            f"https://www.flightnetwork.com/?to={product.sku}&text=1",
            product=product,
        )
        for vi, v in enumerate(variants):
            for h in v.headlines:
                text = h.text
                # An orphan presents when the headline ENDS with one of the
                # orphan prefixes (the name was at the trailing position of
                # the pattern and truncation lopped off the rest).
                for prefix in orphan_prefixes:
                    if text == prefix or text.endswith(" " + prefix):
                        violations.append(
                            f"{product.sku} variant {vi}: headline {text!r} "
                            f"is a strict prefix of {product.name!r} losing "
                            f"{len(tokens) - len(prefix.split())} trailing words"
                        )

    assert not violations, (
        "Orphan first-name truncations detected:\n" + "\n".join(violations[:30])
    )


# v0.3.4 fix 3.3: 'Cheap …' banned phrase ------------------------------------


def test_no_cheap_lead_in_in_any_headline(monkeypatch) -> None:
    """No variant headline may start with 'Cheap ' — sem-ad-copy skill banlist
    + FTC/ASA risk. The keyword pool may still contain 'cheap flights to {name}'
    as a match term, but the headline-fallback path must filter the title-cased
    version before it ships.
    """
    monkeypatch.setenv("SEM_DISABLE_LLM", "1")
    catalog = load_catalog_from_yaml(SAMPLE_YAML)
    products = [catalog_row_to_product(r) for r in catalog]
    plan = build_campaigns_from_catalog(_en_client(), products, _build_config())

    offenders: list[str] = []
    for ag in plan.campaigns[0].ad_groups:
        for vi, ad in enumerate(ag.ads):
            for h in ad.headlines:
                if h.text.lstrip().lower().startswith("cheap "):
                    offenders.append(f"{ag.name} variant {vi}: {h.text!r}")
    assert not offenders, (
        "Banned 'Cheap …' headlines leaked into copy:\n" + "\n".join(offenders[:30])
    )
