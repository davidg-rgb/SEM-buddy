"""Tests for per-row keyword templating (C9)."""

from __future__ import annotations

from src.generators.keyword_generator import (
    generate_keywords_for_product,
    render_keyword_template,
    sanitize_keyword_text,
)
from src.models.catalog import Product


def _p(**attrs) -> Product:
    base = {"sku": "BKK", "name": "Bangkok", "attributes": {}}
    if "attributes" in attrs:
        base["attributes"] = attrs.pop("attributes")
    base.update(attrs)
    return Product(**base)


def test_render_keyword_template_substitutes_name() -> None:
    p = _p()
    assert render_keyword_template("flights to {name}", p) == "flights to Bangkok"


def test_render_keyword_template_skips_when_attribute_missing() -> None:
    p = _p()
    # discount_pct not in attributes -> None
    assert render_keyword_template("{discount_pct}% off {name}", p) is None


def test_render_keyword_template_uses_attributes() -> None:
    # Note: Google Ads disallows `$` in keyword text, so it's stripped.
    p = _p(attributes={"from_price": 499})
    assert render_keyword_template("flights from {from_price}", p) == "flights from 499"


def test_generate_keywords_for_product_basic() -> None:
    p = _p()
    templates = [
        "flights to {name}",
        "cheap flights to {name}",
        "{name} flights",
        "{sku} flights",
    ]
    kws = generate_keywords_for_product(p, templates, match_types=["PHRASE", "EXACT"])
    # 4 templates × 2 match types = 8
    assert len(kws) == 8
    texts = {k.text for k in kws}
    assert "flights to Bangkok" in texts
    assert "BKK flights" in texts


def test_generate_keywords_for_product_skips_missing_attributes() -> None:
    p = _p(attributes={})  # no from_price
    templates = [
        "flights to {name}",
        "flights from ${from_price}",  # would render empty -> skip
        "{name} flights",
    ]
    kws = generate_keywords_for_product(p, templates)
    texts = [k.text for k in kws]
    assert "flights to Bangkok" in texts
    assert "Bangkok flights" in texts
    assert all("${" not in t for t in texts)
    assert len(kws) == 2  # only 2 templates rendered cleanly


def test_generate_keywords_for_product_deduplicates() -> None:
    """Identical templates produce identical text; case-insensitive dedupe."""
    p = _p()
    # Google Ads treats keyword text case-insensitively, so we dedupe by lower()
    templates = ["{name} flights", "{name} FLIGHTS"]
    kws = generate_keywords_for_product(p, templates, match_types=["PHRASE"])
    assert len(kws) == 1

    kws2 = generate_keywords_for_product(p, ["{name} flights", "{name} flights"], match_types=["PHRASE"])
    assert len(kws2) == 1


def test_generate_keywords_skips_over_80_chars() -> None:
    long_name = "A" * 100
    p = Product(sku="X", name=long_name)
    kws = generate_keywords_for_product(p, ["flights to {name}"])
    assert kws == []


def test_default_match_type_is_phrase() -> None:
    p = _p()
    kws = generate_keywords_for_product(p, ["{name} flights"])
    assert len(kws) == 1
    assert kws[0].match_type == "PHRASE"


def test_sanitize_strips_parentheses() -> None:
    assert sanitize_keyword_text("West Palm Beach (Florida)") == "West Palm Beach Florida"


def test_sanitize_strips_commas() -> None:
    """Google Ads rejects commas in keyword text despite being common in destination names."""
    assert sanitize_keyword_text("San Andres Island, Colombia") == "San Andres Island Colombia"


def test_sanitize_strips_other_special_chars() -> None:
    assert sanitize_keyword_text("flights! to / Bangkok?") == "flights to Bangkok"
    assert sanitize_keyword_text("a [b] c") == "a b c"
    assert sanitize_keyword_text("foo:bar*baz") == "foo bar baz"
    assert sanitize_keyword_text("trip.com") == "trip com"


def test_sanitize_preserves_allowed_punct() -> None:
    assert sanitize_keyword_text("Mazow'iecki") == "Mazow'iecki"
    assert sanitize_keyword_text("rock & roll") == "rock & roll"
    assert sanitize_keyword_text("flight tickets - cheap") == "flight tickets - cheap"


def test_render_with_parens_in_name_is_sanitized() -> None:
    p = Product(sku="PBI", name="West Palm Beach (Florida)")
    rendered = render_keyword_template("book flights {name}", p)
    assert "(" not in rendered
    assert "Florida" in rendered


# v0.3.6 — alias-driven keyword expansion ----------------------------------


def test_keyword_generator_expands_name_templates_across_aliases() -> None:
    """A DPS product with aliases ['Denpasar Bali', 'Bali Denpasar'] should
    produce 'flights to Bali', 'flights to Denpasar Bali', 'flights to
    Bali Denpasar' — one keyword per (template, name-variant) combo."""
    p = Product(
        sku="DPS",
        name="Bali",
        aliases=["Denpasar Bali", "Bali Denpasar"],
    )
    kws = generate_keywords_for_product(
        p, ["flights to {name}", "{name} flights"],
        match_types=["PHRASE"],
    )
    texts = sorted(k.text for k in kws)
    assert "flights to Bali" in texts
    assert "flights to Denpasar Bali" in texts
    assert "flights to Bali Denpasar" in texts
    assert "Bali flights" in texts
    assert "Denpasar Bali flights" in texts
    assert "Bali Denpasar flights" in texts
    # 2 templates × 3 name variants = 6 unique keywords
    assert len(kws) == 6


def test_keyword_generator_does_not_duplicate_sku_only_templates() -> None:
    """Templates that don't reference {name} (e.g. '{sku} flights') should
    only render ONCE per product, even when the product has aliases."""
    p = Product(
        sku="DPS",
        name="Bali",
        aliases=["Denpasar Bali", "Bali Denpasar"],
    )
    kws = generate_keywords_for_product(
        p, ["{sku} flights", "flights to {name}"],
        match_types=["PHRASE"],
    )
    sku_kws = [k for k in kws if "DPS" in k.text]
    name_kws = [k for k in kws if "to " in k.text]
    assert len(sku_kws) == 1  # '{sku} flights' didn't multiply
    assert len(name_kws) == 3  # name template ×3 variants (name + 2 aliases)


def test_keyword_generator_dedupes_alias_that_matches_canonical_name() -> None:
    """A duplicate alias (same as canonical name, case-insensitively) is
    already filtered at load time, but defend against pathological direct
    callers: dedup at the keyword level too."""
    p = Product(
        sku="LHR",
        name="London Heathrow",
        aliases=["london heathrow", "London Heathrow", "LHR Airport"],
    )
    kws = generate_keywords_for_product(p, ["flights to {name}"])
    texts = [k.text for k in kws]
    # Case-insensitive dedup — only 2 unique keywords ('London Heathrow' and
    # 'LHR Airport' variants, lowercase dup of canonical eliminated).
    assert sorted({t.lower() for t in texts}) == [
        "flights to lhr airport", "flights to london heathrow",
    ]


def test_keyword_generator_no_aliases_behaves_like_v035() -> None:
    """For products without aliases (the majority of the etraveli catalog),
    behavior must be identical to the pre-v0.3.6 contract."""
    p = Product(sku="BKK", name="Bangkok", aliases=[])
    kws = generate_keywords_for_product(
        p, ["flights to {name}", "{name} flights", "{sku} flights"],
        match_types=["PHRASE", "EXACT"],
    )
    # 3 templates × 2 match types = 6 unique keywords (no alias expansion)
    assert len(kws) == 6
