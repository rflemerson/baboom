import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class DarkLabSpider(BaseSpider):
    BRAND_NAME = "Dark Lab"
    BASE_URL = "https://www.darklabsuplementos.com.br"
    API_COLLECTIONS = "https://www.darklabsuplementos.com.br/collections.json"

    # Fallback if dynamic fetching fails
    FALLBACK_CATEGORIES = [
        "best-sellers",
        "whey-protein",
        "creatina",
        "pre-treino",
        "hipercalorico",
        "aminoacidos",
        "acessorios",
        "kits",
        "vegan",
        "vitaminas",
    ]

    def _fetch_categories(self):
        """
        Fetch dynamic collections (categories) from Shopify's collections.json endpoint.
        Returns a list of collection handles (slugs).
        """
        try:
            logger.info("Fetching categories for Dark Lab...")
            response = requests.get(
                self.API_COLLECTIONS, headers=self.get_headers(), timeout=15
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch collections: {response.status_code}")
                return []

            data = response.json()
            collections = data.get("collections", [])

            handles = []
            for collection in collections:
                handle = collection.get("handle")
                if handle:
                    handles.append(handle)

            return handles

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def crawl(self):
        """
        Main crawl method: fetches collections and iterates over them to get products.
        """
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")
        all_products = []

        categories = self._fetch_categories()
        if not categories:
            logger.info("No dynamic categories found, using fallback.")
            categories = self.FALLBACK_CATEGORIES

        logger.info(f"Discovered {len(categories)} categories to crawl.")

        for category in categories:
            logger.info(f"Crawling Category: {category}")

            # Shopify usually allows fetching products for a specific collection via:
            # /collections/{handle}/products.json
            collection_endpoint = (
                f"{self.BASE_URL}/collections/{category}/products.json"
            )

            page = 1
            limit = 250  # Shopify often allows up to 250 per page

            while True:
                params = {"page": page, "limit": limit}

                try:
                    response = requests.get(
                        collection_endpoint,
                        params=params,
                        headers=self.get_headers(),
                        timeout=30,
                    )

                    if response.status_code != 200:
                        logger.error(
                            f"Error fetching {category} page {page}: {response.status_code}"
                        )
                        break

                    data = response.json()
                    products = data.get("products", [])

                    if not products:
                        break

                    for item in products:
                        try:
                            processed = self._process_item(item, category)
                            if processed:
                                all_products.append(processed)
                        except Exception as e:
                            logger.debug(f"Item error in {category}: {e}")

                    # Determine when to stop
                    if len(products) < limit:
                        break

                    page += 1
                    self.sleep_random(0.5, 1.5)

                except Exception as e:
                    logger.error(f"Crawl error for {category}: {e}")
                    break

        return all_products

    def _process_item(self, item, category_name="products-json"):
        try:
            pid = str(item.get("id"))
            name = item.get("title")
            brand = item.get("vendor") or self.BRAND_NAME
            handle = item.get("handle")
            url = f"{self.BASE_URL}/products/{handle}" if handle else ""

            # Find Price in variants
            variants = item.get("variants", [])
            if not variants:
                return None

            # Pick first available or just first
            selected_variant = variants[0]
            price = selected_variant.get("price")

            # Stock: Shopify JSON usually has 'available' boolean, sometimes 'inventory_quantity' if leaked
            stock = 0
            if selected_variant.get("available"):
                stock = 999  # Dummy for available

            if not price:
                return None

            return {
                "item_id": pid,
                "item_name": name,
                "price": float(price),
                "item_brand": brand,
                "item_list_name": category_name,
                "url": url,
                "stock": stock,
            }
        except Exception as e:
            logger.warning(f"Item parse error: {e}")
            return None
