import logging

import requests

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VtexLegacyAPI:
    """
    Documentation and Testing Script for VTEX Legacy / Search API.
    Used by Dux Nutrition, IntegralMedica, Max Titanium, Probiotica.
    """

    STORES = {
        "dux": "https://www.duxhumanhealth.com",
        "integral": "https://www.integralmedica.com.br",
        "max": "https://www.maxtitanium.com.br",
        "probiotica": "https://www.probiotica.com.br",
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    def test_store_apis(self, store_key):
        base_url = self.STORES.get(store_key)
        if not base_url:
            logger.error(f"Unknown store: {store_key}")
            return

        logger.info(f"=== Testing Store: {store_key.upper()} ({base_url}) ===")

        # 1. Category Tree
        # The '3' at the end specifies depth.
        tree_endpoint = "/api/catalog_system/pub/category/tree/3"
        logger.info(f"Fetching Category Tree: {tree_endpoint}")

        slugs = []
        try:
            resp = requests.get(
                f"{base_url}{tree_endpoint}", headers=self.HEADERS, timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Tree fetched. Top level categories: {len(data)}")

                # Extract a few slugs for testing
                def extract(nodes):
                    found = []
                    for node in nodes:
                        url = node.get("url", "")
                        if url:
                            slug = url.rstrip("/").split("/")[-1]
                            found.append(slug)
                        if "children" in node:
                            found.extend(extract(node["children"]))
                    return found

                all_slugs = extract(data)
                # Prioritize 'whey' or common terms
                slugs = [s for s in all_slugs if "whey" in s.lower()][:1]
                if not slugs and all_slugs:
                    slugs = [all_slugs[0]]

                logger.info(f"Selected slug for search test: {slugs}")
            else:
                logger.warning(f"Tree Fetch Failed: {resp.status_code}")

        except Exception as e:
            logger.error(f"Tree Error: {e}")

        # 2. Product Search
        # Note: Probiótica returns 0 products when searching by slug, so we search without it
        if slugs or store_key == "probiotica":
            # Force Probiótica to search without slug (their category search doesn't work)
            slug = "" if store_key == "probiotica" else (slugs[0] if slugs else "")
            search_endpoint = f"/api/catalog_system/pub/products/search/{slug}" if slug else "/api/catalog_system/pub/products/search"
            logger.info(f"Testing Search API: {search_endpoint}")

            try:
                params = {"_from": 0, "_to": 4}  # Fetch 5 items
                resp = requests.get(
                    f"{base_url}{search_endpoint}",
                    headers=self.HEADERS,
                    params=params,
                    timeout=15,
                )

                if resp.status_code in [200, 206]:
                    items = resp.json()
                    logger.info(f"Response Type: {type(items)}")
                    if isinstance(items, list):
                        logger.info(f"Items Found: {len(items)}")
                        if items:
                            first = items[0]
                            logger.info(
                                f"Sample Item: {first.get('productName')} (ID: {first.get('productId')})"
                            )

                            # Verify critical fields we extract
                            if "items" in first and len(first["items"]) > 0:
                                sku = first["items"][0]
                                sellers = sku.get("sellers", [])
                                if sellers:
                                    price = (
                                        sellers[0]
                                        .get("commertialOffer", {})
                                        .get("Price")
                                    )
                                    stock = (
                                        sellers[0]
                                        .get("commertialOffer", {})
                                        .get("AvailableQuantity")
                                    )
                                    ean = sku.get("ean")
                                    logger.info(f"  > Price: {price} | Stock: {stock} | EAN: {ean}")
                else:
                    logger.warning(f"Search Failed: {resp.status_code}")

            except Exception as e:
                logger.error(f"Search Error: {e}")

        logger.info("\n")


if __name__ == "__main__":
    api = VtexLegacyAPI()
    for store in ["dux", "integral", "max", "probiotica"]:
        api.test_store_apis(store)
