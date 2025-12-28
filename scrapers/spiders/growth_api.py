import logging

import requests
import urllib3

from .base_spider import BaseSpider

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class GrowthApiSpider(BaseSpider):
    BRAND_NAME = "Growth Supplements"
    BASE_URL = "https://www.gsuplementos.com.br"
    API_LISTING = (
        "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category"
    )

    # Static Category URLs for now (Proteins)
    # Could be dynamic later via Menus API
    CATEGORY_URLS = ["/proteina/", "/creatina/", "/aminoacidos/"]

    def crawl(self):
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        headers = {
            "User-Agent": "insomnia/12.2.0",
            "app-token": "wapstore",
            "Content-Type": "application/json",
        }

        all_products = []

        session = requests.Session()
        session.verify = False

        # 1. Iterate Categories
        for cat_url in self.CATEGORY_URLS:
            logger.info(f"Crawling Category: {cat_url}")
            offset = 0
            limit = 30

            while True:
                params = {"url": cat_url, "offset": offset, "limit": limit}

                try:
                    logger.info(f"Fetching offset {offset}...")
                    resp = session.get(self.API_LISTING, headers=headers, params=params)  # type: ignore

                    if resp.status_code != 200:
                        logger.error(f"API Error {resp.status_code}: {resp.text[:100]}")
                        break

                    data = resp.json()

                    # Correct Parsing Logic (Thanks user!)
                    products_list = []
                    if "conteudo" in data and "produtos" in data["conteudo"]:
                        products_list = data["conteudo"]["produtos"]

                    if not products_list:
                        logger.info("No more products found in this category.")
                        break

                    logger.info(f"Found {len(products_list)} products.")

                    for p in products_list:
                        item = self._process_item(p)
                        if item:
                            all_products.append(item)

                    # Pagination logic
                    # If we got less than limit, we are likely done
                    if len(products_list) < limit:
                        break

                    offset += limit
                    self.sleep_random(0.5, 1.5)

                except Exception as e:
                    logger.error(f"Request failed: {e}")
                    break

        return all_products

    def _process_item(self, p):
        try:
            # Wap.Store JSON Structure
            pid = p.get("id")
            name = p.get("nome")
            link = p.get("link")  # e.g. "top-whey..."

            url = f"{self.BASE_URL}/{link}" if link else ""

            # Prices
            precos = p.get("precos", {})
            price = precos.get("vista") or precos.get("por") or 0.0

            # Stock
            stock = p.get("estoque", 0)

            if not pid or not name:
                return None

            return {
                "item_id": str(pid),
                "item_name": name,
                "price": float(price),
                "item_brand": self.BRAND_NAME,  # Growth is its own brand usually
                "item_list_name": "proteina",  # Broadly applying
                "url": url,
                "stock": int(stock),
            }
        except Exception as e:
            logger.warning(f"Item parse error: {e}")
            return None
