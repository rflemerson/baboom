import logging
from typing import Any

import requests

from ..models import ScrapedItem
from ..services import ScraperService
from ..types import ProductIngestionInput
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class DarkLabSpider(BaseSpider):
    """Spider for Dark Lab (Shopify API)."""

    BRAND_NAME = "Dark Lab"
    STORE_SLUG = "dark_lab"
    BASE_URL = "https://www.darklabsuplementos.com.br"

    API_COLLECTIONS = "https://www.darklabsuplementos.com.br/collections.json"

    FALLBACK_CATEGORIES = [
        "best-sellers",
        "whey-protein",
        "creatina",
        "pre-treino",
        "hipercalorico",
        "aminoacidos",
        "acessorios",
        "kits",
        "vegan",
        "vitaminas",
    ]

    def get_headers(self) -> dict[str, str]:
        """Get API headers."""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
        }

    def _fetch_categories(self) -> list[str]:
        try:
            logger.info("Fetching categories for Dark Lab...")
            response = requests.get(
                self.API_COLLECTIONS, headers=self.get_headers(), timeout=15
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch collections: {response.status_code}")
                return []

            data = response.json()
            collections = data.get("collections", [])

            handles = []
            for collection in collections:
                handle = collection.get("handle")
                if handle:
                    handles.append(handle)

            return handles

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def crawl(self) -> list[Any]:
        """Crawl products from API."""
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")
        all_products = []
        processed_ids = set()

        categories = self._fetch_categories()
        self.check_category_discrepancy(categories, self.FALLBACK_CATEGORIES)

        if not categories:
            logger.info("No dynamic categories found, using fallback/config.")
            categories = self.categories_to_crawl or self.FALLBACK_CATEGORIES

        logger.info(f"Discovered {len(categories)} categories to crawl.")

        for category in categories:
            logger.info(f"Crawling Category: {category}")
            collection_endpoint = (
                f"{self.BASE_URL}/collections/{category}/products.json"
            )

            page = 1
            limit = 250

            while True:
                params = {"page": page, "limit": limit}

                try:
                    response = requests.get(
                        collection_endpoint,
                        params=params,
                        headers=self.get_headers(),
                        timeout=30,
                    )

                    if response.status_code != 200:
                        logger.error(
                            f"Error fetching {category} page {page}: {response.status_code}"
                        )
                        break

                    data = response.json()
                    products = data.get("products", [])

                    if not products:
                        break

                    items_in_page = 0
                    for item in products:
                        try:
                            item_id = str(item.get("id"))
                            if item_id in processed_ids:
                                continue

                            processed_ids.add(item_id)

                            saved_obj = self._process_and_save(item, category)
                            if saved_obj:
                                all_products.append(saved_obj)
                                items_in_page += 1
                        except Exception as e:
                            logger.debug(f"Item error in {category}: {e}")

                    if len(products) < limit:
                        break

                    page += 1
                    self.sleep_random(0.5, 1.5)

                except Exception as e:
                    logger.error(f"Crawl error for {category}: {e}")
                    break

        logger.info(f"Crawl finished. Total products: {len(all_products)}")
        return all_products

    def _process_and_save(self, item: dict, category: str) -> Any | None:
        try:
            pid = str(item.get("id"))
            name = item.get("title")
            handle = item.get("handle")
            url = f"{self.BASE_URL}/products/{handle}" if handle else ""

            variants = item.get("variants", [])
            if not variants:
                return None

            selected_variant = variants[0]
            for v in variants:
                if v.get("available"):
                    selected_variant = v
                    break

            price = selected_variant.get("price")

            is_available = selected_variant.get("available")
            inventory_quantity = selected_variant.get("inventory_quantity")

            if inventory_quantity is not None:
                stock_quantity = int(inventory_quantity)
            else:
                stock_quantity = 100 if is_available else 0

            if is_available:
                stock_status = ScrapedItem.StockStatus.AVAILABLE
            else:
                stock_status = ScrapedItem.StockStatus.OUT_OF_STOCK
                stock_quantity = 0

            ean = selected_variant.get("barcode")
            sku = str(selected_variant.get("id", ""))

            if not price:
                return None

            input_data = ProductIngestionInput(
                store_slug=self.STORE_SLUG,
                external_id=pid,
                url=url,
                name=str(name) if name else "",
                price=float(price),
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean=str(ean) if ean else "",
                sku=sku,
                pid=pid,
                category=category,
            )
            return ScraperService.save_product(input_data)

        except Exception as e:
            logger.warning(f"Item parse error: {e}")
            return None
