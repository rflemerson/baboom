import json
import logging
import os

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class BlackSkullSpider(BaseSpider):
    def crawl(self):
        url = "https://www.blackskullusa.com.br/proteinas"
        logger.info(f"Starting crawl for {url} using Playwright...")

        with sync_playwright() as p:
            cdp_url = os.getenv("PLAYWRIGHT_CDP_URL", "http://localhost:9222")
            try:
                browser = p.chromium.connect_over_cdp(cdp_url)
                logger.info(f"Connected to CDP at {cdp_url}...")
                context = browser.contexts[0]
                page = context.new_page()
            except Exception as e:
                logger.error(f"Could not connect to browser: {e}")
                return []

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logger.error(f"Navigation failed: {e}")
                return []

            logger.info(f"Page Title: {page.title()}")

            # Auto-scroll for VTEX lazy loading
            self._auto_scroll(page)

            # Extract DataLayer
            try:
                # Wait a bit for final events
                page.wait_for_timeout(2000)
                data_layer = page.evaluate("window.dataLayer")
            except Exception as e:
                logger.error(f"Failed to get dataLayer: {e}")
                return []

            # Let's extract from view_item_list or productImpression
            dl_products = []
            for entry in data_layer:
                # Check for view_item_list (GA4)
                if entry.get("event") == "view_item_list":
                    ecommerce = entry.get("ecommerce", {})
                    if ecommerce and "items" in ecommerce:
                        dl_products.extend(ecommerce["items"])

                # Check for productImpression (Universal Analytics)
                elif entry.get("event") == "productImpression":
                    ecommerce = entry.get("ecommerce", {})
                    if ecommerce and "impressions" in ecommerce:
                        dl_products.extend(ecommerce["impressions"])

            logger.info(f"Found {len(dl_products)} items in dataLayer.")

            soup = BeautifulSoup(page.content(), "lxml")

            # Standardize products
            unique_products = {}
            for p in dl_products:
                # CMS dependent field names
                pid = str(p.get("item_id") or p.get("id"))
                name = p.get("item_name") or p.get("name")
                price = p.get("price")
                brand = p.get("item_brand") or p.get("brand") or "Black Skull"
                category = p.get("item_category") or p.get("category")

                if not pid or not name:
                    continue

                if pid not in unique_products:
                    unique_products[pid] = {
                        "item_id": pid,
                        "item_name": name,
                        "price": price,
                        "item_brand": brand,
                        "item_list_name": category,
                        "url": "",  # To be filled
                    }

            # Fallback: Extract from LD+JSON for URLs, they are reliable there
            ld_json_scripts = soup.find_all("script", type="application/ld+json")
            for script in ld_json_scripts:
                try:
                    data = json.loads(script.string)
                    if data.get("@type") == "ItemList" and "itemListElement" in data:
                        for item in data["itemListElement"]:
                            item_data = item.get("item", {})
                            p_name = item_data.get("name")
                            p_url = item_data.get("url")

                            if not p_name or not p_url:
                                continue

                            # Find matching product in our dict by name match
                            for _, p in unique_products.items():
                                # Simple normalization for match
                                if (
                                    p["item_name"].strip().lower()
                                    == p_name.strip().lower()
                                ):
                                    p["url"] = p_url
                except Exception as e:
                    logger.debug(f"Error enriching data with LD+JSON: {e}")

            # Final Fallback for missing URLs
            final_items = []
            for p in unique_products.values():
                if not p["url"]:
                    logger.warning(
                        f"Product {p['item_name']} missing URL. Using fallback."
                    )
                    # Fallback to search result or just category
                    p["url"] = (
                        f"https://www.blackskullusa.com.br/busca?ft={p['item_name'].replace(' ', '%20')}"
                    )

                final_items.append(p)

            return final_items

    def _auto_scroll(self, page):
        logger.info("Scrolling to bottom...")
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
                    }, 50);
                });
            }
        """)
        page.wait_for_timeout(2000)
