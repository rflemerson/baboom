import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class VtexSearchSpider(BaseSpider):
    """
    Base Spider for VTEX Legacy / Search API stores.
    Handles dynamic category discovery via Tree API and standardized JSON parsing.
    """

    # Abstract attributes to be defined by subclasses
    BRAND_NAME = ""
    BASE_URL = ""
    API_TREE = ""
    # List of slugs to use if Tree API fails
    FALLBACK_CATEGORIES: list[str] = []

    def _fetch_categories(self):
        """
        Fetch dynamic category tree from VTEX API.
        Returns a list of category URL slugs (e.g. 'whey-protein', 'creatina').
        """
        try:
            resp = requests.get(self.API_TREE, headers=self.get_headers(), timeout=10)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch category tree: {resp.status_code}")
                return []

            tree = resp.json()
            slugs = set()

            def extract_slugs(nodes):
                for node in nodes:
                    # 'url' usually looks like "https://domain.com/whey-protein"
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

    def crawl(self):
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")

        # Dynamic Discovery
        categories = self._fetch_categories()
        if not categories:
            logger.info("Using Fallback Categories.")
            categories = self.FALLBACK_CATEGORIES

        logger.info(f"Discovered {len(categories)} categories to crawl.")

        all_products = []

        for category_slug in categories:
            logger.info(f"Crawling Category: {category_slug}")
            # Standard VTEX Search Endpoint Pattern
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
                        # 404 or 500 might mean invalid category or empty
                        break

                    data = response.json()
                    if not data:
                        break

                    for item in data:
                        try:
                            # Pass category_slug to process_item
                            processed_item = self._process_item(item, category_slug)
                            if processed_item:
                                all_products.append(processed_item)
                        except Exception as e:
                            logger.debug(f"Skipping item: {e}")

                    if len(data) < step:
                        break

                    start += step
                    self.sleep_random(0.5, 1.0)

                except Exception as e:
                    logger.error(f"Error crawling {category_slug}: {e}")
                    break

        return all_products

    def _process_item(self, item, category_name="proteina"):
        """
        Map VTEX API Product to our internal dict structure.
        """
        try:
            # 1. Basic Info
            pid = item.get("productId")
            name = item.get("productName")
            # Use subclass BRAND_NAME if item doesn't specify, or respect item brand
            brand = item.get("brand") or self.BRAND_NAME
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            # 2. SKU / Price Information
            skus = item.get("items", [])
            if not skus:
                return None

            # Pick the first SKU
            first_sku = skus[0]

            # Check availability and price in sellers
            sellers = first_sku.get("sellers", [])
            active_seller = None

            # Usually seller "1" is the main store, or find default
            for seller in sellers:
                if seller.get("sellerDefault"):
                    active_seller = seller
                    break

            if not active_seller and sellers:
                active_seller = sellers[0]

            if not active_seller:
                return None

            ean = first_sku.get("ean", "")

            comm_offer = active_seller.get("commertialOffer", {})
            price = comm_offer.get("Price")
            stock = comm_offer.get("AvailableQuantity", 0)

            if price is None:
                return None

            return {
                "item_id": str(pid),
                "item_name": name,
                "price": float(price),
                "item_brand": brand,
                "item_list_name": category_name,  # Use dynamic category name
                "url": url,
                "stock": int(stock),
                "ean": ean,
            }
        except Exception as e:
            logger.debug(f"Item parse error: {e}")
            return None
