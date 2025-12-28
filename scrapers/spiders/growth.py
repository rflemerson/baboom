import logging

import requests
import urllib3

from .base_spider import BaseSpider

# Disable warnings for verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class GrowthApiSpider(BaseSpider):
    BRAND_NAME = "Growth Supplements"
    BASE_URL = "https://www.gsuplementos.com.br"
    API_ENDPOINT = (
        "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category"
    )

    # Expanded Category List
    CATEGORY_URLS = [
        "/proteina/",
        "/creatina/",
        "/aminoacidos/",
        "/pre-treino/",
        "/carboidratos/",
        "/vitaminas/",
        "/acessorios/",
        "/roupas/",
        "/kits/",
    ]

    def crawl(self):
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        all_products = []

        for category_slug in self.CATEGORY_URLS:
            logger.info(f"Crawling Category: {category_slug}")
            # The API expects just the slug (e.g. "proteina"), but urls might be "/proteina/"
            slug_clean = category_slug.strip("/")

            page = 1
            limit = 30  # Max limit observed

            while True:
                params = {"slug": slug_clean, "page": page, "limit": limit}

                try:
                    response = requests.get(
                        self.API_ENDPOINT,
                        params=params,  # type: ignore
                        headers=self.get_headers(),
                        verify=False,  # noqa: S501
                        timeout=30,
                    )

                    if response.status_code != 200:
                        break

                    data = response.json()
                    # Data structure: data -> list -> [products]
                    products_list = data.get("data", {}).get("list", [])

                    if not products_list:
                        break

                    for item in products_list:
                        try:
                            processed_item = self._process_item(item, category_slug)
                            if processed_item:
                                all_products.append(processed_item)
                        except Exception as e:
                            logger.debug(f"Skipping item: {e}")

                    # Pagination Check
                    # If we got fewer items than limit, it's the last page
                    if len(products_list) < limit:
                        break

                    page += 1
                    self.sleep_random(1, 2)

                except Exception as e:
                    logger.error(f"Error crawling {category_slug}: {e}")
                    break

        return all_products

    def get_headers(self):
        # Override headers specifically for Growth
        return {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "app-token": "wapstore",  # Critical Header
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.gsuplementos.com.br",
            "Referer": "https://www.gsuplementos.com.br/",
        }

    def _process_item(self, item, category_name="proteina"):
        try:
            name = item.get("name")
            pid = item.get("id")
            # Prices: 'price' (original), 'promotional_price' (discounted)
            price_raw = item.get("promotional_price") or item.get("price")
            # In Growth API, price is usually a float or string float
            price = float(price_raw) if price_raw else 0.0

            slug = item.get("slug")
            url = f"{self.BASE_URL}/{slug}" if slug else ""

            # Stock check not explicit in list, assume available if listed?
            # Or balance check? Let's check 'balance' or 'stock'.
            # Checking 'balance' field often present in wap.store
            stock = int(item.get("balance", 0))

            # If item has attributes (flavors), price might vary, but listing usually gives main price.

            if not name or not price:
                return None

            return {
                "item_id": str(pid),
                "item_name": name,
                "price": price,
                "item_brand": self.BRAND_NAME,
                "item_list_name": category_name.strip("/"),
                "url": url,
                "stock": stock,
            }

        except Exception as e:
            logger.warning(f"Item parse error: {e}")
            return None
