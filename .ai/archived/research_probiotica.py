import json
import logging

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Search URL Strategy (Success with Max Titanium)
API_TEST_URL = "https://www.probiotica.com.br/api/catalog_system/pub/products/search/whey?_from=0&_to=5"


def run():
    print(f"Testing API: {API_TEST_URL}")
    try:
        # Requests is faster than Playwright for API check
        response = requests.get(API_TEST_URL, timeout=10)
        if response.status_code == 200:
            print("\n=== VTEX API SUCCESS (Search: 'whey') ===")
            data = response.json()
            print(f"Items found: {len(data)}")
            if len(data) > 0:
                print(json.dumps(data[0], default=str)[:1000])
        else:
            print(f"VTEX API Failed: {response.status_code}")
    except Exception as e:
        print(f"API Check Error: {e}")


if __name__ == "__main__":
    run()
