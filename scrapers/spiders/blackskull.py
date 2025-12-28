import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class BlackSkullApiSpider(BaseSpider):
    BRAND_NAME = "Black Skull"
    BASE_URL = "https://www.blackskullusa.com.br"
    API_ENDPOINT = "https://www.blackskullusa.com.br/_v/segment/graphql/v1"

    # Query matching standard VTEX IO "productSearch" or similar persisted query
    # This query string must match what the site expects if using GET (persisted)
    # or you can use POST with full body. POST is reliably easier if not blocked.
    GRAPHQL_QUERY = """
    query productSearch($selectedFacets: [SelectedFacetInput], $from: Int, $to: Int, $orderBy: String) {
      productSearch(selectedFacets: $selectedFacets, from: $from, to: $to, orderBy: $orderBy, hideUnavailableItems: true, simulationBehavior: default) {
        products {
          productId
          productName
          brand
          linkText
          items {
            itemId
            name
            sellers {
              sellerId
              commertialOffer {
                Price
                ListPrice
                AvailableQuantity
              }
            }
          }
        }
      }
    }
    """

    def crawl(self):
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        all_products = []
        # We can implement pagination or categories here.
        # For simplicity, let's try a broad search or specific category if needed.
        # Check if faceting is needed. "Proteina" might be a facet.

        # Facet for 'Proteina' -> Usually requires checking URL structure: /proteina
        # Or we can just list EVERYTHING by not filtering too strictly?
        # Let's try iterating pages of a broad search.

        start = 0
        step = 50

        # Category Facet: "cluster" or "category-1"
        # Using a reliable category ID or slug is safer.
        # Let's assume we want "Proteinas"

        while True:
            end = start + step - 1

            variables = {
                "from": start,
                "to": end,
                "orderBy": "OrderByScoreDESC",  # or OrderByPriceDESC
                "selectedFacets": [
                    # If we leave empty, it might search all.
                    # Filtering generally yields better results but requires knowing facets.
                ],
            }

            # If we don't pass facets, it searches whole store

            try:
                # Need to hash query if using GET persisted, but POST works often
                payload = {"query": self.GRAPHQL_QUERY, "variables": variables}

                # IMPORTANT: Calculate SHA256 if standard requests fail,
                # but let's try raw POST first.

                response = requests.post(
                    self.API_ENDPOINT,
                    json=payload,
                    headers=self.get_headers(),
                    timeout=30,
                )

                if response.status_code != 200:
                    logger.error(f"GraphQL Error: {response.text}")
                    break

                data = response.json()

                # Check for errors in body
                if "errors" in data:
                    logger.error(f"GraphQL Body Errors: {data['errors']}")
                    break

                # Item Path: data -> products -> products
                products = (
                    data.get("data", {}).get("productSearch", {}).get("products", [])
                )

                if not products:
                    break

                for item in products:
                    try:
                        processed = self._process_item(item)
                        if processed:
                            all_products.append(processed)
                    except Exception as e:
                        logger.debug(f"Item error: {e}")

                # Determine when to stop
                if len(products) < step:
                    break

                start += step
                self.sleep_random(1, 2)

            except Exception as e:
                logger.error(f"Crawl error: {e}")
                break

        return all_products

    def _process_item(self, item):
        try:
            pid = item.get("productId")
            name = item.get("productName")
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            # SKUs
            items_list = item.get("items", [])
            if not items_list:
                return None

            first_sku = items_list[0]

            sellers = first_sku.get("sellers", [])
            if not sellers:
                return None

            offer = sellers[0].get("commertialOffer", {})
            price = offer.get("Price")
            stock = offer.get("AvailableQuantity", 0)

            if not price:
                return None

            return {
                "item_id": str(pid),
                "item_name": name,
                "price": float(price),
                "item_brand": self.BRAND_NAME,
                "item_list_name": "proteina",  # Default bucket for search results
                "url": url,
                "stock": int(stock),
            }

        except Exception:
            return None
