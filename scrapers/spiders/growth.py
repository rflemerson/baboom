import logging
from typing import Any

import urllib3

from ..models import ScrapedItem
from ..services import ScraperService
from ..types import ProductIngestionInput
from .base_spider import BaseSpider
from .http_client import HttpClient

# Disable warnings for verify=False as per API strategy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class GrowthSpider(BaseSpider):
    """Spider for Growth Supplements (Wap.Store API)."""

    BRAND_NAME = "Growth Supplements"
    STORE_SLUG = "growth"
    BASE_URL = "https://www.gsuplementos.com.br"

    API_LISTING = (
        "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category"
    )
    API_MENU = "https://www.gsuplementos.com.br/api/v2/front/struct/menus/nova-home-suplementos-categorias"

    FALLBACK_CATEGORIES = [
        "/proteina/",
        "/creatina/",
        "/aminoacidos/",
        "/pre-treino/",
        "/vitaminas/",
        "/acessorios/",
        "/vegano/",
    ]

    def __init__(self, categories: list[str] | None = None) -> None:
        super().__init__(categories)
        self.http_client = HttpClient(timeout=30)

    def get_headers(self) -> dict[str, str]:
        """Get API headers."""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "app-token": "wapstore",  # Critical for API auth
            "Content-Type": "application/json",
            "Origin": "https://www.gsuplementos.com.br",
            "Referer": "https://www.gsuplementos.com.br/",
            "Sec-Ch-Ua": '"Chromium";v="120", "Google Chrome";v="120", "Not_A Brand";v="8"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _fetch_categories(self) -> list[str]:
        logger.info("Fetching dynamic categories...")
        try:
            resp = self.http_client.get(
                self.API_MENU,
                headers=self.get_headers(),
                verify=False,
            )
            if resp is None or resp.status_code != 200:
                logger.warning(
                    f"Menu API failed: {resp.status_code if resp else 'No response'}"
                )
                return []

            data = resp.json()
            # Wap.Store menu structure varies, try "data" or "menu"
            items = data.get("data") or data.get("menu") or []

            slugs = set()

            def extract_recursive(nodes: list[dict]) -> None:
                for node in nodes:
                    url = node.get("url") or node.get("link")
                    if url:
                        # Clean URL to get slug/path (e.g., "/proteina/")
                        path = url.replace("https://www.gsuplementos.com.br", "")
                        if not path.startswith("/"):
                            path = f"/{path}"
                        if not path.endswith("/"):
                            path = f"{path}/"

                        if len(path) > 1:
                            slugs.add(path)

                    # Recurse
                    children = node.get("children") or node.get("itens") or []
                    if children:
                        extract_recursive(children)

            extract_recursive(items if isinstance(items, list) else [])
            return list(slugs)

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def crawl(self) -> list[Any]:
        """Crawl products from API."""
        logger.info(f"Starting crawl for {self.BRAND_NAME}")

        categories = self._fetch_categories()
        self.check_category_discrepancy(categories, self.FALLBACK_CATEGORIES)

        if not categories:
            logger.info("Using fallback/config categories")
            categories = self.categories_to_crawl or self.FALLBACK_CATEGORIES

        logger.info(f"Categories to crawl: {len(categories)}")

        all_products = []
        for category_path in categories:
            products = self._crawl_category(category_path)
            all_products.extend(products)

        logger.info(f"Crawl finished. Total products: {len(all_products)}")
        return all_products

    def _crawl_category(self, category_path: str) -> list[Any]:
        """Crawl a single category."""
        logger.info(f"Crawling: {category_path}")
        products = []
        processed_ids = set()
        offset = 0
        limit = 30

        while True:
            params = {"url": category_path, "offset": offset, "limit": limit}
            try:
                resp = self.http_client.get(
                    self.API_LISTING,
                    params=params,
                    headers=self.get_headers(),
                    verify=False,
                )

                if resp is None or resp.status_code != 200:
                    break

                data = resp.json()
                products_list = self._extract_products_list(data)

                if not products_list:
                    break

                items_in_page = 0
                for item in products_list:
                    item_id = str(item.get("id"))
                    if item_id in processed_ids:
                        continue

                    processed_ids.add(item_id)
                    saved_obj = self._process_and_save(item, category_path)
                    if saved_obj:
                        products.append(saved_obj)
                        items_in_page += 1

                if len(products_list) < limit:
                    break

                offset += limit
                self.sleep_random(1, 2)

            except Exception as e:
                logger.error(f"Error crawling {category_path}: {e}")
                break

        return products

    def _extract_products_list(self, data: dict) -> list[dict]:
        """Extract product list from response."""
        if "conteudo" in data and "produtos" in data["conteudo"]:
            return data["conteudo"]["produtos"]
        if "data" in data and "list" in data["data"]:
            return data["data"]["list"]
        return []

    def _process_and_save(self, item: dict, category: str) -> Any | None:
        try:
            external_id = str(item.get("id"))
            name = item.get("nome") or item.get("name")
            if not external_id or not name:
                return None

            sku = str(item.get("sku") or "")

            link_slug = item.get("link") or item.get("slug") or item.get("url")
            product_url = ""
            if link_slug:
                if link_slug.startswith("http"):
                    product_url = link_slug
                else:
                    product_url = f"{self.BASE_URL}/{link_slug}"

            # Structure: "precos": { "vista": 139.50, "por": 139.50 }
            price_val = None
            precos = item.get("precos")
            if isinstance(precos, dict):
                price_val = precos.get("por") or precos.get("vista")
            elif "price" in item:
                price_val = item["price"]

            # Structure: "estoque": 100
            stock_quantity = item.get("estoque") or item.get("balance") or 0
            try:
                stock_quantity = int(stock_quantity)
            except (ValueError, TypeError):
                stock_quantity = 0

            if stock_quantity > 0:
                stock_status = ScrapedItem.StockStatus.AVAILABLE
            else:
                stock_status = ScrapedItem.StockStatus.OUT_OF_STOCK

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
            return ScraperService.save_product(input_data)

        except Exception as e:
            logger.error(f"Error processing item {item.get('id')}: {e}")
            return None
