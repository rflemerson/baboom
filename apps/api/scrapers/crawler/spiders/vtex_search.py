"""Scrapy spider template for the VTEX legacy search API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...normalizers.vtex import VtexNormalizer
from ..base import CatalogSpider

if TYPE_CHECKING:
    from collections.abc import Iterator

    from scrapy import Request
    from scrapy.http import Response

    from ...contracts import ScrapedProductInput


logger = logging.getLogger(__name__)

VTEX_CATEGORY_TREE_SUCCESS_CODE = 200
VTEX_SUCCESS_CODES = (200, 206)
VTEX_PAGE_SIZE = 50


class VtexSearchSpider(CatalogSpider):
    """Crawl VTEX category search ranges and emit normalized product pages."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    API_TREE = ""
    normalizer = VtexNormalizer(context_platform="vtex_legacy")
    FALLBACK_CATEGORIES: tuple[str, ...] = ()

    def category_discovery_request(self) -> Request:
        """Start VTEX category-tree discovery."""
        return self.request(
            self.API_TREE,
            callback=self._parse_categories,
            headers=self.get_headers(),
        )

    def category_request(self, category: str) -> Request:
        """Request the first VTEX search range for a category."""
        return self.request(
            self._build_search_url(category),
            callback=self._parse_category,
            params=self._build_pagination_params(0, VTEX_PAGE_SIZE),
            headers=self.get_headers(),
            meta={"category": category, "start": 0},
            handle_httpstatus_list=list(VTEX_SUCCESS_CODES),
        )

    def get_headers(self) -> dict[str, str]:
        """Return headers for VTEX's JSON endpoints."""
        return {"Accept": "application/json"}

    def _parse_categories(
        self,
        response: Response,
    ) -> Iterator[Request | ScrapedProductInput]:
        """Flatten the VTEX tree and schedule its category requests."""
        if response.status != VTEX_CATEGORY_TREE_SUCCESS_CODE:
            logger.warning("Failed to fetch category tree: %s", response.status)
            yield from self.requests_for_categories(self.FALLBACK_CATEGORIES)
            return
        try:
            tree = response.json()
            slugs: set[str] = set()
            self._extract_slugs(tree if isinstance(tree, list) else [], slugs)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.debug("VTEX category payload parse error: %s", exc)
            slugs = set()
        yield from self.requests_for_categories(self.categories_or_fallback(slugs))

    def _extract_slugs(self, nodes: list[object], slugs: set[str]) -> None:
        """Recursively extract the last path segment from category URLs."""
        for node in nodes:
            if not isinstance(node, dict):
                continue
            url = str(node.get("url") or "").rstrip("/")
            if url and url.split("/")[-1]:
                slugs.add(url.split("/")[-1])
            children = node.get("children")
            if isinstance(children, list):
                self._extract_slugs(children, slugs)

    def _build_search_url(self, category: str) -> str:
        """Build a VTEX category search endpoint URL."""
        return f"{self.BASE_URL}/api/catalog_system/pub/products/search/{category}"

    def _build_pagination_params(self, start: int, step: int) -> dict[str, int]:
        """Build VTEX inclusive range parameters."""
        return {"_from": start, "_to": start + step - 1}

    def _parse_category(
        self,
        response: Response,
    ) -> Iterator[Request | ScrapedProductInput]:
        """Normalize one VTEX search range and continue while it is full."""
        category = str(response.meta["category"])
        start = int(response.meta["start"])
        try:
            data = response.json()
            items = data if isinstance(data, list) else []
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            logger.debug("VTEX item page parse error for %s: %s", category, exc)
            items = []
        yield from self.emit_products(items, category)
        if len(items) >= VTEX_PAGE_SIZE:
            yield self.request(
                response.url.split("?", maxsplit=1)[0],
                callback=self._parse_category,
                params=self._build_pagination_params(
                    start + VTEX_PAGE_SIZE, VTEX_PAGE_SIZE
                ),
                headers=self.get_headers(),
                meta={"category": category, "start": start + VTEX_PAGE_SIZE},
                handle_httpstatus_list=list(VTEX_SUCCESS_CODES),
            )
