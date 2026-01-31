import logging
from typing import Any

import requests

from ..models import ScrapedItem
from ..services import ScraperService
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class VtexSearchSpider(BaseSpider):
    """Base Spider for VTEX Legacy / Search API stores."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    API_TREE = ""

    FALLBACK_CATEGORIES: list[str] = []

    def _fetch_categories(self) -> list[str]:
        try:
            resp = requests.get(self.API_TREE, headers=self.get_headers(), timeout=10)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch category tree: {resp.status_code}")
                return []

            tree = resp.json()
            slugs = set()

            def extract_slugs(nodes: list[dict]) -> None:
                for node in nodes:
                    url = node.get("url", "")
                    if url:
                        url = url.rstrip("/")
                        slug = url.split("/")[-1]
                        if slug:
                            slugs.add(slug)

                    if "children" in node:
                        extract_slugs(node["children"])

            extract_slugs(tree)
            return list(slugs)

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def crawl(self) -> list[Any]:
        """Crawl products from API."""
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        categories = self._fetch_categories()
        self.check_category_discrepancy(categories, self.FALLBACK_CATEGORIES)

        if not categories:
            logger.info("Using Fallback Categories.")
            categories = self.FALLBACK_CATEGORIES

        logger.info(f"Discovered {len(categories)} categories to crawl.")

        all_products = []
        processed_ids = set()

        for category_slug in categories:
            logger.info(f"Crawling Category: {category_slug}")
            search_url = f"{self.BASE_URL}/api/catalog_system/pub/products/search/{category_slug}"

            start = 0
            step = 50

            while True:
                end = start + step - 1
                params = {"_from": start, "_to": end}

                try:
                    response = requests.get(
                        search_url,
                        params=params,
                        headers=self.get_headers(),
                        timeout=30,
                    )

                    if response.status_code not in [200, 206]:
                        break

                    data = response.json()
                    if not data:
                        break

                    items_in_page = 0
                    for item in data:
                        try:
                            item_id = str(item.get("productId"))
                            if item_id in processed_ids:
                                continue

                            processed_ids.add(item_id)

                            saved_obj = self._process_and_save(item, category_slug)
                            if saved_obj:
                                all_products.append(saved_obj)
                                items_in_page += 1
                        except Exception as e:
                            logger.debug(f"Skipping item: {e}")

                    if len(data) < step:
                        break

                    start += step
                    self.sleep_random(0.5, 1.0)

                except Exception as e:
                    logger.error(f"Error crawling {category_slug}: {e}")
                    break

        logger.info(f"Crawl finished. Total products: {len(all_products)}")
        return all_products

    def _process_and_save(self, item: dict, category: str) -> Any | None:
        try:
            skus = item.get("items", [])
            if not skus:
                return None

            first_sku = self._extract_first_sku(skus)
            if not first_sku:
                return None

            active_seller = self._select_active_seller(first_sku)
            if not active_seller:
                return None

            comm_offer = active_seller.get("commertialOffer", {})
            price = comm_offer.get("Price")
            if price is None:
                return None

            pid = item.get("productId")
            name = item.get("productName")
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            ean = first_sku.get("ean", "")
            sku_code = first_sku.get("itemId", "")

            stock_quantity = self._parse_stock(comm_offer.get("AvailableQuantity"))
            stock_status = (
                ScrapedItem.StockStatus.AVAILABLE
                if stock_quantity > 0
                else ScrapedItem.StockStatus.OUT_OF_STOCK
            )

            store_slug = self.STORE_SLUG or self.BRAND_NAME.lower().replace(" ", "_")

            return ScraperService.save_product(
                store_slug=store_slug,
                external_id=str(pid),
                url=url,
                name=str(name) if name else "",
                price=float(price),
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean=str(ean),
                sku=str(sku_code),
                pid=str(pid),
                category=category,
            )
        except Exception as e:
            logger.debug(f"Item parse error: {e}")
            return None

    def _extract_first_sku(self, skus: list[dict]) -> dict | None:
        """Find the first valid SKU with a default seller."""
        for sku_chem in skus:
            sellers_chem = sku_chem.get("sellers", [])
            for seller in sellers_chem:
                if seller.get("sellerDefault"):
                    return sku_chem
        return skus[0] if skus else None

    def _select_active_seller(self, sku: dict) -> dict | None:
        """Select the active seller for the SKU."""
        sellers = sku.get("sellers", [])
        for seller in sellers:
            if seller.get("sellerDefault"):
                return seller
        return sellers[0] if sellers else None

    def _parse_stock(self, quantity: Any) -> int:
        """Parse stock quantity to integer."""
        try:
            return int(quantity) if quantity is not None else 0
        except (ValueError, TypeError):
            return 0
