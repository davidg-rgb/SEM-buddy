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
