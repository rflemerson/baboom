import logging

import requests
import urllib3

from .base_spider import BaseSpider

# Disable warnings for verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class GrowthSpider(BaseSpider):
    BRAND_NAME = "Growth Supplements"
    BASE_URL = "https://www.gsuplementos.com.br"
    API_ENDPOINT = (
        "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category"
    )
    API_MENU = "https://www.gsuplementos.com.br/api/v2/front/struct/menus/nova-home-suplementos-categorias"
    FALLBACK_CATEGORIES = [
        "/proteina/",
        "/creatina/",
        "/aminoacidos/",
        "/pre-treino/",
        "/carboidratos/",
        "/vitaminas/",
        "/acessorios/",
        "/roupas/",
        "/kits/",
        "/vegano/",
    ]

    def _fetch_categories(self):
        """
        Fetch dynamic categories from the 'nova-home-suplementos-categorias' menu endpoint.
        """
        try:
            logger.info("Fetching dynamic categories for Growth...")

            response = requests.get(
                self.API_MENU,
                headers=self.get_headers(),
                verify=False,  # noqa: S501
                timeout=15,
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch menu: {response.status_code}")
                return []

            data = response.json()
            # Wap.Store V2 menu structure handling
            menu_items = data.get("data", [])
            if not menu_items:
                menu_items = data.get("menu", [])

            if isinstance(data, list):
                menu_items = data

            urls = set()

            def extract_urls(items):
                for item in items:
                    # 'url' might be full "https://..." or relative
                    raw_url = item.get("url") or item.get("link")
                    if raw_url:
                        # Extract the path part
                        # If full url, split
                        if "gsuplementos.com.br" in raw_url:
                            path = raw_url.split("gsuplementos.com.br")[-1]
                        else:
                            path = raw_url

                        # Ensure it ends with / and starts with /
                        if not path.startswith("/"):
                            path = "/" + path
                        if not path.endswith("/"):
                            path = path + "/"

                        # Basic validation
                        if len(path) > 1:
                            urls.add(path)

                    # Check children
                    children = item.get("children", []) or item.get("itens", [])
                    if children:
                        extract_urls(children)

            extract_urls(menu_items)
            return list(urls)

        except Exception as e:
            logger.error(f"Error fetching Growth categories: {e}")
            return []

    def crawl(self):
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        # Dynamic Discovery
        categories = self._fetch_categories()

        if not categories:
            logger.info("Using Fallback Categories.")
            categories = self.FALLBACK_CATEGORIES

        logger.info(f"Discovered {len(categories)} categories to crawl.")

        all_products = []

        for category_url in categories:
            logger.info(f"Crawling Category: {category_url}")
            # The API expects just the slug (e.g. "proteina"), but urls might be "/proteina/"
            slug_clean = category_url.strip("/")

            # Skip empty slugs
            if not slug_clean:
                continue

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
                            processed_item = self._process_item(item, slug_clean)
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
                    logger.error(f"Error crawling {category_url}: {e}")
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

            # Check 'balance' or 'stock'. Checking 'balance' field often present in wap.store
            stock = int(item.get("balance", 0))

            # If item has attributes (flavors), price might vary, but listing usually gives main price.

            if not name or not price:
                return None

            return {
                "item_id": str(pid),
                "item_name": name,
                "price": price,
                "item_brand": self.BRAND_NAME,
                "item_list_name": category_name,
                "url": url,
                "stock": stock,
            }

        except Exception as e:
            logger.warning(f"Item parse error: {e}")
            return None
