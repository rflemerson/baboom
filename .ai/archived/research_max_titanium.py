import json
import logging
import os

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_URL = "https://www.maxtitanium.com.br/proteinas-e-aminoacidos"
API_TEST_URL = "https://www.maxtitanium.com.br/api/catalog_system/pub/products/search/proteinas-e-aminoacidos?_from=0&_to=5"


def run():
    with sync_playwright() as p:
        cdp_url = os.getenv("PLAYWRIGHT_CDP_URL", "http://localhost:9222")
        logger.info(f"Connecting to {cdp_url}")
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.new_page()

        logger.info(f"Navigating to {TARGET_URL}")
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning(f"Navigation error: {e}")

        logger.info(f"Title: {page.title()}")

        # 1. API Test (Broader Search)
        try:
            # Try searching by term "whey" instead of category slug
            api_url = "https://www.maxtitanium.com.br/api/catalog_system/pub/products/search/whey?_from=0&_to=5"
            logger.info(f"Testing API: {api_url}")
            response = page.request.get(api_url)
            if response.status == 200:
                print("\n=== VTEX API SUCCESS (Search: 'whey') ===")
                data = response.json()
                print(f"Items found: {len(data)}")
                if len(data) > 0:
                    print(json.dumps(data[0], default=str)[:1000])
            else:
                print(f"VTEX API Failed: {response.status}")
        except Exception as e:
            print(f"API Check Error: {e}")

        # 2. Dump HTML Variables (Find Category ID)
        try:
            # Look for common VTEX variables in head
            content = page.content()
            if "skuJson" in content:
                print("\nFound 'skuJson' in HTML")
            if "vtex.events" in content:
                print("Found 'vtex.events' in HTML")

            # Try to grab category ID from some global var
            cat_id = page.evaluate(
                "window.vtex && window.vtex.categoryId ? window.vtex.categoryId : 'Not Found'"
            )
            print(f"Window VTEX Category ID: {cat_id}")

        except Exception as e:
            logger.error(f"HTML analysis error: {e}")

        page.close()
        browser.close()


if __name__ == "__main__":
    run()
