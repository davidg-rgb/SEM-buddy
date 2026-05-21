"""Promotion Extension generator — one per catalog row with a non-zero discount.

Each `Product` becomes a `PromotionExtension` pointing at its ad group, with
percent-off pulled from the configured attribute (typically `discount_pct`).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Iterable

from src.catalog.url_templating import NCycler, expand_url_template
from src.models.campaign import PromotionExtension
from src.models.catalog import Product

logger = logging.getLogger(__name__)


def _coerce_percent(raw: float | int | None) -> float | None:
    """Normalize a discount value into a 0–100 percent.

    The canonical case stores discounts as fractions (0.0–1.0). We accept
    either form and emit a sane percent. Values outside [0, 100] (after
    fractional expansion) are clipped + logged.
    """
    if raw is None:
        return None
    val = float(raw)
    if 0.0 < val <= 1.0:
        val = val * 100.0
    if val < 0:
        logger.warning("Negative discount %s clipped to 0", raw)
        return 0.0
    if val > 100:
        logger.warning("Discount %s exceeds 100%%; clipping", raw)
        return 100.0
    return round(val, 2)


def generate_promotions_from_products(
    products: Iterable[Product],
    campaign_name: str,
    url_template: str,
    *,
    discount_attribute: str = "discount_pct",
    ad_group_name_template: str = "{name} ({sku})",
    language: str = "en",
    start_date: date | None = None,
    end_date: date | None = None,
    occasion: str | None = None,
    money_currency: str = "SEK",
    text_n_range: tuple[int, int] = (1, 5),
) -> list[PromotionExtension]:
    """Emit a PromotionExtension per product with a positive discount."""
    promotions: list[PromotionExtension] = []
    cycler = NCycler(text_n_range[0], text_n_range[1])

    for product in products:
        raw_discount = product.attributes.get(discount_attribute)
        pct = _coerce_percent(raw_discount)
        n = cycler.next()
        if pct is None or pct <= 0:
            continue  # skip products with no/zero discount
        ad_group_name = ad_group_name_template.format(name=product.name, sku=product.sku)
        final_url = expand_url_template(url_template, product, n=n)
        promotions.append(
            PromotionExtension(
                campaign_name=campaign_name,
                ad_group_name=ad_group_name,
                discount_modifier="UP_TO",
                percent_off=pct,
                money_currency=money_currency,
                start_date=start_date,
                end_date=end_date,
                final_url=final_url,
                language=language,
                occasion=occasion,
            )
        )
    logger.info(
        "Generated %d promotion extensions (campaign='%s')",
        len(promotions), campaign_name,
    )
    return promotions


__all__ = ["generate_promotions_from_products"]
