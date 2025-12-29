import logging

import requests

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WapStoreAPI:
    """
    Documentation and Testing Script for Wap.Store V2 API (Growth Supplements).
    Based on research from .ai/growth.yaml and reverse engineering.
    """

    BASE_URL = "https://www.gsuplementos.com.br/api/v2/front"
    HEADERS = {
        "User-Agent": "insomnia/12.2.0",  # Required to bypass some WAF/Bot checks?
        "app-token": "wapstore",  # Public App Token
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Verify SSL is often irrelevant/problematic with Sucuri WAF for this specific site
    VERIFY_SSL = False

    def __init__(self):
        # Suppress insecure request warnings if verify=False
        requests.packages.urllib3.disable_warnings()  # type: ignore

    def test_endpoint(self, name, endpoint, params=None):
        url = f"{self.BASE_URL}{endpoint}"
        logger.info(f"--- Testing Endpoint: {name} ---")
        logger.info(f"URL: {url}")
        logger.info(f"Params: {params}")

        try:
            response = requests.get(
                url,
                headers=self.HEADERS,
                params=params,
                verify=self.VERIFY_SSL,
                timeout=15,
            )

            logger.info(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                # Try to output a summary of keys
                if isinstance(data, dict):
                    keys = list(data.keys())
                    logger.info(f"Response Keys: {keys}")

                    # Specific checks based on known structure
                    if "data" in data:
                        logger.info("found 'data' key.")
                    if "conteudo" in data:
                        logger.info("found 'conteudo' key (often contains 'produtos').")
                        if "produtos" in data["conteudo"]:
                            prods = data["conteudo"]["produtos"]
                            logger.info(f"Products Found: {len(prods)}")
                            if prods:
                                logger.info(f"Sample Product: {prods[0].get('nome')}")

            else:
                logger.warning(f"Response Body Preview: {response.text[:200]}")

        except Exception as e:
            logger.error(f"Error testing {name}: {e}")
        logger.info("\n")

    def run_tests(self):
        # 1. Menu Structure
        self.test_endpoint("Menu / Categories", "/struct/menus/menu-pitchbar/")

        # 2. Product Listing (Category)
        # "url" param is the category slug with slashes
        self.test_endpoint(
            "Product Listing (Category: /proteina/)",
            "/url/product/listing/category",
            params={"url": "/proteina/", "offset": 0, "limit": 5},
        )

        # 3. URL Verification
        self.test_endpoint(
            "URL Verification", "/url/verify", params={"url": "/creatina/"}
        )


if __name__ == "__main__":
    api = WapStoreAPI()
    api.run_tests()
