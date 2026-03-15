"""Template Method base for Shopify API scrapers."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..models import ScrapedItem
from ..services import ScraperService
from ..types import ProductIngestionInput
from .catalog_api_spider import CatalogApiSpider
from .common import parse_positive_price, persist_json_context

logger = logging.getLogger(__name__)


class ShopifyApiSpider(CatalogApiSpider):
    """Template spider for Shopify public API stores."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""

    FALLBACK_CATEGORIES: list[str] = []
    USE_PRODUCT_DETAIL = False
    PRICE_INT_IS_CENTS = False
    PRICE_DIGIT_STR_IS_CENTS = False

    def get_headers(self) -> dict[str, str]:
        """Get API headers."""
        return {
            "User-Agent": self.user_agents[0],
            "Accept": "application/json",
        }

    def _collections_endpoint(self) -> str:
        return f"{self.BASE_URL}/collections.json"

    def _initial_cursor(self) -> int:
        """Return initial page cursor for category pagination."""
        return 1

    def _next_cursor(self, cursor: int, page_size: int) -> int:
        """Advance Shopify page cursor."""
        _ = page_size
        return cursor + 1

    def _fetch_categories(self) -> list[str]:
        """Fetch category handles from Shopify collections API."""
        logger.info(f"Fetching categories for {self.BRAND_NAME} (Shopify)...")
        handles: set[str] = set()
        page = 1
        limit = 250
        endpoint = self._collections_endpoint()

        try:
            while True:
                response = self._request_get(
                    endpoint,
                    params={"page": page, "limit": limit},
                    timeout=20,
                )
                if response is None:
                    break
                if response.status_code != 200:
                    logger.warning(
                        f"Failed to fetch collections page {page}: {response.status_code}"
                    )
                    break

                payload = response.json()
                collections = payload.get("collections") or []
                if not collections:
                    break

                for collection in collections:
                    if not isinstance(collection, dict):
                        continue
                    handle = collection.get("handle")
                    if handle:
                        handles.add(str(handle))

                if len(collections) < limit:
                    break
                page += 1
                self.sleep_random(0.3, 0.8)

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")

        return list(handles)

    def _fetch_product_detail(self, handle: str) -> dict | None:
        """Fetch one product detail JSON by Shopify handle."""
        try:
            response = self._request_get(
                f"{self.BASE_URL}/products/{handle}.js",
                timeout=20,
            )
            if response is None:
                return None
            if response.status_code != 200:
                return None
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _resolve_source_product(self, listing_product: dict) -> dict:
        """Strategy hook: choose listing payload or detail payload as source."""
        if not self.USE_PRODUCT_DETAIL:
            return listing_product

        handle = str(listing_product.get("handle") or "")
        if not handle:
            return listing_product
        detail = self._fetch_product_detail(handle)
        return detail if detail else listing_product

    def _crawl_category(
        self, category_handle: str, processed_ids: set[str]
    ) -> list[Any]:
        """Crawl one Shopify collection and save products."""
        logger.info(f"Crawling category: {category_handle}")
        products: list[Any] = []
        page = self._initial_cursor()
        limit = 250

        while True:
            try:
                page_products = self._fetch_page_items(category_handle, page, limit)
                if page_products is None or not page_products:
                    break

                for product in page_products:
                    if not isinstance(product, dict):
                        continue
                    product_id = str(product.get("id") or "")
                    if not product_id or product_id in processed_ids:
                        continue
                    processed_ids.add(product_id)

                    source_item = self._resolve_source_product(product)
                    saved = self._process_and_save(source_item, category_handle)
                    if saved:
                        products.append(saved)

                if len(page_products) < limit:
                    break

                page = self._next_cursor(page, limit)
                self.sleep_random(0.4, 1.0)

            except Exception as e:
                logger.error(f"Error crawling {category_handle}: {e}")
                break

        return products

    def _fetch_page_items(
        self, category_handle: str, cursor: int, page_size: int
    ) -> list[dict] | None:
        """Fetch one Shopify collection page."""
        endpoint = f"{self.BASE_URL}/collections/{category_handle}/products.json"
        response = self._request_get(
            endpoint,
            params={"page": cursor, "limit": page_size},
            timeout=30,
        )
        if response is None:
            return None
        if response.status_code != 200:
            logger.warning(
                f"Failed category {category_handle} page {cursor}: {response.status_code}"
            )
            return None
        payload = response.json()
        products = payload.get("products") or []
        return products if isinstance(products, list) else []

    def _parse_price(self, raw_price: Any) -> float | None:
        return parse_positive_price(
            raw_price,
            cents_for_int=self.PRICE_INT_IS_CENTS,
            cents_for_digit_string=self.PRICE_DIGIT_STR_IS_CENTS,
        )

    def _select_variant(self, variants: list[Any]) -> dict | None:
        """Select first available variant, fallback to first."""
        if not variants:
            return None
        selected = variants[0]
        for variant in variants:
            if isinstance(variant, dict) and variant.get("available"):
                selected = variant
                break
        return selected if isinstance(selected, dict) else None

    def _process_and_save(self, data: dict, category_name: str) -> Any | None:
        """Normalize one Shopify product and persist."""
        try:
            pid = str(data.get("id") or "")
            handle = str(data.get("handle") or "")
            if not pid or not handle:
                return None

            name = data.get("title")
            url = f"{self.BASE_URL}/products/{handle}"
            variants = data.get("variants") or []
            selected_variant = self._select_variant(variants)
            if not selected_variant:
                return None

            parsed_price = self._parse_price(selected_variant.get("price"))
            if parsed_price is None:
                logger.warning(f"Skipping Shopify item without valid price: {pid}")
                return None

            is_available = bool(selected_variant.get("available"))
            inventory_quantity = selected_variant.get("inventory_quantity")
            try:
                stock_quantity = (
                    int(inventory_quantity) if inventory_quantity is not None else 0
                )
            except (TypeError, ValueError):
                stock_quantity = 0

            stock_status = (
                ScrapedItem.StockStatus.AVAILABLE
                if is_available
                else ScrapedItem.StockStatus.OUT_OF_STOCK
            )
            if not is_available:
                stock_quantity = 0

            sku = str(selected_variant.get("id") or selected_variant.get("sku") or "")
            ean = str(selected_variant.get("barcode") or "")

            input_data = ProductIngestionInput(
                store_slug=self.STORE_SLUG,
                external_id=pid,
                url=url,
                name=str(name) if name else "",
                price=parsed_price,
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean=ean,
                sku=sku,
                pid=pid,
                category=category_name,
            )
            saved = ScraperService.save_product(input_data)
            persist_json_context(saved, self._build_product_context(data))
            return saved

        except Exception as e:
            logger.error(f"Error processing item {data.get('id')}: {e}")
            return None

    def _build_product_context(self, item: dict) -> str:
        """Build structured context for downstream agents."""
        payload = {
            "platform": "shopify",
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
