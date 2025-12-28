import logging
import os

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_URL = "https://www.gsuplementos.com.br/whey-protein/"


def run():
    with sync_playwright() as p:
        cdp_url = os.getenv("PLAYWRIGHT_CDP_URL", "http://localhost:9222")
        logger.info(f"Connecting to {cdp_url}")
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.new_page()

        logger.info(f"Navigating to {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="networkidle")

        # 1. Look for Total Count Text
        # "Exibindo 1 de 20 de 50 produtos" or similar
        try:
            # Common selectors for counts
            count_text = page.evaluate("document.body.innerText")
            # simplistic search for "produtos" lines
            import re

            matches = re.findall(r"(\d+)\s+produtos", count_text, re.IGNORECASE)
            print(f"\nPotential Product Counts finding in text: {matches}")

            # Try specific selectors if known (Growth usually uses .sub-titulo or .quantidade-produtos)
            # Let's dump likely elements
            selectors = [
                ".quantidade-produtos",
                ".sub-titulo",
                ".toolbar-amount",
                ".pager",
            ]
            for sel in selectors:
                if page.locator(sel).count() > 0:
                    print(f"Selector '{sel}': {page.locator(sel).first.inner_text()}")

        except Exception as e:
            logger.error(f"Error checking count: {e}")

        # 2. Check DataLayer count vs DOM count
        try:
            # Wait for dataLayer to be defined
            page.wait_for_function("() => window.dataLayer !== undefined", timeout=5000)

            dl_count = page.evaluate("""
                window.dataLayer
                .filter(e => e.event === 'view_item_list')
                .reduce((acc, e) => acc + (e.ecommerce && e.ecommerce.items ? e.ecommerce.items.length : 0), 0)
             """)
            print(f"\nDataLayer Items Count: {dl_count}")

            dom_count = page.locator(
                ".vitrine-produto, .product-item, .prod-wrapper"
            ).count()
            print(f"DOM Product Elements Count: {dom_count}")
        except Exception as e:
            print(f"Count Error: {e}")

        # 3. Check Pagination
        try:
            # Check for "Ver mais produtos" button (common in Growth)
            ver_mais = page.locator(
                "button:has-text('Ver mais'), a:has-text('Ver mais'), .btn-load-more"
            ).first
            if ver_mais.count() > 0:
                print(f"\nFound 'Ver mais' button: {ver_mais.inner_text()}")
            else:
                print("\nNo 'Ver mais' button found.")

            # Check hidden total count input
            total_hidden = page.locator("input#TotalProdutos, #TotalItems").first
            if total_hidden.count() > 0:
                print(f"Hidden Total Input: {total_hidden.get_attribute('value')}")

        except Exception as e:
            print(f"Pagination error: {e}")

        page.close()
        browser.close()


if __name__ == "__main__":
    run()
