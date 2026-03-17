import base64
import json
import logging
from typing import Any

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


class VtexGraphqlSpider(CatalogApiSpider):
    """Template spider for VTEX GraphQL stores."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    API_ENDPOINT = ""
    API_TREE = ""
    QUERY_HASH = ""

    FALLBACK_CATEGORIES: list[str] = []

    def _initial_cursor(self) -> int:
        """Return initial offset for pagination."""
        return 0

    def _next_cursor(self, cursor: int, page_size: int) -> int:
        """Advance VTEX GraphQL offset cursor."""
        return cursor + page_size

    def _fetch_categories(self) -> list[str]:
        try:
            logger.info(f"Fetching categories for {self.BRAND_NAME}...")
            response = self._request_get(self.API_TREE, timeout=10)
            if response is None:
                return []
            if response.status_code != 200:
                logger.error(f"Failed to fetch categories: {response.status_code}")
                return []

            categories = []
            for item in response.json():
                if item.get("hasChildren") or item.get("url"):
                    url = item.get("url", "")
                    slug = url.split("/")[-1] if url else ""
                    if slug:
                        categories.append(slug)

            return categories

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def _crawl_category(self, category: str, processed_ids: set[str]) -> list[Any]:
        """Crawl one category with GraphQL pagination."""
        logger.info(f"Crawling Category: {category}")
        products = []
        start = self._initial_cursor()
        step = 50

        while True:
            items = self._fetch_page_items(category, start, step)
            if items is None or not items:
                break

            for item in items:
                try:
                    item_id = str(item.get("productId"))
                    if item_id in processed_ids:
                        continue

                    processed_ids.add(item_id)
                    saved_obj = self._process_and_save(item, category)
                    if saved_obj:
                        products.append(saved_obj)
                except Exception as e:
                    logger.debug(f"Skipping item: {e}")

            if len(items) < step:
                break

            start = self._next_cursor(start, step)
            self.sleep_random(0.5, 1.5)

        return products

    def _fetch_page_items(
        self,
        category: str,
        cursor: int,
        page_size: int,
    ) -> list[dict] | None:
        """Fetch and parse one GraphQL page into product items."""
        end = cursor + page_size - 1
        data = self._fetch_graphql_data(category, cursor, end)
        if not data:
            return None
        return self._parse_graphql_response(data)

    def _build_variables_payload(self, category: str, start: int, end: int) -> dict:
        """Build VTEX search variables payload."""
        return {
            "hideUnavailableItems": False,
            "category": category,
            "specificationFilters": [],
            "orderBy": "OrderByScoreDESC",
            "from": start,
            "to": end,
            "shippingOptions": [],
            "variant": "",
            "advertisementOptions": {
                "showSponsored": False,
                "sponsoredCount": 0,
                "repeatSponsoredProducts": False,
                "advertisementPlacement": "home_shelf",
            },
        }

    def _build_graphql_params(
        self,
        category: str,
        start: int,
        end: int,
    ) -> dict[str, str]:
        """Build GraphQL persisted-query params."""
        variables_dict = self._build_variables_payload(category, start, end)
        vars_json = json.dumps(variables_dict, separators=(",", ":"))
        vars_b64 = base64.b64encode(vars_json.encode("utf-8")).decode("utf-8")

        extensions_dict = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": self.QUERY_HASH,
                "sender": "vtex.store-resources@0.x",
                "provider": "vtex.search-graphql@0.x",
            },
            "variables": vars_b64,
        }
        extensions_json = json.dumps(extensions_dict, separators=(",", ":"))
        return {
            "workspace": "master",
            "maxAge": "short",
            "appsEtag": "remove",
            "domain": "store",
            "locale": "pt-BR",
            "operationName": "Products",
            "variables": "{}",
            "extensions": extensions_json,
        }

    def _fetch_graphql_data(self, category: str, start: int, end: int) -> dict | None:
        """Execute GraphQL query for one page."""
        params = self._build_graphql_params(category, start, end)

        try:
            response = self._request_get(self.API_ENDPOINT, params=params, timeout=30)
            if response is None:
                return None

            if response.status_code != 200:
                logger.error(f"GraphQL Error: {response.text[:200]}")
                return None

            data = response.json()
            if "errors" in data:
                logger.error(f"GraphQL Body Errors: {data['errors']}")
                return None

            return data
        except Exception as e:
            logger.error(f"Crawl error for {category}: {e}")
            return None

    def _parse_graphql_response(self, data: dict) -> list[dict]:
        """Extract product list from GraphQL response."""
        products_list = []
        p_search = data.get("data", {}).get("productSearch")
        if p_search and isinstance(p_search, dict):
            products_list = p_search.get("products", [])

        if not products_list:
            p_direct = data.get("data", {}).get("products")
            if isinstance(p_direct, list):
                products_list = p_direct
            elif isinstance(p_direct, dict):
                products_list = p_direct.get("products", [])

        return products_list

    def _process_and_save(self, item: dict, category_name: str) -> Any | None:
        """Normalize and persist one VTEX GraphQL product."""
        try:
            pid = item.get("productId")
            name = item.get("productName")
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            items_list = item.get("items", [])
            if not items_list:
                return None

            first_sku = items_list[0]
            sellers = first_sku.get("sellers", [])
            active_seller = None
            if sellers:
                active_seller = sellers[0]
                for seller in sellers:
                    if seller.get("sellerDefault"):
                        active_seller = seller
                        break

            if not active_seller:
                return None

            comm_offer = active_seller.get("commertialOffer", {})
            price = self._parse_price(comm_offer.get("Price"))
            if price is None:
                return None

            stock_quantity = self._parse_stock(comm_offer.get("AvailableQuantity"))
            stock_status = (
                ScrapedItem.StockStatus.AVAILABLE
                if stock_quantity is None or stock_quantity > 0
                else ScrapedItem.StockStatus.OUT_OF_STOCK
            )

            if not is_http_url(url):
                return None

            ean = first_sku.get("ean", "")
            sku = first_sku.get("itemId", "")
            input_data = ProductIngestionInput(
                store_slug=self.STORE_SLUG,
                external_id=str(pid),
                url=url,
                name=str(name) if name else "",
                price=price,
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean=str(ean),
                sku=str(sku),
                pid=str(pid),
                category=category_name,
            )
            saved = ScraperService.save_product(input_data)
            persist_json_context(saved, self._build_product_context(item))
            return saved

        except Exception as e:
            logger.debug(f"Item parse error: {e}")
            return None

    def _parse_stock(self, quantity: Any) -> int | None:
        return parse_optional_int(quantity)

    def _parse_price(self, raw_price: Any) -> float | None:
        return parse_positive_price(raw_price)

    def _build_product_context(self, item: dict) -> str:
        """Build structured VTEX GraphQL context for downstream agents."""
        payload = {
            "platform": "vtex_graphql",
            "product": {
                "productId": item.get("productId"),
                "productName": item.get("productName"),
                "brand": item.get("brand"),
                "linkText": item.get("linkText"),
                "clusterHighlights": item.get("clusterHighlights") or {},
            },
            "items": item.get("items") or [],
        }
        return json.dumps(payload, ensure_ascii=False)
