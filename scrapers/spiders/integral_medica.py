import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class IntegralMedicaSpider(BaseSpider):
    BRAND_NAME = "Integralmedica"
    BASE_URL = "https://www.integralmedica.com.br"
    API_ENDPOINT = "https://www.integralmedica.com.br/api/catalog_system/pub/products/search/proteina"

    def crawl(self):
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        products = []
        start = 0
        step = 50

        while True:
            end = start + step - 1
            params = {"_from": start, "_to": end}
            logger.info(f"Fetching products {start} to {end}...")

            try:
                # Use standard requests, emulate browser headers just in case
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

                if not data:
                    logger.info("No more products found.")
                    break

                logger.info(f"Fetched {len(data)} products.")

                for item in data:
                    try:
                        # Extract Main Info
                        processed_item = self._process_item(item)
                        if processed_item:
                            products.append(processed_item)
                    except Exception as e:
                        logger.error(
                            f"Error processing item {item.get('productId')}: {e}"
                        )

                start += step
                self.sleep_random(1, 2)  # Be polite

            except Exception as e:
                logger.error(f"Request failed: {e}")
                break

        return products

    def _process_item(self, item):
        """
        Map VTEX API Product to our internal dict structure.
        """
        try:
            # 1. Basic Info
            pid = item.get("productId")
            name = item.get("productName")
            brand = item.get("brand") or self.BRAND_NAME
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            # 2. SKU / Price Information
            # VTEX products have 'items' (SKUs). We need to pick one (usually the first or available one).
            skus = item.get("items", [])
            if not skus:
                return None

            # Pick the first SKU
            first_sku = skus[0]

            # Check availability and price in sellers
            sellers = first_sku.get("sellers", [])
            active_seller = None

            # Usually seller "1" is the main store
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
