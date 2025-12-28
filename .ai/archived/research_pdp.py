import json
import logging
import os

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_CATEGORY = "https://www.gsuplementos.com.br/whey-protein/"


def run():
    with sync_playwright() as p:
        # Connect to host chrome
        cdp_url = os.getenv("PLAYWRIGHT_CDP_URL", "http://localhost:9222")
        logger.info(f"Connecting to {cdp_url}")
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.new_page()

        # 1. Get a valid Product Link from Category
        logger.info(f"Navigating to Category: {TARGET_CATEGORY}")
        page.goto(TARGET_CATEGORY, wait_until="domcontentloaded")

        try:
            page.wait_for_function("() => window.dataLayer !== undefined", timeout=5000)
            data_layer = page.evaluate("window.dataLayer")

            # Find first product url
            product_url = None
            for entry in data_layer:
                if entry.get("event") == "view_item_list":
                    items = entry.get("ecommerce", {}).get("items", [])
                    if items:
                        # Sometimes URL is not in the item, but usually is or we can infer
                        # For now, let's grab the first item and see if we can find a link in the DOM if not in dataLayer
                        # Actually, Growth's dataLayer items usually have relative or full URLs?
                        # If not, we scrape the <a> tag based on the item name or just grab first .product-item a
                        pass
        except Exception:
            pass

        # Fallback: Scrape first href from DOM
        # Growth uses .vitrine-produto or similar. Let's try flexible selector
        product_url = page.evaluate("""() => {
            const link = document.querySelector('.vitrine-produto a.vitrine-produto-nome');
            return link ? link.href : null;
        }""")

        if not product_url:
            logger.warning("Specific selector failed. Dumping all candidate links...")
            links = page.evaluate(
                "Array.from(document.querySelectorAll('a')).map(a => a.href)"
            )
            candidates = [
                l for l in links if "gsuplementos.com.br" in l and "p9" in l
            ]  # 'p9' usually indicates product ID in slug

            if candidates:
                product_url = candidates[0]
                logger.info(f"Found candidate from dump: {product_url}")
            else:
                logger.error(
                    "No likely product links found. Dumping first 10 links for context:"
                )
                for l in links[:10]:
                    print(l)

                # Snapshot of HTML to debug
                # print(page.content()[:2000])
                return

        # 2. Navigate to PDP
        logger.info(f"Navigating to PDP: {product_url}")
        page.goto(product_url, wait_until="networkidle")
        # mask_all_requests is wrong, networkidle
        page.wait_for_load_state("networkidle")

        print(f"Title: {page.title()}")

        # 3. Dump dataLayer
        data_layer = page.evaluate("window.dataLayer")
        print("\n=== PDP dataLayer Dump ===")
        print(json.dumps(data_layer, indent=2, ensure_ascii=False, default=str))

        # 4. Dump ID+JSON
        scripts = page.locator('script[type="application/ld+json"]').all_inner_texts()
        print("\n=== PDP LD+JSON Dump ===")
        for s in scripts:
            print(s)

        # 5. Check Nutrition Table content
        # Growth often puts nutrition in a hidden tab or a table
        try:
            # Just dump text content of potential nutrition areas
            nutrition = page.locator(".tabela-nutricional, #tabela-nutricional").first
            if nutrition.count() > 0:
                print("\n=== Nutrition Table Text ===")
                print(nutrition.inner_text())
                print("\n=== Nutrition Table HTML ===")
                print(nutrition.inner_html()[:500])
            else:
                print("\nNo .tabela-nutricional found. Dumping <table>s...")
                for t in page.locator("table").all():
                    print(t.inner_text()[:200])
        except Exception as e:
            print(f"\nTable error: {e}")

        page.close()
        browser.close()


if __name__ == "__main__":
    run()
