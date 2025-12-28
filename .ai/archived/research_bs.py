import json
import logging
import os

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Likely Category URL
TARGET_URL = "https://www.blackskullusa.com.br/proteinas"


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

        # 1. Dump dataLayer
        try:
            # Wait for dataLayer to populate
            page.wait_for_timeout(3000)
            data_layer = page.evaluate("window.dataLayer")

            print("\n=== DataLayer Dump (Head 3 items) ===")
            # Try to find product list events
            found_products = False
            for entry in data_layer:
                # Look for common ecommerce keys
                s = json.dumps(entry, default=str)
                if "ecommerce" in s or "items" in s:
                    print(
                        json.dumps(entry, indent=2, ensure_ascii=False, default=str)[
                            :2000
                        ]
                        + "..."
                    )
                    found_products = True

            if not found_products:
                print("No obvious ecommerce events found in dataLayer.")
                # Print everything small
                # print(json.dumps(data_layer, indent=2, default=str))

        except Exception as e:
            logger.error(f"dataLayer error: {e}")

        # 2. Check VTEX (Black Skull might use VTEX)
        try:
            vtex = page.evaluate("window.vtex")
            if vtex:
                print("\n=== VTEX Detected ===")
                # VTEX usually has `vtexjs` or `skuJson`
        except:
            pass

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
