"""Scrapy spider template for Nuvemshop storefronts.

A listing page names products through JSON-LD but describes only the first
unit of each. The units a product sells -- one per flavor or size -- are in the
product page's ``LS.variants``, so every listed product's page is read too.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from ...normalizers.nuvemshop import NuvemshopNormalizer
from ..base import CatalogSpider

if TYPE_CHECKING:
    from collections.abc import Iterator

    from scrapy import Request
    from scrapy.http import Response

    from ...contracts import ScrapedProductInput


logger = logging.getLogger(__name__)

NUVEMSHOP_SUCCESS_CODE = 200
JSON_LD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
VARIANTS_PATTERN = re.compile(
    r"LS\.variants\s*=\s*(\[.*?\]);\s*$",
    re.DOTALL | re.MULTILINE,
)
# The page also carries quick-buy forms for related products; only the main
# one has this id.
PRODUCT_FORM_PATTERN = re.compile(
    r'<form[^>]*id="product_form"[^>]*>(.*?)</form>',
    re.DOTALL | re.IGNORECASE,
)
OPTION_LABEL_PATTERN = re.compile(
    r'<label[^>]*for="variation_(\d+)"[^>]*>\s*([^<]+?)\s*</label>',
    re.IGNORECASE,
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

    def _parse_category(
        self,
        response: Response,
    ) -> Iterator[Request | ScrapedProductInput]:
        """Extract JSON-LD products and continue until the listing ends."""
        category = str(response.meta["category"])
        page = int(response.meta["page"])
        if response.status != NUVEMSHOP_SUCCESS_CODE:
            self.mark_incomplete(
                f"category {category} page {page} answered {response.status}",
            )
            return
        products = self.extract_products(response.text)
        yield from self._product_page_requests(products, category)
        self._set_stat("categories_crawled")
        if products and page < self.MAX_PAGES:
            yield self.request(
                response.url.split("?", maxsplit=1)[0],
                callback=self._parse_category,
                params={"page": page + 1},
                headers=self.get_headers(),
                meta={"category": category, "page": page + 1},
            )

    def _product_page_requests(
        self,
        products: list[dict[str, object]],
        category: str,
    ) -> Iterator[Request]:
        """Ask for each listed product's page once, carrying its listing entry."""
        for listing in products:
            product_id = self.product_id(listing)
            page_url = self.normalizer.page_url(listing)
            if not product_id or not page_url or product_id in self.processed_ids:
                continue
            self.processed_ids.add(product_id)
            yield self.request(
                page_url,
                callback=self._parse_product,
                headers=self.get_headers(),
                meta={"category": category, "listing": listing},
            )

    def _parse_product(self, response: Response) -> Iterator[ScrapedProductInput]:
        """Emit every unit a product page sells, or its listing unit if lost."""
        category = str(response.meta["category"])
        listing = response.meta["listing"]
        variants = (
            self.extract_variants(response.text)
            if response.status == NUVEMSHOP_SUCCESS_CODE
            else []
        )
        if variants:
            product = self.normalizer.normalize_page(
                listing,
                variants,
                self.extract_option_names(response.text),
                store_slug=self.STORE_SLUG,
                category=category,
            )
        else:
            # The listing unit keeps its price current; the page's other units
            # were not read, so this run cannot establish that any are gone.
            self.mark_incomplete(
                f"product page {response.url} answered {response.status} "
                "without variants",
            )
            product = self.normalizer.normalize(
                listing,
                store_slug=self.STORE_SLUG,
                base_url=self.BASE_URL,
                category=category,
            )
        if product is not None:
            self._set_stat("offers_collected", len(product.offers))
            self._set_stat("products_collected")
            yield self.with_market(product)

    @staticmethod
    def extract_variants(html: str) -> list[dict[str, object]]:
        """Return the product's own units from ``LS.variants``."""
        match = VARIANTS_PATTERN.search(html or "")
        if match is None:
            return []
        try:
            variants = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
        return [variant for variant in variants if isinstance(variant, dict)]

    @staticmethod
    def extract_option_names(html: str) -> list[str]:
        """Return the option names of the product form, in option0.. order."""
        form = PRODUCT_FORM_PATTERN.search(html or "")
        if form is None:
            return []
        labels = sorted(
            (int(position), label.rstrip(":").strip())
            for position, label in OPTION_LABEL_PATTERN.findall(form[1])
        )
        return [label for _position, label in labels]

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
