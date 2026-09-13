"""Wap.Store product payload normalization."""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from ..contracts import (
    ScrapedOfferInput,
    ScrapedProductInput,
    StockReading,
    VariantContext,
)
from .parsing import is_http_url, parse_optional_int, parse_positive_price

logger = logging.getLogger(__name__)


class WapStoreNormalizer:
    """Normalize one Wap.Store listing item."""

    provider = "wapstore"

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize one Wap.Store unit, or skip unusable source data."""
        external_id = str(raw.get("id") or "")
        name_value = raw.get("nome") or raw.get("name")
        if not external_id or not name_value:
            logger.debug(
                "Skipping malformed Wap.Store item %s without id or name",
                external_id or "<missing>",
            )
            return None
        name = str(name_value)
        sku = str(raw.get("sku") or "")
        page_url = self._build_product_url(raw, base_url)
        if not is_http_url(page_url):
            logger.warning(
                "Skipping Wap.Store item without valid URL: %s",
                external_id,
            )
            return None

        price = parse_positive_price(self._extract_raw_price(raw))
        if price is None:
            # Kept: dropping the unit leaves its previous price standing.
            logger.warning("Wap.Store item %s has no usable price", external_id)
        stock_quantity = parse_optional_int(
            raw.get("estoque") or raw.get("balance"),
        )
        ean = raw.get("ean") or raw.get("gtin") or ""
        return ScrapedProductInput(
            store_slug=store_slug,
            provider=self.provider,
            provider_product_id=external_id,
            page_url=page_url,
            category=category,
            api_context=self._build_product_context(raw),
            offers=[
                ScrapedOfferInput(
                    external_id=external_id,
                    offer_url=page_url,
                    name=name,
                    price=None if price is None else Decimal(str(price)),
                    stock_quantity=stock_quantity if price is not None else 0,
                    stock_status=self._resolve_stock_status(stock_quantity, price),
                    ean=str(ean),
                    sku=sku,
                    variant_context=VariantContext(
                        provider=self.provider,
                        provider_product_id=external_id,
                        provider_variant_id=sku or external_id,
                        title=name,
                        options=[],
                        selection=None,
                    ),
                ),
            ],
        )

    def _build_product_url(self, item: dict, base_url: str) -> str:
        """Build the canonical product URL from a listing item."""
        link_slug = item.get("link") or item.get("slug") or item.get("url")
        if not link_slug:
            return ""
        value = str(link_slug)
        if value.startswith("http"):
            return value
        return f"{base_url}/{value.lstrip('/')}"

    def _extract_raw_price(self, item: dict) -> object:
        """Extract the price token used by the Wap.Store payload."""
        prices = item.get("precos")
        if isinstance(prices, dict):
            return prices.get("por") or prices.get("vista")
        return item.get("price")

    def _resolve_stock_status(
        self,
        stock_quantity: int | None,
        price: float | None,
    ) -> StockReading:
        """Treat absent/positive stock as available, but never a unit with no price."""
        if price is not None and (stock_quantity is None or stock_quantity > 0):
            return StockReading.AVAILABLE
        return StockReading.OUT_OF_STOCK

    def _build_product_context(self, item: dict) -> str:
        """Build the structured source context used by the current spider."""
        payload = {
            "platform": self.provider,
            "product": {
                "id": item.get("id"),
                "name": item.get("nome") or item.get("name"),
                "slug": item.get("slug"),
                "url": item.get("url") or item.get("link"),
                "sku": item.get("sku"),
                "ean": item.get("ean") or item.get("gtin"),
                "prices": item.get("precos") or {},
                "stock_raw": item.get("estoque") or item.get("balance"),
            },
        }
        return json.dumps(payload, ensure_ascii=False)
