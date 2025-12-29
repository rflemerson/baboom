import logging
from typing import Any

import requests

from ..services import ScraperService
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class VtexSearchSpider(BaseSpider):
    """
    Base Spider for VTEX Legacy / Search API stores.
    """

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
            pid = item.get("productId")
            name = item.get("productName")

            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            skus = item.get("items", [])
            if not skus:
                return None

            first_sku = None
            for sku_chem in skus:
                sellers_chem = sku_chem.get("sellers", [])
                for seller in sellers_chem:
                    if seller.get("sellerDefault"):
                        first_sku = sku_chem
                        break
                if first_sku:
                    break

            if not first_sku:
                first_sku = skus[0]

            sellers = first_sku.get("sellers", [])
            active_seller = None

            for seller in sellers:
                if seller.get("sellerDefault"):
                    active_seller = seller
                    break

            if not active_seller and sellers:
                active_seller = sellers[0]

            if not active_seller:
                return None

            ean = first_sku.get("ean", "")
            sku_code = first_sku.get("itemId", "")

            comm_offer = active_seller.get("commertialOffer", {})
            price = comm_offer.get("Price")

            stock_quantity = comm_offer.get("AvailableQuantity")
            try:
                stock_quantity = (
                    int(stock_quantity) if stock_quantity is not None else 0
                )
            except (ValueError, TypeError):
                stock_quantity = 0

            from ..models import ScrapedItem

            if stock_quantity > 0:
                stock_status = ScrapedItem.StockStatus.AVAILABLE
            else:
                stock_status = ScrapedItem.StockStatus.OUT_OF_STOCK

            if price is None:
                return None

            store_slug = self.STORE_SLUG
            if not store_slug:
                store_slug = self.BRAND_NAME.lower().replace(" ", "_")

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
