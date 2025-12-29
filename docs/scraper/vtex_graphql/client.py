import base64
import json
import logging

import requests

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VtexGraphQLAPI:
    """
    Documentation and Testing Script for VTEX IO GraphQL API.
    Specifically for Black Skull (using Persisted Queries).
    """

    BASE_URL = "https://www.blackskullusa.com.br"
    ENDPOINT = "/_v/segment/graphql/v1"

    # SHA256 Hash for the 'Products' query in Black Skull
    QUERY_HASH = "ee2478d319404f621c3e0426e79eba3997665d48cb277a53bf0c3276e8e53c22"

    def test_category_query(self, category_slug="proteina"):
        logger.info(f"--- Testing GraphQL Query for Category: {category_slug} ---")

        # 1. Variables
        # "category" variable expects the slug (e.g., "proteina")
        variables = {
            "category": category_slug,
            "specificationFilters": [],
            "collection": "",
            "orderBy": "OrderByPriceDESC",
            "from": 0,
            "to": 4,  # Fetch 5 items
            "hideUnavailableItems": True,
        }

        # 2. Extensions (Persisted Query + Variables)
        extensions = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": self.QUERY_HASH,
                "sender": "vtex.store-resources@0.x",
                "provider": "vtex.search-graphql@0.x",
            },
            "variables": base64.b64encode(json.dumps(variables).encode("utf-8")).decode(
                "utf-8"
            ),
        }

        params = {
            "workspace": "master",  # Usually 'master'
            "maxAge": "short",
            "appsEtag": "remove",
            "domain": "store",
            "locale": "pt-BR",
            "operationName": "Products",  # Matches the query name associated with the hash
            "extensions": json.dumps(extensions),
        }

        url = f"{self.BASE_URL}{self.ENDPOINT}"
        logger.info(f"URL: {url}")

        try:
            response = requests.get(url, params=params, timeout=15)
            logger.info(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                # Check for Errors
                if "errors" in data:
                    logger.error(f"GraphQL Errors: {data['errors']}")
                    return

                # Parse Response (Robust Logic)
                products_list = []

                # Check 1: data -> productSearch -> products
                p_search = data.get("data", {}).get("productSearch")
                if p_search and isinstance(p_search, dict):
                    products_list = p_search.get("products", [])

                # Check 2: data -> products
                if not products_list:
                    p_direct = data.get("data", {}).get("products")
                    if isinstance(p_direct, list):
                        products_list = p_direct
                    elif isinstance(p_direct, dict):
                        products_list = p_direct.get("products", [])

                logger.info(f"Products Found: {len(products_list)}")

                if products_list:
                    first = products_list[0]
                    logger.info(
                        f"Sample Item: {first.get('productName')} (ID: {first.get('productId')})"
                    )

                    # Extract Price/Stock
                    items = first.get("items", [])
                    if items:
                        seller = items[0].get("sellers", [])[0]
                        price = seller.get("commertialOffer", {}).get("Price")
                        stock = seller.get("commertialOffer", {}).get(
                            "AvailableQuantity"
                        )
                        logger.info(f"  > Price: {price} | Stock: {stock}")

            else:
                logger.warning(f"Request Failed: {response.text[:200]}")

        except Exception as e:
            logger.error(f"Error: {e}")
        logger.info("\n")


if __name__ == "__main__":
    api = VtexGraphQLAPI()
    api.test_category_query()
    api.test_category_query("creatina")
