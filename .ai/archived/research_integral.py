import json
import logging
import os

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Likely Category URL found via search or guess
TARGET_URL = "https://www.integralmedica.com.br/proteinas"


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
            # Scroll a bit
            page.mouse.wheel(0, 500)
        except Exception as e:
            logger.warning(f"Navigation error (continuing): {e}")

        logger.info(f"Title: {page.title()}")

        # 1. Dump dataLayer (Aggressive)
        try:
            # Wait for dataLayer to populate
            page.wait_for_timeout(3000)
            data_layer = page.evaluate("window.dataLayer")

            print(f"\n=== DataLayer Dump (Total {len(data_layer)}) ===")
            for i, entry in enumerate(data_layer):
                print(f"[{i}] {json.dumps(entry, default=str)[:300]}...")

        except Exception as e:
            logger.error(f"dataLayer error: {e}")

        # 2. Check VTEX Globals & API
        try:
            # Try to fetch products from VTEX API directly if possible
            # category path: /proteina (from breadcrumb)
            api_url = "https://www.integralmedica.com.br/api/catalog_system/pub/products/search/proteina?_from=0&_to=9"
            print(f"\n=== API Test: {api_url} ===")
            response = page.request.get(api_url)
            if response.status == 200:
                print("API SUCCESS! Found products via API.")
                print(str(response.json()[0])[:500])
            else:
                print(f"API Failed: {response.status}")

        except Exception as e:
            print(f"API Check Error: {e}")

        # 3. Dump Schema.org
        try:
            scripts = page.locator(
                'script[type="application/ld+json"]'
            ).all_inner_texts()
            print("\n=== LD+JSON Dump ===")
            for s in scripts:
                print(s[:500] + "...")
        except:
            pass

        page.close()
        browser.close()


if __name__ == "__main__":
    run()
