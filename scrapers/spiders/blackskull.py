import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class BlackSkullSpider(BaseSpider):
    BRAND_NAME = "Black Skull"
    BASE_URL = "https://www.blackskullusa.com.br"
    API_ENDPOINT = "https://www.blackskullusa.com.br/_v/segment/graphql/v1"
    API_TREE = "https://www.blackskullusa.com.br/api/catalog_system/pub/category/tree/3"

    # Updated Query with EAN + Context
    GRAPHQL_QUERY = """
    query productSearch($selectedFacets: [SelectedFacetInput], $from: Int, $to: Int, $orderBy: String) {
      productSearch(selectedFacets: $selectedFacets, from: $from, to: $to, orderBy: $orderBy, hideUnavailableItems: true, simulationBehavior: default) @context(provider: "vtex.search-graphql") {
        products {
          productId
          productName
          brand
          linkText
          items {
            itemId
            name
            ean
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

    def _fetch_categories(self):
        """
        Fetch dynamic categories from the VTEX Category Tree codebase.
        """
        try:
            logger.info("Fetching categories for Black Skull...")
            response = requests.get(
                self.API_TREE, headers=self.get_headers(), timeout=10
            )
            if response.status_code != 200:
                logger.error(f"Failed to fetch categories: {response.status_code}")
                return []

            categories = []
            for item in response.json():
                if item.get("hasChildren") or item.get("url"):
                    url = item.get("url", "")
                    # Extract last part of URL as slug
                    slug = url.split("/")[-1] if url else ""
                    if slug:
                        categories.append(slug)

            return categories

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def crawl(self):
        """
        Main crawl method: fetches categories and iterates over them using GraphQL facets.
        """
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")
        all_products = []

        categories = self._fetch_categories()
        if not categories:
            logger.info("No dynamic categories found, using fallback.")
            categories = [
                "proteina",
                "aminoacidos",
                "vitaminas",
                "vestuario",
                "acessorios",
                "kits",
            ]

        logger.info(f"Discovered {len(categories)} categories to crawl.")

        for category in categories:
            logger.info(f"Crawling Category: {category}")
            start = 0
            step = 50

            while True:
                end = start + step - 1

                # Facet for category is usually key="c" value="<slug>"
                variables = {
                    "from": start,
                    "to": end,
                    "orderBy": "OrderByScoreDESC",
                    "selectedFacets": [{"key": "c", "value": category}],
                }

                try:
                    payload = {"query": self.GRAPHQL_QUERY, "variables": variables}
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
                    if "errors" in data:
                        logger.error(f"GraphQL Body Errors: {data['errors']}")
                        break

                    products = (
                        data.get("data", {})
                        .get("productSearch", {})
                        .get("products", [])
                    )
                    if not products:
                        break

                    for item in products:
                        processed = self._process_item(item, category)
                        if processed:
                            all_products.append(processed)

                    # Determine when to stop
                    if len(products) < step:
                        break

                    start += step
                    self.sleep_random(0.5, 1.5)

                except Exception as e:
                    logger.error(f"Crawl error for {category}: {e}")
                    break

        return all_products

    def _process_item(self, item, category_name="proteina"):
        try:
            pid = item.get("productId")
            name = item.get("productName")
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

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

            ean = first_sku.get("ean", "")

            return {
                "item_id": str(pid),
                "item_name": name,
                "price": float(price),
                "item_brand": self.BRAND_NAME,
                "item_list_name": category_name,
                "url": url,
                "stock": int(stock),
                "ean": ean,
                "sku": first_sku.get("itemId", ""),
            }

        except Exception:
            return None
