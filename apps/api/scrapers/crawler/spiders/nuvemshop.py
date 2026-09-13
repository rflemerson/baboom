"""Scrapy spider template for Nuvemshop JSON-LD listing pages."""

from __future__ import annotations

import json
import logging
import re

from scrapy import Request
from scrapy.http import Response

from ..base import CatalogSpider
from ...normalizers.nuvemshop import NuvemshopNormalizer

logger = logging.getLogger(__name__)

NUVEMSHOP_SUCCESS_CODE = 200
JSON_LD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class NuvemshopSpider(CatalogSpider):
    """Crawl Nuvemshop listing pages and emit JSON-LD products."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    normalizer = NuvemshopNormalizer()
    FALLBACK_CATEGORIES: tuple[str, ...] = ("produtos",)
    MAX_PAGES = 60

    def get_headers(self) -> dict[str, str]:
        """Return browser-like headers for storefront HTML."""
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }

    def category_discovery_request(self) -> Request:
        """Nuvemshop has no category endpoint; start configured listings."""
        return self.category_request(self.FALLBACK_CATEGORIES[0])

    def category_request(self, category: str) -> Request:
        """Request the first page of a Nuvemshop listing path."""
        return self.request(
            f"{self.BASE_URL}/{category}/",
            callback=self._parse_category,
            params={"page": 1},
            headers=self.get_headers(),
            meta={"category": category, "page": 1},
        )

    def _parse_category(self, response: Response):
        """Extract JSON-LD products and continue until the listing ends."""
        category = str(response.meta["category"])
        page = int(response.meta["page"])
        if response.status != NUVEMSHOP_SUCCESS_CODE:
            logger.warning("Failed category %s page %s: %s", category, page, response.status)
            return
        products = self.extract_products(response.text)
        yield from self.emit_products(products, category)
        if products and page < self.MAX_PAGES:
            yield self.request(
                response.url.split("?", maxsplit=1)[0],
                callback=self._parse_category,
                params={"page": page + 1},
                headers=self.get_headers(),
                meta={"category": category, "page": page + 1},
            )

    def extract_products(self, html: str) -> list[dict[str, object]]:
        """Return Product JSON-LD entries embedded in one listing page."""
        products: list[dict[str, object]] = []
        for raw in JSON_LD_PATTERN.findall(html or ""):
            try:
                payload = json.loads(raw.strip())
            except json.JSONDecodeError:
                continue
            entries = payload if isinstance(payload, list) else [payload]
            products.extend(
                entry
                for entry in entries
                if isinstance(entry, dict) and entry.get("@type") == "Product"
            )
        return products
