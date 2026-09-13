"""Shopify product payload normalization."""

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
from .parsing import is_http_url, parse_positive_price

logger = logging.getLogger(__name__)


class ShopifyNormalizer:
    """Normalize Shopify products into one offer per variant."""

    provider = "shopify"

    def __init__(
        self,
        *,
        price_int_is_cents: bool = False,
        price_digit_str_is_cents: bool = False,
        default_variant_title: str = "Default Title",
    ) -> None:
        """Configure price units for the Shopify endpoint in use."""
        self.price_int_is_cents = price_int_is_cents
        self.price_digit_str_is_cents = price_digit_str_is_cents
        self.default_variant_title = default_variant_title

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize one Shopify product, or skip it when no variant is usable."""
        product_id = str(raw.get("id") or "")
        handle = str(raw.get("handle") or "")
        if not product_id or not handle:
            logger.debug(
                "Skipping malformed Shopify product %s without id or handle",
                product_id or "<missing>",
            )
            return None

        page_url = f"{base_url}/products/{handle}"
        if not is_http_url(page_url):
            logger.debug(
                "Skipping malformed Shopify product %s with invalid URL",
                product_id,
            )
            return None

        product_title = str(raw.get("title") or "")
        option_names = self._option_names(raw)
        offers: list[ScrapedOfferInput] = []
        variants = raw.get("variants") or []
        if not isinstance(variants, list):
            logger.debug("Skipping malformed Shopify product %s variants", product_id)
            return None

        for variant in variants:
            if not isinstance(variant, dict):
                logger.debug(
                    "Skipping malformed Shopify variant for product %s",
                    product_id,
                )
                continue
            try:
                offer = self._normalize_variant(
                    variant,
                    product_id=product_id,
                    product_title=product_title,
                    option_names=option_names,
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
                    "Skipping malformed Shopify variant %s for product %s: %s",
                    variant.get("id") or "<missing>",
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
            complete_unit_list=len(offers) == len(variants),
        )

    def _normalize_variant(
        self,
        variant: dict,
        *,
        product_id: str,
        product_title: str,
        option_names: list[str],
        page_url: str,
    ) -> ScrapedOfferInput | None:
        """Normalize one Shopify variant without letting bad data abort peers."""
        variant_id = str(variant.get("id") or "")
        price = self.parse_price(variant.get("price"))
        if not variant_id:
            logger.warning(
                "Skipping Shopify variant without id for product %s",
                product_id,
            )
            return None
        if price is None:
            # Kept, not dropped: dropping leaves yesterday's price standing as
            # if it were still on sale. A unit without a price is not for sale.
            logger.warning(
                "Shopify variant %s of product %s has no usable price",
                variant_id,
                product_id,
            )

        is_available = bool(variant.get("available")) and price is not None
        try:
            quantity = variant.get("inventory_quantity")
            stock_quantity = int(quantity) if quantity is not None else None
        except TypeError, ValueError:
            stock_quantity = None
        if not is_available:
            stock_quantity = 0

        variant_title = str(variant.get("title") or "")
        name = (
            f"{product_title} - {variant_title}"
            if variant_title and variant_title != self.default_variant_title
            else product_title
        )
        return ScrapedOfferInput(
            external_id=variant_id,
            offer_url=f"{page_url}?variant={variant_id}",
            name=name,
            price=None if price is None else Decimal(str(price)),
            stock_quantity=stock_quantity,
            stock_status=(
                StockReading.AVAILABLE if is_available else StockReading.OUT_OF_STOCK
            ),
            sku=str(variant.get("sku") or ""),
            ean=str(variant.get("barcode") or ""),
            variant_context=VariantContext(
                provider=self.provider,
                provider_product_id=product_id,
                provider_variant_id=variant_id,
                title=variant_title,
                options=self._variant_options(variant, option_names),
                selection=VariantSelection(
                    kind="query_parameter",
                    parameters={"variant": variant_id},
                ),
            ),
        )

    def _option_names(self, product: dict) -> list[str]:
        """Read Shopify option names in the order published by the product."""
        options = product.get("options") or []
        if not isinstance(options, list):
            return []
        return [
            str(option.get("name") or "")
            for option in options
            if isinstance(option, dict)
        ]

    def _variant_options(
        self,
        variant: dict,
        option_names: list[str],
    ) -> list[VariantOption]:
        """Pair Shopify option names and values positionally."""
        options: list[VariantOption] = []
        for index, name in enumerate(option_names[:3], start=1):
            value = variant.get(f"option{index}")
            if name and value:
                options.append(VariantOption(name=name, value=str(value)))
        return options

    def parse_price(self, raw_price: object) -> float | None:
        """Parse the price format used by this Shopify endpoint."""
        return parse_positive_price(
            raw_price,
            cents_for_int=self.price_int_is_cents,
            cents_for_digit_string=self.price_digit_str_is_cents,
        )

    def _build_product_context(self, item: dict) -> str:
        """Build the structured source context used by the current spider."""
        payload = {
            "platform": self.provider,
            "product": {
                "id": item.get("id"),
                "title": item.get("title"),
                "handle": item.get("handle"),
                "vendor": item.get("vendor"),
                "type": item.get("type") or item.get("product_type"),
                "tags": item.get("tags"),
            },
            "options": item.get("options") or [],
            "variants": item.get("variants") or [],
            "images": item.get("images") or [],
        }
        return json.dumps(payload, ensure_ascii=False)
