import logging
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from ..models import ScrapedItem
from ..services import ScraperService
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class SoldiersSpider(BaseSpider):
    """Spider for Soldiers Nutrition."""

    BRAND_NAME = "Soldiers Nutrition"
    STORE_SLUG = "soldiers_nutrition"
    BASE_URL = "https://www.soldiersnutrition.com.br"

    FALLBACK_CATEGORIES = [
        "creatina",
        "whey-protein-soldiers",
        "glutamina",
        "pre-treino",
        "vitaminas-e-minerais",
        "acessorios",
    ]

    def _discover_categories(self) -> list[str]:
        """Discover categories from homepage navigation."""
        logger.info("Discovering categories from homepage...")
        categories = set()
        try:
            response = requests.get(
                self.BASE_URL, headers=self.get_headers(), timeout=15
            )
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "lxml")
                # Selector for Top Level Menu Items in Loja Integrada themes
                headers = soup.select(".menu.superior .nivel-um > li > a")

                for a_tag in headers:
                    href = a_tag.get("href")
                    if href and isinstance(href, str) and self.BASE_URL in href:
                        slug = href.replace(f"{self.BASE_URL}/", "").strip("/")
                        # Filter out common non-product pages
                        if slug and not any(
                            x in slug
                            for x in [
                                "conta",
                                "carrinho",
                                "pagina",
                                "checkout",
                                "ocultar",
                            ]
                        ):
                            categories.add(slug)

            logger.info(f"Discovered {len(categories)} categories: {categories}")
        except Exception as e:
            logger.error(f"Error discovering categories: {e}")

        return list(categories) if categories else self.FALLBACK_CATEGORIES

    def _fetch_product_links(self, category_slug: str) -> list[str]:
        """Fetch all product links for a category."""
        product_links = []
        page_num = 1

        while True:
            category_url = f"{self.BASE_URL}/{category_slug}?pagina={page_num}"
            logger.info(f"Fetching links from: {category_url}")

            try:
                response = requests.get(
                    category_url, headers=self.get_headers(), timeout=15
                )
                if response.status_code != 200:
                    logger.warning(
                        f"Failed to fetch {category_url}: {response.status_code}"
                    )
                    break

                soup = BeautifulSoup(response.text, "lxml")
                items = soup.select(".listagem-item")
                if not items:
                    logger.info(f"No more items found on page {page_num}.")
                    break

                new_links = 0
                for item in items:
                    a_tag = item.select_one("a.produto-sobrepor")
                    href = a_tag.get("href") if a_tag else None
                    if href and isinstance(href, str):
                        full_url = urljoin(self.BASE_URL, href)
                        if full_url not in product_links:
                            product_links.append(full_url)
                            new_links += 1

                if new_links == 0:
                    logger.info("No new links found on this page, stopping pagination.")
                    break

                logger.info(f"Found {new_links} products on page {page_num}.")
                page_num += 1
                self.sleep_random(0.5, 1.5)

            except Exception as e:
                logger.error(f"Error fetching links for {category_slug}: {e}")
                break

        return product_links

    def crawl(self) -> list[Any]:
        """Crawl products using Playwright."""
        logger.info(f"Starting Browser Crawl for {self.BRAND_NAME}...")
        all_products = []
        raw_items: list[dict[str, Any]] = []

        url_to_categories: dict[str, list[str]] = {}
        unique_urls = set()

        category_slugs = self._discover_categories()

        for category in category_slugs:
            links = self._fetch_product_links(category)
            logger.info(f"Category '{category}' has {len(links)} products.")
            for link in links:
                unique_urls.add(link)
                if link not in url_to_categories:
                    url_to_categories[link] = []
                url_to_categories[link].append(category)

        logger.info(f"Total unique products to scrape: {len(unique_urls)}")

        if not unique_urls:
            return []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = browser.new_context(user_agent=self.user_agents[0])
            page = context.new_page()

            logger.info(f"Processing {len(unique_urls)} unique products...")

            for url in unique_urls:
                product_data = self._scrape_product_page(page, url)
                if product_data:
                    primary_category = url_to_categories[url][0]

                    raw_items.append(
                        {"data": product_data, "category": primary_category, "url": url}
                    )

                self.sleep_random(1, 2)

            browser.close()

        logger.info(f"Browser phase finished. Saving {len(raw_items)} items to DB...")

        for item in raw_items:
            saved = self._process_and_save(item["data"], item["category"], item["url"])
            if saved:
                all_products.append(saved)

        logger.info(f"Crawl finished. Total products saved: {len(all_products)}")
        return all_products

    def _scrape_product_page(self, page, url: str) -> dict | None:
        """Extract product data from page using DataLayer."""
        try:
            logger.debug(f"Navigating to {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            is_out_of_stock = (
                page.locator(".produto-indisponivel, .alert-danger").count() > 0
            )

            data_layer = page.evaluate("() => window.LIgtagDataLayer")

            if not data_layer:
                logger.warning(f"LIgtagDataLayer not found for {url}")
                return None

            target_data = {}
            if isinstance(data_layer, list):
                for item in data_layer:
                    found_items = []

                    if (
                        isinstance(item, dict)
                        and item.get("1") == "view_item"
                        and isinstance(item.get("2"), dict)
                    ):
                        found_items = item.get("2", {}).get("items", [])
                    elif isinstance(item, dict) and item.get("event") == "view_item":
                        if "ecommerce" in item:
                            found_items = item.get("ecommerce", {}).get("items", [])
                        elif "items" in item:
                            found_items = item.get("items", [])

                    if found_items and len(found_items) > 0:
                        target_data = found_items[0]
                        break

            elif isinstance(data_layer, dict):
                target_data = data_layer

            if not target_data:
                logger.warning(
                    f"No valid product object found in LIgtagDataLayer for {url}"
                )
                return None

            target_data["dom_stock_available"] = not is_out_of_stock

            return target_data

        except Exception as e:
            logger.error(f"Browser error scraping {url}: {e}")
            return None

    def _process_and_save(self, data: dict, category_name: str, url: str) -> Any | None:
        """Process extracted data and save product."""
        try:
            pid = data.get("item_id")
            sku = data.get("item_sku")
            name = data.get("item_name")

            price = data.get("price")
            if price is None:
                price = data.get("promotional_price")

            if not price:
                logger.warning(f"No price found for {url}")
                return None

            dom_available = data.get("dom_stock_available", True)

            stock_status = (
                ScrapedItem.StockStatus.AVAILABLE
                if dom_available
                else ScrapedItem.StockStatus.OUT_OF_STOCK
            )
            stock_quantity = 100 if dom_available else 0

            return ScraperService.save_product(
                store_slug=self.STORE_SLUG,
                external_id=str(pid),
                url=url,
                name=str(name) if name else "",
                price=float(price),
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean="",
                sku=str(sku),
                pid=str(pid),
                category=category_name,
            )

        except Exception as e:
            logger.error(f"Error processing item for {url}: {e}")
            return None
