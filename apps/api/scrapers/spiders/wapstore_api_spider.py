"""Base spider for Wap.Store-backed APIs."""

import json
import logging
import os

import urllib3

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
from .http_client import HttpClient

# Disable warnings for verify=False as per API strategy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

PAGE_SIZE = 30
HTTP_FAILURE_LIMIT = 8
HTTP_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
WAPSTORE_SUCCESS_CODE = 200


class WapStoreApiSpider(CatalogApiSpider):
    """Template spider for Wap.Store catalog APIs."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    API_LISTING = ""
    API_MENU = ""

    FALLBACK_CATEGORIES: tuple[str, ...] = ()

    def _initial_cursor(self) -> int:
        """Return initial offset for pagination."""
        return 0

    def _next_cursor(self, cursor: int, page_size: int) -> int:
        """Advance Wap.Store offset cursor."""
        return cursor + page_size

    def __init__(self, categories: list[str] | None = None) -> None:
        """Initialize Wap.Store spider state and HTTP client configuration."""
        super().__init__(categories)
        self.http_client = HttpClient(timeout=30)
        self.ssl_verify = os.getenv("GROWTH_SSL_VERIFY", "0") == "1"
        self._consecutive_http_failures = 0

    def get_headers(self) -> dict[str, str]:
        """Get API headers."""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "app-token": "wapstore",
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
            "Sec-Ch-Ua": (
                '"Chromium";v="120", "Google Chrome";v="120", '
                '"Not_A Brand";v="8"'
            ),
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _fetch_categories(self) -> list[str]:
        """Fetch category paths from the menu endpoint."""
        logger.info("Fetching dynamic categories...")
        try:
            resp = self._http_client_get(
                self.API_MENU,
                verify=self.ssl_verify,
            )
            if resp is None or resp.status_code != WAPSTORE_SUCCESS_CODE:
                logger.warning(
                    "Menu API failed: %s",
                    resp.status_code if resp else "No response",
                )
                return []

            data = resp.json()
            items = data.get("data") or data.get("menu") or []
            slugs = set()

            def extract_recursive(nodes: list[dict[str, object]]) -> None:
                for node in nodes:
                    url = node.get("url") or node.get("link")
                    if url:
                        path = str(url).replace(self.BASE_URL, "")
                        if not path.startswith("/"):
                            path = f"/{path}"
                        if not path.endswith("/"):
                            path = f"{path}/"

                        if len(path) > 1 and self._is_valid_category_path(path):
                            slugs.add(path)

                    children = node.get("children") or node.get("itens") or []
                    if children:
                        extract_recursive(children)

            extract_recursive(items if isinstance(items, list) else [])
            return list(slugs)

        except Exception:
            logger.exception("Error fetching categories")
            return []

    def _crawl_category(
        self,
        category_path: str,
        processed_ids: set[str],
    ) -> list[object]:
        """Crawl a single category."""
        logger.info("Crawling: %s", category_path)
        products: list[object] = []
        offset = self._initial_cursor()
        limit = PAGE_SIZE

        while True:
            try:
                products_list = self._fetch_page_items(category_path, offset, limit)
                if products_list is None or not products_list:
                    break

                for item in products_list:
                    item_id = str(item.get("id"))
                    if item_id in processed_ids:
                        continue

                    processed_ids.add(item_id)
                    saved_obj = self._process_and_save(item, category_path)
                    if saved_obj:
                        products.append(saved_obj)

                if len(products_list) < limit:
                    break

                offset = self._next_cursor(offset, limit)
                self.sleep_random(1, 2)

            except Exception:
                logger.exception("Error crawling %s", category_path)
                break

        return products

    def _fetch_page_items(
        self,
        category_path: str,
        cursor: int,
        page_size: int,
    ) -> list[dict] | None:
        """Fetch one category page from Wap.Store listing endpoint."""
        params = {"url": category_path, "offset": cursor, "limit": page_size}
        resp = self._http_client_get(
            self.API_LISTING,
            params=params,
            verify=self.ssl_verify,
        )
        if resp is None or resp.status_code != WAPSTORE_SUCCESS_CODE:
            return None

        data = resp.json()
        return self._extract_products_list(data)

    def _http_client_get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        verify: bool = True,
    ) -> object | None:
        """Retry wrapper for HttpClient with simple circuit-breaker behavior."""
        # Prevent hammering blocked origins when consecutive failures keep happening.
        if self._consecutive_http_failures >= HTTP_FAILURE_LIMIT:
            logger.error("Circuit breaker open for %s after repeated failures", url)
            return None

        attempts = max(1, int(self.HTTP_RETRIES))
        for attempt in range(1, attempts + 1):
            resp = self.http_client.get(
                url,
                params=params,
                headers=self.get_headers(),
                verify=verify,
            )
            if (
                resp is not None
                and resp.status_code not in HTTP_RETRYABLE_STATUS_CODES
            ):
                self._consecutive_http_failures = 0
                return resp
            if attempt < attempts:
                backoff = self.HTTP_RETRY_BACKOFF_SECONDS * attempt
                self.sleep_random(backoff, backoff + 0.2)

        self._consecutive_http_failures += 1
        return resp

    def _extract_products_list(
        self,
        data: dict[str, object],
    ) -> list[dict[str, object]]:
        """Extract product list from response."""
        if "conteudo" in data and "produtos" in data["conteudo"]:
            return data["conteudo"]["produtos"]
        if "data" in data and "list" in data["data"]:
            return data["data"]["list"]
        return []

    def _process_and_save(
        self,
        item: dict[str, object],
        category: str,
    ) -> object | None:
        """Normalize and persist one Wap.Store product."""
        try:
            external_id = str(item.get("id"))
            name = item.get("nome") or item.get("name")
            if not external_id or not name:
                return None

            sku = str(item.get("sku") or "")
            product_url = self._build_product_url(item)
            if not is_http_url(product_url):
                logger.warning(
                    "Skipping %s item without valid URL: %s",
                    self.BRAND_NAME,
                    external_id,
                )
                return None

            price_val = self._parse_price(self._extract_raw_price(item))
            if price_val is None:
                logger.warning(
                    "Skipping %s item without valid price: %s",
                    self.BRAND_NAME,
                    external_id,
                )
                return None

            stock_quantity = self._parse_stock(
                item.get("estoque") or item.get("balance"),
            )
            stock_status = self._resolve_stock_status(stock_quantity)
            ean = item.get("ean") or item.get("gtin") or ""

            input_data = ProductIngestionInput(
                store_slug=self.STORE_SLUG,
                external_id=external_id,
                url=product_url,
                name=name,
                price=price_val,
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean=str(ean),
                sku=sku,
                pid=external_id,
                category=category,
            )
            saved = ScraperService.save_product(input_data)
            persist_json_context(saved, self._build_product_context(item))
        except Exception:
            logger.exception("Error processing item %s", item.get("id"))
            return None

        return saved

    def _build_product_url(self, item: dict) -> str:
        """Build canonical product URL from payload."""
        link_slug = item.get("link") or item.get("slug") or item.get("url")
        if not link_slug:
            return ""
        if str(link_slug).startswith("http"):
            return str(link_slug)
        return f"{self.BASE_URL}/{str(link_slug).lstrip('/')}"

    def _extract_raw_price(self, item: dict[str, object]) -> object:
        """Extract raw price token from payload."""
        precos = item.get("precos")
        if isinstance(precos, dict):
            return precos.get("por") or precos.get("vista")
        return item.get("price")

    def _resolve_stock_status(self, stock_quantity: int | None) -> str:
        if stock_quantity is None or stock_quantity > 0:
            return ScrapedItem.StockStatus.AVAILABLE
        return ScrapedItem.StockStatus.OUT_OF_STOCK

    def _is_valid_category_path(self, path: str) -> bool:
        """Filter menu paths to product category routes."""
        invalid_tokens = {
            "conta",
            "carrinho",
            "checkout",
            "institucional",
            "blog",
            "atendimento",
            "politica",
            "privacidade",
            "termos",
        }
        lowered = path.lower()
        return not any(token in lowered for token in invalid_tokens)

    def _parse_price(self, raw_price: object) -> float | None:
        return parse_positive_price(raw_price)

    def _parse_stock(self, quantity: object) -> int | None:
        return parse_optional_int(quantity)

    def _build_product_context(self, item: dict) -> str:
        """Build structured context for downstream agents."""
        payload = {
            "platform": "uappi_wapstore",
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
