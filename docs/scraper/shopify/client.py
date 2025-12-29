import logging

import requests

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ShopifyDOCAPI:
    """
    Documentation and Testing Script for Shopify API.
    Used by Dark Lab.
    """

    BASE_URL = "https://www.darklabsuplementos.com.br"
    COLLECTION_HANDLE = "whey-protein"

    def test_shopify_endpoints(self):
        logger.info("=== Testing Shopify API (Dark Lab) ===")

        # 1. Collections + Products JSON
        # Pagination via 'page' and 'limit'
        endpoint = f"/collections/{self.COLLECTION_HANDLE}/products.json"
        url = f"{self.BASE_URL}{endpoint}"
        params = {"page": 1, "limit": 5}

        logger.info(f"Fetching: {url}")
        logger.info(f"Params: {params}")

        try:
            resp = requests.get(url, params=params, timeout=15)
            logger.info(f"Status Code: {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                products = data.get("products", [])
                logger.info(f"Products Found: {len(products)}")

                if products:
                    first = products[0]
                    logger.info(
                        f"Sample Product: {first.get('title')} (ID: {first.get('id')})"
                    )

                    # Variants Check
                    variants = first.get("variants", [])
                    if variants:
                        v = variants[0]
                        price = v.get("price")
                        qty = v.get("inventory_quantity")
                        avail = v.get("available")
                        barcode = v.get("barcode")
                        logger.info(f"  > Variant Price: {price}")
                        logger.info(
                            f"  > Available: {avail} | Qty: {qty} (Note: Qty often hidden/None in public API)"
                        )
                        logger.info(f"  > Barcode (EAN): {barcode}")
                    logger.info("-" * 30)
            else:
                logger.warning(f"Failed: {resp.text[:100]}")

        except Exception as e:
            logger.error(f"Error: {e}")

        logger.info("\n")


if __name__ == "__main__":
    api = ShopifyDOCAPI()
    api.test_shopify_endpoints()
