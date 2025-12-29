import logging
from typing import Any

import requests
import urllib3

from ..services import ScraperService
from .base_spider import BaseSpider

# Disable warnings for verify=False as per API strategy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class GrowthSpider(BaseSpider):
    BRAND_NAME = "Growth Supplements"
    STORE_SLUG = "growth"
    BASE_URL = "https://www.gsuplementos.com.br"

    # API Endpoints
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

    def get_headers(self) -> dict[str, str]:
        """
        Headers strictly required by Wap.Store / Sucuri WAF.
        """
        return {
            "User-Agent": "insomnia/12.2.0",  # Critical for WAF bypass
            "app-token": "wapstore",  # Critical for API auth
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://www.gsuplementos.com.br",
            "Referer": "https://www.gsuplementos.com.br/",
        }

    def _fetch_categories(self) -> list[str]:
        """
        Fetch dynamic category slugs from the menu API.
        """
        logger.info("Fetching dynamic categories...")
        try:
            resp = requests.get(
                self.API_MENU,
                headers=self.get_headers(),
                verify=False,  # noqa: S501
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning(f"Menu API failed: {resp.status_code}")
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
        logger.info(f"Starting crawl for {self.BRAND_NAME}")

        categories = self._fetch_categories()
        if not categories:
            logger.info("Using fallback categories")
            categories = self.FALLBACK_CATEGORIES

        logger.info(f"Categories to crawl: {len(categories)}")

        all_products = []
        processed_ids = set()

        for category_path in categories:
            logger.info(f"Crawling: {category_path}")

            offset = 0
            limit = 30  # API max is usually 30

            while True:
                params = {"url": category_path, "offset": offset, "limit": limit}

                try:
                    resp = requests.get(
                        self.API_LISTING,
                        params=params,  # type: ignore
                        headers=self.get_headers(),
                        verify=False,  # noqa: S501
                        timeout=30,
                    )

                    if resp.status_code != 200:
                        logger.debug(
                            f"Category {category_path} ended or failed: {resp.status_code}"
                        )
                        break

                    data = resp.json()
                    products_list = []

                    # Valid keys checked via research: data['conteudo']['produtos']
                    if "conteudo" in data and "produtos" in data["conteudo"]:
                        products_list = data["conteudo"]["produtos"]
                    elif "data" in data and "list" in data["data"]:
                        products_list = data["data"]["list"]

                    if not products_list:
                        break

                    items_in_page = 0
                    for item in products_list:
                        item_id = str(item.get("id"))
                        if item_id in processed_ids:
                            continue

                        processed_ids.add(item_id)

                        saved_obj = self._process_and_save(item)
                        if saved_obj:
                            all_products.append(saved_obj)
                            items_in_page += 1

                    if len(products_list) < limit:
                        # End of category
                        break

                    offset += limit
                    self.sleep_random(1, 2)

                except Exception as e:
                    logger.error(f"Error crawling {category_path}: {e}")
                    break

        logger.info(f"Crawl finished. Total products: {len(all_products)}")
        return all_products

    def _process_and_save(self, item: dict) -> Any | None:
        try:
            # 1. ID & Name
            external_id = str(item.get("id"))
            name = item.get("nome") or item.get("name")
            if not external_id or not name:
                return None

            # 2. SKU
            sku = str(item.get("sku") or "")

            # 3. URL
            link_slug = item.get("link") or item.get("slug") or item.get("url")
            product_url = ""
            if link_slug:
                if link_slug.startswith("http"):
                    product_url = link_slug
                else:
                    product_url = f"{self.BASE_URL}/{link_slug}"

            # 4. Price
            # Structure: "precos": { "vista": 139.50, "por": 139.50 }
            price_val = None
            precos = item.get("precos")
            if isinstance(precos, dict):
                price_val = precos.get("por") or precos.get("vista")
            elif "price" in item:
                price_val = item["price"]

            # 5. Stock
            # Structure: "estoque": 100
            stock_quantity = item.get("estoque") or item.get("balance") or 0
            try:
                stock_quantity = int(stock_quantity)
            except (ValueError, TypeError):
                stock_quantity = 0

            # Determine status based on quantity
            from ..models import ScrapedItem

            if stock_quantity > 0:
                stock_status = ScrapedItem.StockStatus.AVAILABLE
            else:
                stock_status = ScrapedItem.StockStatus.OUT_OF_STOCK

            # 6. EAN (Not reliable in listing, but let's try)
            ean = item.get("ean") or item.get("gtin") or ""

            # Save via Service
            return ScraperService.save_product(
                store_slug=self.STORE_SLUG,
                external_id=external_id,
                url=product_url,
                name=name,
                price=price_val,
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean=str(ean),
                sku=sku,
                pid=external_id,  # PID is often same as ID
            )

        except Exception as e:
            logger.error(f"Error processing item {item.get('id')}: {e}")
            return None
