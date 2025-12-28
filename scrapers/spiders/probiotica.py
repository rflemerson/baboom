import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class ProbioticaSpider(BaseSpider):
    BRAND_NAME = "Probiótica"
    BASE_URL = "https://www.probiotica.com.br"
    # Same strategy as Max Titanium: Search for 'whey'
    API_ENDPOINT = (
        "https://www.probiotica.com.br/api/catalog_system/pub/products/search/whey"
    )

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
                        processed_item = self._process_item(item)
                        if processed_item:
                            products.append(processed_item)
                    except Exception as e:
                        logger.error(
                            f"Error processing item {item.get('productId')}: {e}"
                        )

                start += step
                self.sleep_random(1, 2)

            except Exception as e:
                logger.error(f"Request failed: {e}")
                break

        return products

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
