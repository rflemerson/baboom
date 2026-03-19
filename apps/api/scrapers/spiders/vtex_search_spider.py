"""Base spider for VTEX legacy search APIs."""

from __future__ import annotations

import json
import logging

from ..models import ScrapedItem
from ..services import ScraperService
from ..types import ProductIngestionInput
from .catalog_api_spider import CatalogApiSpider
from .common import (
    is_http_url,
    parse_optional_int,
    parse_positive_price,
    persist_json_context,
)

logger = logging.getLogger(__name__)

VTEX_CATEGORY_TREE_SUCCESS_CODE = 200
VTEX_SUCCESS_CODES = (VTEX_CATEGORY_TREE_SUCCESS_CODE, 206)
VTEX_PAGE_SIZE = 50
VTEX_ITEM_PROCESSING_EXCEPTIONS = (
    KeyError,
    TypeError,
    ValueError,
)


class VtexSearchSpider(CatalogApiSpider):
    """Base Spider for VTEX Legacy / Search API stores."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    API_TREE = ""

    FALLBACK_CATEGORIES: tuple[str, ...] = ()

    def _initial_cursor(self) -> int:
        """Return initial offset for pagination."""
        return 0

    def _next_cursor(self, cursor: int, page_size: int) -> int:
        """Advance VTEX search offset cursor."""
        return cursor + page_size

    def _fetch_categories(self) -> list[str]:
        """Fetch category slugs from the VTEX category tree."""
        try:
            resp = self._request_get(self.API_TREE, timeout=10)
            if resp is None:
                return []
            if resp.status_code != VTEX_CATEGORY_TREE_SUCCESS_CODE:
                logger.warning("Failed to fetch category tree: %s", resp.status_code)
                return []

            tree = resp.json()
            slugs = set()

            def extract_slugs(nodes: list[dict]) -> None:
                for node in nodes:
                    url = node.get("url", "")
                    if url:
                        url = url.rstrip("/")
                        slug = url.split("/")[-1]
                        if slug:
                            slugs.add(slug)

                    if "children" in node:
                        extract_slugs(node["children"])

            extract_slugs(tree)
            return list(slugs)

        except Exception:
            logger.exception("Error fetching categories")
            return []

    def _build_search_url(self, category_slug: str) -> str:
        """Build category endpoint URL."""
        return f"{self.BASE_URL}/api/catalog_system/pub/products/search/{category_slug}"

    def _build_pagination_params(self, start: int, step: int) -> dict[str, int]:
        """Build VTEX range params for one page."""
        end = start + step - 1
        return {"_from": start, "_to": end}

    def _fetch_page_items(
        self,
        category_slug: str,
        start: int,
        step: int,
    ) -> list[dict] | None:
        """Fetch one page and normalize response contract."""
        search_url = self._build_search_url(category_slug)
        params = self._build_pagination_params(start, step)
        response = self._request_get(search_url, params=params, timeout=30)
        if response is None:
            return None
        if response.status_code not in VTEX_SUCCESS_CODES:
            return None

        data = response.json()
        if not data or not isinstance(data, list):
            return []
        return data

    def _crawl_category(
        self,
        category_slug: str,
        processed_ids: set[str],
    ) -> list[object]:
        """Crawl one VTEX category with offset pagination."""
        logger.info("Crawling Category: %s", category_slug)
        products: list[object] = []
        start = self._initial_cursor()
        step = VTEX_PAGE_SIZE

        while True:
            try:
                data = self._fetch_page_items(category_slug, start, step)
                if data is None or not data:
                    break

                for item in data:
                    try:
                        item_id = str(item.get("productId"))
                        if item_id in processed_ids:
                            continue

                        processed_ids.add(item_id)
                        saved_obj = self._process_and_save(item, category_slug)
                        if saved_obj:
                            products.append(saved_obj)
                    except VTEX_ITEM_PROCESSING_EXCEPTIONS as exc:
                        logger.debug("Skipping item: %s", exc)

                if len(data) < step:
                    break

                start = self._next_cursor(start, step)
                self.sleep_random(0.5, 1.0)

            except Exception:
                logger.exception("Error crawling %s", category_slug)
                break

        return products

    def _process_and_save(
        self,
        item: dict[str, object],
        category: str,
    ) -> object | None:
        try:
            skus = item.get("items", [])
            first_sku = self._extract_first_sku(skus) if skus else None
            active_seller = self._select_active_seller(first_sku) if first_sku else None
            comm_offer = (
                active_seller.get("commertialOffer", {}) if active_seller else {}
            )
            price = self._parse_price(comm_offer.get("Price"))

            pid = item.get("productId")
            name = item.get("productName")
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            if first_sku is None or active_seller is None or price is None:
                return None
            if not is_http_url(url):
                return None

            ean = first_sku.get("ean", "")
            sku_code = first_sku.get("itemId", "")

            stock_quantity = self._parse_stock(comm_offer.get("AvailableQuantity"))
            stock_status = (
                ScrapedItem.StockStatus.AVAILABLE
                if stock_quantity is None or stock_quantity > 0
                else ScrapedItem.StockStatus.OUT_OF_STOCK
            )

            store_slug = self.STORE_SLUG or self.BRAND_NAME.lower().replace(" ", "_")
            input_data = ProductIngestionInput(
                store_slug=store_slug,
                external_id=str(pid),
                url=url,
                name=str(name) if name else "",
                price=price,
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean=str(ean),
                sku=str(sku_code),
                pid=str(pid),
                category=category,
            )
            saved = ScraperService.save_product(input_data)
            persist_json_context(saved, self._build_product_context(item))
        except VTEX_ITEM_PROCESSING_EXCEPTIONS as exc:
            logger.debug("Item parse error: %s", exc)
            return None

        return saved

    def _extract_first_sku(self, skus: list[dict]) -> dict | None:
        """Find the first valid SKU with a default seller."""
        for sku_chem in skus:
            sellers_chem = sku_chem.get("sellers", [])
            for seller in sellers_chem:
                if seller.get("sellerDefault"):
                    return sku_chem
        return skus[0] if skus else None

    def _select_active_seller(self, sku: dict) -> dict | None:
        """Select the active seller for the SKU."""
        sellers = sku.get("sellers", [])
        for seller in sellers:
            if seller.get("sellerDefault"):
                return seller
        return sellers[0] if sellers else None

    def _parse_stock(self, quantity: object) -> int | None:
        """Parse stock quantity to integer."""
        return parse_optional_int(quantity)

    def _parse_price(self, raw_price: object) -> float | None:
        return parse_positive_price(raw_price)

    def parse_price(self, raw_price: object) -> float | None:
        """Expose VTEX price normalization for reuse and tests."""
        return self._parse_price(raw_price)

    def _build_product_context(self, item: dict) -> str:
        """Build structured VTEX context for downstream agents."""
        payload = {
            "platform": "vtex_legacy",
            "product": {
                "productId": item.get("productId"),
                "productName": item.get("productName"),
                "brand": item.get("brand"),
                "linkText": item.get("linkText"),
                "categories": item.get("categories") or [],
                "categoryId": item.get("categoryId"),
            },
            "items": item.get("items") or [],
        }
        return json.dumps(payload, ensure_ascii=False)

    def process_item(
        self,
        item: dict[str, object],
        category: str,
    ) -> object | None:
        """Normalize and persist one VTEX search product."""
        return self._process_and_save(item, category)
