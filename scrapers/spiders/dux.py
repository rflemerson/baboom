import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class DuxSpider(BaseSpider):
    BRAND_NAME = "Dux Nutrition"
    BASE_URL = "https://www.duxhumanhealth.com"
    API_TREE = "https://www.duxhumanhealth.com/api/catalog_system/pub/category/tree/3"
    FALLBACK_CATEGORIES = ["proteinas", "creatina", "saude", "vestuario", "acessorios"]

    def _fetch_categories(self):
        try:
            resp = requests.get(self.API_TREE, headers=self.get_headers(), timeout=10)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch category tree: {resp.status_code}")
                return []

            tree = resp.json()
            slugs = set()

            def extract_slugs(nodes):
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
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def crawl(self):
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        categories = self._fetch_categories()
        if not categories:
            logger.info("Using Fallback Categories.")
            categories = self.FALLBACK_CATEGORIES

        logger.info(f"Discovered {len(categories)} categories to crawl.")

        all_products = []

        for category_slug in categories:
            logger.info(f"Crawling Category: {category_slug}")
            search_url = f"https://www.duxhumanhealth.com/api/catalog_system/pub/products/search/{category_slug}"

            start = 0
            step = 50

            while True:
                end = start + step - 1
                params = {"_from": start, "_to": end}

                try:
                    response = requests.get(
                        search_url,
                        params=params,
                        headers=self.get_headers(),
                        timeout=30,
                    )

                    if response.status_code not in [200, 206]:
                        break

                    data = response.json()
                    if not data:
                        break

                    for item in data:
                        try:
                            processed_item = self._process_item(item)
                            if processed_item:
                                all_products.append(processed_item)
                        except Exception as e:
                            logger.debug(f"Skipping item: {e}")

                    if len(data) < step:
                        break

                    start += step
                    self.sleep_random(0.5, 1.0)

                except Exception as e:
                    logger.error(f"Error crawling {category_slug}: {e}")
                    break

        return all_products

    def _process_item(self, item):
        try:
            pid = item.get("productId")
            name = item.get("productName")
            brand = item.get("brand") or self.BRAND_NAME
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            skus = item.get("items", [])
            if not skus:
                return None

            first_sku = skus[0]

            sellers = first_sku.get("sellers", [])
            active_seller = None

            for seller in sellers:
                if seller.get("sellerDefault"):
                    active_seller = seller
                    break

            if not active_seller and sellers:
                active_seller = sellers[0]

            if not active_seller:
                return None

            comm_offer = active_seller.get("commertialOffer", {})
            price = comm_offer.get("Price")
            stock = comm_offer.get("AvailableQuantity", 0)

            if price is None:
                return None

            return {
                "item_id": str(pid),
                "item_name": name,
                "price": price,
                "item_brand": brand,
                "item_list_name": "proteina",
                "url": url,
                "stock": stock,
            }
        except Exception as e:
            logger.warning(f"Item parse error: {e}")
            return None
