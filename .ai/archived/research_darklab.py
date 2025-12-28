import json
import logging

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Likely URL structure
CATEGORY_URL = "https://www.darklabsuplementos.com.br/whey-protein"
# Shopify API
SHOPIFY_JSON_URL = "https://www.darklabsuplementos.com.br/products.json?limit=5"


def run():
    print(f"1. Testing Shopify products.json: {SHOPIFY_JSON_URL}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(SHOPIFY_JSON_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            print("\n=== SHOPIFY API SUCCESS ===")
            data = response.json()
            products = data.get("products", [])
            print(f"Items found: {len(products)}")
            if len(products) > 0:
                print(json.dumps(products[0], default=str)[:1000])
        else:
            print(f"Shopify Endpoint Failed: {response.status_code}")
    except Exception as e:
        print(f"API Check Error: {e}")


if __name__ == "__main__":
    run()
