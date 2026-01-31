import base64
import json
import logging
from typing import Any

import requests

from ..models import ScrapedItem
from ..services import ScraperService
from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class BlackSkullSpider(BaseSpider):
    """Spider for Black Skull (VTEX GraphQL)."""

    BRAND_NAME = "Black Skull"
    STORE_SLUG = "black_skull"
    BASE_URL = "https://www.blackskullusa.com.br"

    API_ENDPOINT = "https://www.blackskullusa.com.br/_v/segment/graphql/v1"
    API_TREE = "https://www.blackskullusa.com.br/api/catalog_system/pub/category/tree/3"

    QUERY_HASH = "ee2478d319404f621c3e0426e79eba3997665d48cb277a53bf0c3276e8e53c22"

    FALLBACK_CATEGORIES = [
        "proteina",
        "aminoacidos",
        "vitaminas",
        "vestuario",
        "acessorios",
        "kits",
    ]

    def _fetch_categories(self) -> list[str]:
        try:
            logger.info("Fetching categories for Black Skull...")
            response = requests.get(
                self.API_TREE, headers=self.get_headers(), timeout=10
            )
            if response.status_code != 200:
                logger.error(f"Failed to fetch categories: {response.status_code}")
                return []

            categories = []
            for item in response.json():
                if item.get("hasChildren") or item.get("url"):
                    url = item.get("url", "")
                    slug = url.split("/")[-1] if url else ""
                    if slug:
                        categories.append(slug)

            return categories

        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def crawl(self) -> list[Any]:
        """Crawl products from API."""
        logger.info(f"Starting API crawl for {self.BRAND_NAME}...")
        all_products = []

        categories = self._fetch_categories()
        self.check_category_discrepancy(categories, self.FALLBACK_CATEGORIES)

        if not categories:
            logger.info("No dynamic categories found, using fallback.")
            categories = self.FALLBACK_CATEGORIES

        logger.info(f"Discovered {len(categories)} categories to crawl.")

        for category in categories:
            products = self._crawl_category(category)
            all_products.extend(products)

        logger.info(f"Crawl finished. Total products: {len(all_products)}")
        return all_products

    def _crawl_category(self, category: str) -> list[Any]:
        """Crawl a single category."""
        logger.info(f"Crawling Category: {category}")
        products = []
        processed_ids = set()
        start = 0
        step = 50

        while True:
            end = start + step - 1
            data = self._fetch_graphql_data(category, start, end)

            if not data:
                break

            items = self._parse_graphql_response(data)
            if not items:
                break

            items_in_page = 0
            for item in items:
                try:
                    item_id = str(item.get("productId"))
                    if item_id in processed_ids:
                        continue

                    processed_ids.add(item_id)
                    saved_obj = self._process_and_save(item, category)
                    if saved_obj:
                        products.append(saved_obj)
                        items_in_page += 1
                except Exception as e:
                    logger.debug(f"Skipping item: {e}")

            if len(items) < step:
                break

            start += step
            self.sleep_random(0.5, 1.5)

        return products

    def _fetch_graphql_data(self, category: str, start: int, end: int) -> dict | None:
        """Execute GraphQL query."""
        variables_dict = {
            "hideUnavailableItems": False,
            "category": category,
            "specificationFilters": [],
            "orderBy": "OrderByScoreDESC",
            "from": start,
            "to": end,
            "shippingOptions": [],
            "variant": "",
            "advertisementOptions": {
                "showSponsored": False,
                "sponsoredCount": 0,
                "repeatSponsoredProducts": False,
                "advertisementPlacement": "home_shelf",
            },
        }

        vars_json = json.dumps(variables_dict, separators=(",", ":"))
        vars_b64 = base64.b64encode(vars_json.encode("utf-8")).decode("utf-8")

        extensions_dict = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": self.QUERY_HASH,
                "sender": "vtex.store-resources@0.x",
                "provider": "vtex.search-graphql@0.x",
            },
            "variables": vars_b64,
        }
        extensions_json = json.dumps(extensions_dict, separators=(",", ":"))

        params = {
            "workspace": "master",
            "maxAge": "short",
            "appsEtag": "remove",
            "domain": "store",
            "locale": "pt-BR",
            "operationName": "Products",
            "variables": "{}",
            "extensions": extensions_json,
        }

        try:
            response = requests.get(
                self.API_ENDPOINT,
                params=params,
                headers=self.get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"GraphQL Error: {response.text[:200]}")
                return None

            data = response.json()
            if "errors" in data:
                logger.error(f"GraphQL Body Errors: {data['errors']}")
                return None

            return data
        except Exception as e:
            logger.error(f"Crawl error for {category}: {e}")
            return None

    def _parse_graphql_response(self, data: dict) -> list[dict]:
        """Extract product list from GraphQL response."""
        products_list = []
        p_search = data.get("data", {}).get("productSearch")
        if p_search and isinstance(p_search, dict):
            products_list = p_search.get("products", [])

        if not products_list:
            p_direct = data.get("data", {}).get("products")
            if isinstance(p_direct, list):
                products_list = p_direct
            elif isinstance(p_direct, dict):
                products_list = p_direct.get("products", [])

        return products_list

    def _process_and_save(self, item: dict, category_name: str) -> Any | None:
        try:
            pid = item.get("productId")
            name = item.get("productName")
            link_text = item.get("linkText")
            url = f"{self.BASE_URL}/{link_text}/p" if link_text else ""

            items_list = item.get("items", [])
            if not items_list:
                return None

            first_sku = items_list[0]
            sellers = first_sku.get("sellers", [])
            active_seller = None
            if sellers:
                active_seller = sellers[0]
                for s in sellers:
                    if s.get("sellerDefault"):
                        active_seller = s
                        break

            if not active_seller:
                return None

            comm_offer = active_seller.get("commertialOffer", {})
            price = comm_offer.get("Price")

            stock_quantity = comm_offer.get("AvailableQuantity")

            try:
                stock_quantity = (
                    int(stock_quantity) if stock_quantity is not None else 0
                )
            except (ValueError, TypeError):
                stock_quantity = 0

            if stock_quantity > 0:
                stock_status = ScrapedItem.StockStatus.AVAILABLE
            else:
                stock_status = ScrapedItem.StockStatus.OUT_OF_STOCK

            if not price:
                return None

            ean = first_sku.get("ean", "")
            sku = first_sku.get("itemId", "")

            return ScraperService.save_product(
                store_slug=self.STORE_SLUG,
                external_id=str(pid),
                url=url,
                name=str(name) if name else "",
                price=float(price),
                stock_quantity=stock_quantity,
                stock_status=stock_status,
                ean=str(ean),
                sku=str(sku),
                pid=str(pid),
                category=category_name,
            )

        except Exception as e:
            logger.debug(f"Item parse error: {e}")
            return None
