"""Nuvemshop JSON-LD product normalization."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from ..contracts import (
    ScrapedOfferInput,
    ScrapedProductInput,
    StockReading,
    VariantContext,
)
from .parsing import is_http_url, parse_positive_price

logger = logging.getLogger(__name__)

IN_STOCK_MARKER = "instock"


class NuvemshopNormalizer:
    """Normalize one JSON-LD product entry exposed by a listing page."""

    provider = "nuvemshop"

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize one item and keep malformed source data out of the crawl."""
        identifier = str(raw.get("sku") or "") if isinstance(raw, dict) else "<missing>"
        try:
            return self._normalize(
                raw,
                store_slug=store_slug,
                base_url=base_url,
                category=category,
            )
        except (
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            # Warning, not error: the run must survive one malformed item.
            logger.warning("Skipping malformed Nuvemshop item %s: %s", identifier, exc)
            return None

    def _normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize the one unit represented by a JSON-LD product entry."""
        _ = base_url
        sku = str(raw.get("sku") or "")
        if not sku:
            logger.debug("Skipping malformed Nuvemshop item without SKU")
            return None

        offer = self._offer(raw)
        price = parse_positive_price(offer.get("price"))
        if price is None:
            # Kept: dropping the unit leaves its previous price standing.
            logger.warning("Nuvemshop item %s has no usable price", sku)

        offer_url = str(offer.get("url") or raw.get("url") or "")
        page_url = offer_url.split("?", maxsplit=1)[0]
        if not is_http_url(offer_url) or not is_http_url(page_url):
            logger.warning("Skipping Nuvemshop item without valid URL: %s", sku)
            return None

        title = str(raw.get("name") or "")
        availability = str(offer.get("availability") or "").lower()
        is_available = IN_STOCK_MARKER in availability
        stock_quantity = self._stock_quantity(offer) if is_available else 0
        context = VariantContext(
            provider=self.provider,
            provider_product_id=sku,
            provider_variant_id=sku,
            title=title,
            options=[],
            selection=None,
        )
        return ScrapedProductInput(
            store_slug=store_slug,
            provider=self.provider,
            provider_product_id=sku,
            page_url=page_url,
            category=category,
            api_context=json.dumps(
                {"platform": self.provider, "product": raw},
                ensure_ascii=False,
            ),
            offers=[
                ScrapedOfferInput(
                    external_id=sku,
                    offer_url=offer_url,
                    name=title,
                    price=None if price is None else Decimal(str(price)),
                    stock_quantity=stock_quantity if price is not None else 0,
                    stock_status=(
                        StockReading.AVAILABLE
                        if is_available and price is not None
                        else StockReading.OUT_OF_STOCK
                    ),
                    ean=str(raw.get("gtin13") or ""),
                    sku=sku,
                    variant_context=context,
                ),
            ],
        )

    def _offer(self, item: dict[str, Any]) -> dict[str, Any]:
        """Return the first JSON-LD offer object."""
        offers = item.get("offers")
        if isinstance(offers, list):
            offers = next((offer for offer in offers if isinstance(offer, dict)), None)
        return offers if isinstance(offers, dict) else {}

    def _stock_quantity(self, offer: dict[str, Any]) -> int | None:
        """Read the advertised inventory level, when present."""
        level = offer.get("inventoryLevel")
        value = level.get("value") if isinstance(level, dict) else None
        if value is None:
            return None
        try:
            return int(float(value))
        except TypeError, ValueError:
            return None
