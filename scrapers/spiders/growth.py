import logging
import os

from playwright.sync_api import sync_playwright

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class GrowthSpider(BaseSpider):
    BASE_URL = "https://www.gsuplementos.com.br/whey-protein/"

    def crawl(self, url=None):
        target_url = url or self.BASE_URL
        cdp_url = os.getenv("PLAYWRIGHT_CDP_URL", "http://localhost:9222")
        logger.info(f"Starting crawl for {target_url} using Playwright...")

        products = []

        try:
            with sync_playwright() as p:
                # Connect to the remote browser (WSL2 Host)
                # Ensure Chrome is running with --remote-debugging-port=9222
                logger.info(f"Connecting to CDP at {cdp_url}...")
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0]
                page = context.new_page()

                logger.info(f"Navigating to {target_url}")
                page.goto(
                    target_url, wait_until="domcontentloaded"
                )  # Faster than networkidle sometimes

                title = page.title()
                logger.info(f"Page Title: {title}")

                # Auto-scroll to ensure lazy-loaded items are triggered
                logger.info("Scrolling to bottom to load all products...")
                page.evaluate("""
                    async () => {
                        await new Promise((resolve) => {
                            var totalHeight = 0;
                            var distance = 100;
                            var timer = setInterval(() => {
                                var scrollHeight = document.body.scrollHeight;
                                window.scrollBy(0, distance);
                                totalHeight += distance;

                                if(totalHeight >= scrollHeight - window.innerHeight){
                                    clearInterval(timer);
                                    resolve();
                                }
                            }, 100);
                        });
                    }
                """)
                # Wait a bit for final lazy loads
                page.wait_for_timeout(2000)

                # Wait for dataLayer explicitly
                try:
                    page.wait_for_function(
                        "() => window.dataLayer !== undefined", timeout=10000
                    )
                except Exception:
                    logger.warning("Timed out waiting for window.dataLayer definition.")

                # Extract dataLayer
                data_layer = page.evaluate("window.dataLayer")

                if data_layer is None:
                    logger.error(
                        "dataLayer is None! Page might not have loaded correctly or blocked."
                    )
                else:
                    logger.info(f"dataLayer raw type: {type(data_layer)}")
                    # Parse for 'view_item_list' event
                    for entry in data_layer:
                        if entry.get("event") == "view_item_list":
                            items = entry.get("ecommerce", {}).get("items", [])
                            logger.info(f"Found {len(items)} items in dataLayer.")
                            products.extend(items)

                page.close()
                browser.close()

        except Exception as e:
            logger.error(f"Playwright Crawl Failed: {e}")
            return []

        return products
