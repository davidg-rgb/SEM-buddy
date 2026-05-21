"""Tests for URL templating (C4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.catalog.url_templating import (
    NCycler,
    UrlTemplateError,
    expand_for_products,
    expand_url_template,
)
from src.models.catalog import Product


def _p(sku: str = "BKK", name: str = "Bangkok", **attrs) -> Product:
    return Product(sku=sku, name=name, attributes=attrs)


def test_sku_substitution() -> None:
    p = _p()
    url = expand_url_template(
        "https://example.com/{sku}", p
    )
    assert url == "https://example.com/BKK"


def test_n_rotation_cycles() -> None:
    cycler = NCycler(1, 3)
    assert [cycler.next() for _ in range(7)] == [1, 2, 3, 1, 2, 3, 1]


def test_n_rotation_single_value() -> None:
    cycler = NCycler(2, 2)
    assert [cycler.next() for _ in range(3)] == [2, 2, 2]


def test_n_cycler_invalid_range() -> None:
    with pytest.raises(ValueError, match="low .* must be <= high"):
        NCycler(5, 3)


def test_attribute_substitution() -> None:
    p = _p(from_price=499, discount_pct=0.25)
    url = expand_url_template(
        "https://x.com/?p={from_price}&d={discount_pct}", p
    )
    assert url == "https://x.com/?p=499&d=0.25"


def test_n_placeholder() -> None:
    p = _p()
    url = expand_url_template("https://x.com/?to={sku}&text={N}", p, n=4)
    assert url == "https://x.com/?to=BKK&text=4"


def test_missing_attribute_raises() -> None:
    p = _p()
    with pytest.raises(UrlTemplateError, match="region"):
        expand_url_template("https://x.com/{region}", p)


def test_pydantic_httpurl_validates_expanded_url() -> None:
    from pydantic import HttpUrl, TypeAdapter

    p = _p()
    url = expand_url_template(
        "https://www.flightnetwork.com/from/google/rf/destination?to={sku}&text={N}",
        p, n=1,
    )
    # Should validate as HttpUrl
    adapter = TypeAdapter(HttpUrl)
    parsed = adapter.validate_python(url)
    assert str(parsed).startswith("https://www.flightnetwork.com/")


def test_expand_for_products_cycles_n() -> None:
    products = [_p(sku="A"), _p(sku="B"), _p(sku="C"), _p(sku="D")]
    urls = expand_for_products("p={sku}&n={N}", products, n_range=(1, 2))
    assert urls == ["p=A&n=1", "p=B&n=2", "p=C&n=1", "p=D&n=2"]


def test_template_with_no_placeholders() -> None:
    p = _p()
    assert expand_url_template("https://static.com/", p) == "https://static.com/"


def test_unicode_in_name_substitutes() -> None:
    p = _p(name="Göteborg")
    url = expand_url_template("https://x.com/?city={name}", p)
    assert "Göteborg" in url


def test_none_attribute_substitutes_empty() -> None:
    p = _p(from_price=None)
    url = expand_url_template("https://x.com/?p={from_price}", p)
    assert url == "https://x.com/?p="
