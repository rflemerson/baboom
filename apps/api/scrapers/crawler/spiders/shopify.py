"""Scrapy spider template for Shopify public catalog APIs."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from scrapy import Request
from scrapy.http import Response

from ..base import CatalogSpider
from ...normalizers.shopify import ShopifyNormalizer

logger = logging.getLogger(__name__)

SHOPIFY_SUCCESS_CODE = 200
SHOPIFY_PAGE_SIZE = 250


class ShopifyApiSpider(CatalogSpider):
    """Crawl Shopify collections and emit one normalized page per product."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    normalizer = ShopifyNormalizer()
    FALLBACK_CATEGORIES: tuple[str, ...] = ()
    USE_PRODUCT_DETAIL = False

    def category_discovery_request(self) -> Request:
        """Start Shopify collection discovery."""
        return self.request(
            self._collections_endpoint(),
            callback=self._parse_collections,
            params={"page": 1, "limit": SHOPIFY_PAGE_SIZE},
            meta={"collection_page": 1, "collection_handles": []},
        )

    def category_request(self, category: str) -> Request:
        """Request the first page of one Shopify collection."""
        return self.request(
            f"{self.BASE_URL}/collections/{category}/products.json",
            callback=self._parse_category,
            params={"page": 1, "limit": SHOPIFY_PAGE_SIZE},
            headers=self.get_headers(),
            meta={"category": category, "page": 1},
        )

    def get_headers(self) -> dict[str, str]:
        """Return headers for Shopify's JSON endpoints."""
        return {"Accept": "application/json"}

    def _collections_endpoint(self) -> str:
        """Return the collection discovery endpoint."""
        return f"{self.BASE_URL}/collections.json"

    def _parse_collections(self, response: Response):
        """Collect handles, paginate discovery, then schedule collections."""
        try:
            payload = response.json()
            collections = payload.get("collections") or []
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.debug("Shopify collection payload parse error: %s", exc)
            collections = []

        handles = set(response.meta.get("collection_handles", []))
        for collection in collections if isinstance(collections, list) else []:
            if isinstance(collection, dict) and collection.get("handle"):
                handles.add(str(collection["handle"]))

        page = int(response.meta.get("collection_page", 1))
        if len(collections) >= SHOPIFY_PAGE_SIZE:
            yield self.request(
                self._collections_endpoint(),
                callback=self._parse_collections,
                params={"page": page + 1, "limit": SHOPIFY_PAGE_SIZE},
                meta={
                    "collection_page": page + 1,
                    "collection_handles": list(handles),
                },
                dont_filter=True,
            )
            return
        yield from self.requests_for_categories(self.categories_or_fallback(handles))

    def _parse_category(self, response: Response):
        """Normalize one Shopify collection page and continue pagination."""
        category = str(response.meta["category"])
        page = int(response.meta["page"])
        try:
            payload = response.json()
            products = payload.get("products") or []
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.debug("Shopify category payload parse error for %s: %s", category, exc)
            products = []

        yield from self._emit_category_products(products, category)
        if len(products) >= SHOPIFY_PAGE_SIZE:
            yield self.request(
                response.url.split("?", maxsplit=1)[0],
                callback=self._parse_category,
                params={"page": page + 1, "limit": SHOPIFY_PAGE_SIZE},
                headers=self.get_headers(),
                meta={"category": category, "page": page + 1},
            )

    def _emit_category_products(
        self,
        products: object,
        category: str,
    ) -> Iterable[object]:
        """Handle listings and optionally fetch Shopify product details."""
        if not isinstance(products, list):
            return
        for product in products:
            if not isinstance(product, dict):
                continue
            product_id = self.product_id(product)
            if not product_id or product_id in self.processed_ids:
                continue
            self.processed_ids.add(product_id)
            if self.USE_PRODUCT_DETAIL and product.get("handle"):
                yield self.request(
                    f"{self.BASE_URL}/products/{product['handle']}.js",
                    callback=self._parse_detail,
                    errback=self._detail_failed,
                    headers=self.get_headers(),
                    meta={"listing_product": product, "category": category},
                    dont_filter=True,
                )
            else:
                yield from self.process_raw_product(product, category, claim_id=False)

    def _parse_detail(self, response: Response):
        """Normalize a Shopify detail response, falling back to its listing."""
        listing = response.meta["listing_product"]
        category = str(response.meta["category"])
        try:
            detail = response.json()
        except (TypeError, ValueError) as exc:
            logger.debug("Shopify detail payload parse error for %s: %s", self.product_id(listing), exc)
            detail = None
        yield from self.process_raw_product(
            detail if isinstance(detail, dict) else listing,
            category,
            claim_id=False,
        )

    def _detail_failed(self, failure: object):
        """Keep a listing product when its optional detail request fails."""
        request = getattr(failure, "request", None)
        if request is None:
            return
        listing = request.meta.get("listing_product")
        category = request.meta.get("category", "")
        if isinstance(listing, dict):
            yield from self.process_raw_product(listing, str(category), claim_id=False)
