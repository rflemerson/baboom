import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class DarkLabSpider(BaseSpider):
    BRAND_NAME = "Dark Lab"
    BASE_URL = "https://www.darklabsuplementos.com.br"
    API_ENDPOINT = "https://www.darklabsuplementos.com.br/products.json"

    def crawl(self):
        logger.info(f"Starting Shopify API crawl for {self.BRAND_NAME}...")

        products = []
        page = 1
        limit = 250  # Max shopify limit per page usually

        while True:
            params = {"limit": limit, "page": page}
            logger.info(f"Fetching page {page}...")

            try:
                response = requests.get(
                    self.API_ENDPOINT,
                    params=params,
                    headers=self.get_headers(),
                    timeout=30,
                )

                if response.status_code != 200:
                    logger.error(f"API Error {response.status_code}: {response.text}")
                    break

                data = response.json()
                items = data.get("products", [])

                if not items:
                    logger.info("No more products found.")
                    break

                logger.info(f"Fetched {len(items)} products on page {page}.")

                for item in items:
                    try:
                        # Iterate through variants if needed, or just main product
                        # For Baboom model, we save the Product.
                        # Price usually comes from variants. We pick the cheapest or first available.
                        processed_item = self._process_item(item)
                        if processed_item:
                            products.append(processed_item)
                    except Exception as e:
                        logger.error(f"Error processing item {item.get('id')}: {e}")

                page += 1
                self.sleep_random(1, 2)

            except Exception as e:
                logger.error(f"Request failed: {e}")
                break

        return products

    def _process_item(self, item):
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
            stock = 0

            # Shopify usually doesn't expose strict stock count publicly in standard JSON unless tweaked,
            # but 'available' boolean is present.
            if selected_variant.get("available"):
                stock = 999  # Dummy for available

            # Filter for "Whey" or "Protein" if we want only that category?
            # User asked "Dark Lab", maybe simplest is to scrape everything and filter in service?
            # Or filter by product_type or tags here.
            # Let's simple check if "body_html" or "product_type" mentions protein, or just save everything for now.
            # However, task context was "whey protein".
            # Let's filter by name or type
            p_name_lower = name.lower()

            is_relevant = (
                "whey" in p_name_lower
                or "protein" in p_name_lower
                or "proteina" in p_name_lower
            )
            if not is_relevant:
                return None

            return {
                "item_id": pid,
                "item_name": name,
                "price": price,
                "item_brand": brand,
                "item_list_name": "products-json",
                "url": url,
                "stock": stock,
            }
        except Exception as e:
            logger.warning(f"Item parse error: {e}")
            return None
