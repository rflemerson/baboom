"""VTEX product payload normalization shared by Search and GraphQL spiders."""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from ..contracts import (
    ScrapedOfferInput,
    ScrapedProductInput,
    StockReading,
    VariantContext,
    VariantOption,
    VariantSelection,
)
from .parsing import is_http_url, parse_optional_int, parse_positive_price

logger = logging.getLogger(__name__)


class VtexNormalizer:
    """Normalize one VTEX product into one offer per catalog SKU."""

    provider = "vtex"

    def __init__(self, *, context_platform: str = "vtex_legacy") -> None:
        """Keep the source-context envelope used by the calling VTEX API."""
        self.context_platform = context_platform

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize one VTEX product, skipping unusable SKUs individually."""
        product_id = str(raw.get("productId") or "")
        link_text = raw.get("linkText")
        page_url = f"{base_url}/{link_text}/p" if link_text else ""
        if not product_id or not is_http_url(page_url):
            logger.debug(
                "Skipping malformed VTEX product %s without id or valid URL",
                product_id or "<missing>",
            )
            return None

        product_name = str(raw.get("productName") or "")
        offers: list[ScrapedOfferInput] = []
        items = raw.get("items") or []
        if not isinstance(items, list):
            logger.debug("Skipping malformed VTEX product %s items", product_id)
            return None
        for sku in items:
            if not isinstance(sku, dict):
                logger.debug("Skipping malformed VTEX item for product %s", product_id)
                continue
            try:
                offer = self._normalize_sku(
                    sku,
                    product_id=product_id,
                    product_name=product_name,
                    page_url=page_url,
                )
            except (
                AttributeError,
                KeyError,
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                logger.debug(
                    "Skipping malformed VTEX item %s for product %s: %s",
                    sku.get("itemId") or "<missing>",
                    product_id,
                    exc,
                )
                offer = None
            if offer is not None:
                offers.append(offer)

        if not offers:
            return None

        return ScrapedProductInput(
            store_slug=store_slug,
            provider=self.provider,
            provider_product_id=product_id,
            page_url=page_url,
            category=category,
            api_context=self._build_product_context(raw),
            offers=offers,
            complete_unit_list=len(offers) == len(items),
        )

    def _normalize_sku(
        self,
        sku: dict,
        *,
        product_id: str,
        product_name: str,
        page_url: str,
    ) -> ScrapedOfferInput | None:
        """Normalize one SKU, returning None for malformed unit data."""
        item_id = str(sku.get("itemId") or "")
        seller = self._select_seller(sku)
        if not item_id:
            logger.debug("Skipping malformed VTEX item without itemId")
            return None
        if seller is None:
            logger.debug("Skipping VTEX item %s without seller", item_id)
            return None

        commercial = seller.get("commertialOffer") or {}
        if not isinstance(commercial, dict):
            logger.debug("Skipping malformed VTEX item %s commercial offer", item_id)
            return None
        price = parse_positive_price(commercial.get("Price"))
        if price is None:
            # An unavailable VTEX SKU commonly reports price zero. Dropping it
            # would leave the previous price standing as if still on sale.
            logger.warning("VTEX item %s has no usable price", item_id)
        stock_quantity = parse_optional_int(commercial.get("AvailableQuantity"))
        sku_name = str(sku.get("nameComplete") or sku.get("name") or "")
        return ScrapedOfferInput(
            external_id=item_id,
            offer_url=f"{page_url}?skuId={item_id}",
            name=sku_name or product_name,
            price=None if price is None else Decimal(str(price)),
            stock_quantity=stock_quantity if price is not None else 0,
            stock_status=(
                StockReading.AVAILABLE
                if price is not None and (stock_quantity is None or stock_quantity > 0)
                else StockReading.OUT_OF_STOCK
            ),
            sku=item_id,
            ean=str(sku.get("ean") or ""),
            variant_context=VariantContext(
                provider=self.provider,
                provider_product_id=product_id,
                provider_variant_id=item_id,
                title=str(sku.get("name") or ""),
                options=self._sku_options(sku),
                selection=VariantSelection(
                    kind="query_parameter",
                    parameters={"skuId": item_id},
                ),
            ),
        )

    def _select_seller(self, sku: dict) -> dict | None:
        """Select the default seller, falling back to the first seller."""
        sellers = sku.get("sellers") or []
        if not isinstance(sellers, list) or not sellers:
            return None
        for seller in sellers:
            if isinstance(seller, dict) and seller.get("sellerDefault"):
                return seller
        first = sellers[0]
        return first if isinstance(first, dict) else None

    def _sku_options(self, sku: dict) -> list[VariantOption]:
        """Read VTEX variations in the order published by the SKU."""
        options: list[VariantOption] = []
        variations = sku.get("variations") or []
        if not isinstance(variations, list):
            return options
        for name in variations:
            values = sku.get(str(name)) or []
            if isinstance(values, list) and values:
                options.append(
                    VariantOption(name=str(name), value=str(values[0])),
                )
        return options

    def _build_product_context(self, item: dict) -> str:
        """Build the source context envelope for either VTEX API."""
        if self.context_platform == "vtex_graphql":
            product = {
                "productId": item.get("productId"),
                "productName": item.get("productName"),
                "brand": item.get("brand"),
                "linkText": item.get("linkText"),
                "clusterHighlights": item.get("clusterHighlights") or {},
            }
        else:
            product = {
                "productId": item.get("productId"),
                "productName": item.get("productName"),
                "brand": item.get("brand"),
                "linkText": item.get("linkText"),
                "categories": item.get("categories") or [],
                "categoryId": item.get("categoryId"),
            }
        payload = {
            "platform": self.context_platform,
            "product": product,
            "items": item.get("items") or [],
        }
        return json.dumps(payload, ensure_ascii=False)
