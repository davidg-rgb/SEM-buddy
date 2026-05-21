"""URL templating with round-robin {N} rotation.

Supports placeholders:
  - {sku} → product.sku
  - {name} → product.name
  - {any_attribute} → product.attributes[name]
  - {N} → 1..N counter that round-robins across products in a build

Unknown placeholders raise `KeyError`-derived `UrlTemplateError` so the caller
sees a clear failure rather than rendering empty values.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

from src.models.catalog import Product

logger = logging.getLogger(__name__)


PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class UrlTemplateError(KeyError):
    """Raised when a template references a placeholder that has no value."""


def expand_url_template(template: str, product: Product, n: int = 1) -> str:
    """Expand `{placeholder}` tokens in `template` against `product`.

    `n` provides the value for the special `{N}` placeholder.
    """
    def _lookup(name: str) -> str:
        if name == "N":
            return str(n)
        if name == "sku":
            return product.sku
        if name == "name":
            return product.name
        if name in product.attributes:
            val = product.attributes[name]
            return "" if val is None else str(val)
        raise UrlTemplateError(
            f"URL template references unknown placeholder '{{{name}}}' "
            f"for product sku={product.sku!r}; available attributes: "
            f"{list(product.attributes.keys())}"
        )

    def _sub(match: re.Match) -> str:
        return _lookup(match.group(1))

    return PLACEHOLDER_RE.sub(_sub, template)


class NCycler:
    """Round-robin counter for the {N} placeholder.

    >>> c = NCycler(1, 3)
    >>> [c.next() for _ in range(5)]
    [1, 2, 3, 1, 2]
    """

    def __init__(self, low: int, high: int) -> None:
        if low > high:
            raise ValueError(f"NCycler low ({low}) must be <= high ({high})")
        self.low = low
        self.high = high
        self._next = low

    def next(self) -> int:
        v = self._next
        nxt = v + 1
        self._next = self.low if nxt > self.high else nxt
        return v

    def __iter__(self) -> "NCycler":
        return self

    def __next__(self) -> int:
        return self.next()


def expand_for_products(
    template: str,
    products: Iterable[Product],
    n_range: tuple[int, int] = (1, 5),
) -> list[str]:
    """Convenience helper: expand `template` once per product with a shared
    `{N}` cycler. Returns the list of URLs in the same order as `products`.
    """
    cycler = NCycler(n_range[0], n_range[1])
    return [expand_url_template(template, p, n=cycler.next()) for p in products]


__all__ = [
    "UrlTemplateError",
    "expand_url_template",
    "NCycler",
    "expand_for_products",
]
