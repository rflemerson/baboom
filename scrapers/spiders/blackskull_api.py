import base64
import json
import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class BlackSkullApiSpider(BaseSpider):
    BRAND_NAME = "Black Skull"
    BASE_URL = "https://www.blackskullusa.com.br"
    API_ENDPOINT = "https://www.blackskullusa.com.br/_v/segment/graphql/v1"

    # Static Configuration for Persisted Query
    QUERY_HASH = "ee2478d319404f621c3e0426e79eba3997665d48cb277a53bf0c3276e8e53c22"
    SENDER = "vtex.store-resources@0.x"
    PROVIDER = "vtex.search-graphql@0.x"

    def crawl(self):
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        headers = self.get_headers()  # Default headers
        all_products = []

        start = 0
        step = 50

        while True:
            end = start + step - 1
            logger.info(f"Fetching {start} to {end}...")

            try:
                # 1. Prepare Variables
                variables = {
                    "hideUnavailableItems": False,
                    "category": "",
                    "specificationFilters": [],
                    "orderBy": "OrderByTopSaleDESC",
                    "from": start,
                    "to": end,
                    "shippingOptions": [],
                    "variant": "",
                    "advertisementOptions": {
                        "showSponsored": False,
                        "sponsoredCount": 0,
                        "repeatSponsoredProducts": False,
                        "advertisementPlacement": "home_shelf",
                    },
                }

                # 2. Encode Variables (Base64)
                vars_json = json.dumps(variables, separators=(",", ":"))
                vars_b64 = base64.b64encode(vars_json.encode("utf-8")).decode("utf-8")

                # 3. Build Extensions
                extensions = {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.QUERY_HASH,
                        "sender": self.SENDER,
                        "provider": self.PROVIDER,
                    },
                    "variables": vars_b64,
                }
                extensions_json = json.dumps(extensions, separators=(",", ":"))

                # 4. Request Params
                params = {
                    "workspace": "newblackpdp",
                    "maxAge": "short",
                    "appsEtag": "remove",
                    "domain": "store",
                    "locale": "pt-BR",
                    "operationName": "Products",
                    "variables": "{}",
                    "extensions": extensions_json,
                }

                resp = requests.get(
                    self.API_ENDPOINT, params=params, headers=headers, timeout=20
                )

                if resp.status_code != 200:
                    logger.error(f"API Error {resp.status_code}: {resp.text[:100]}")
                    break

                data = resp.json()

                # 5. Extract items
                # Item Path: data -> products -> products
                products_list = []
                if "data" in data and "products" in data["data"]:
                    prods_container = data["data"]["products"]
                    if isinstance(prods_container, list):
                        products_list = prods_container
                    elif isinstance(prods_container, dict):
                        products_list = prods_container.get("products", [])
                        # Some VTEX queries return 'items' instead of 'products' inside
                        if not products_list and "items" in prods_container:
                            products_list = prods_container["items"]

                if not products_list:
                    logger.info("No more products found.")
                    break

                logger.info(f"Found {len(products_list)} items.")

                for p in products_list:
                    item = self._process_item(p)
                    if item:
                        all_products.append(item)

                # Check if we got fewer than requested (end of list)
                if len(products_list) < step:
                    break

                start += step
                self.sleep_random(0.5, 1.5)

            except Exception as e:
                logger.error(f"Request failed: {e}")
                break

        return all_products

    def _process_item(self, item):
        try:
            pid = item.get("productId")
            name = item.get("productName")
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            # Find Price in Sellers
            items_sku = item.get("items", [])
            if not items_sku:
                return None

            # Usually take first SKU
            sku = items_sku[0]
            sellers = sku.get("sellers", [])

            # Find default seller or first
            active_seller = next(
                (s for s in sellers if s.get("sellerDefault")),
                sellers[0] if sellers else None,
            )

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
                "price": float(price),
                "item_brand": self.BRAND_NAME,
                "item_list_name": "proteina",  # Default bucket for now
                "url": url,
                "stock": int(stock),
            }

        except Exception as e:
            logger.warning(f"Parse error: {e}")
            return None
