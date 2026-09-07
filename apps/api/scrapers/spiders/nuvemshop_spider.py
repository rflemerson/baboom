"""Template Method base for Nuvemshop (Tiendanube) storefront scrapers.

Nuvemshop exposes no public catalog JSON API. Its listing pages do embed one
JSON-LD ``Product`` block per item, carrying name, SKU, canonical URL, price,
availability and inventory level, so that is the ingestion source: structured
data published by the platform itself rather than parsed markup.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from offers.models import StockStatus

from ..dtos import ScrapedItemIngestionInput
from ..services import ScraperService
from .catalog_api_spider import CatalogApiSpider
from .common import parse_positive_price

logger = logging.getLogger(__name__)

NUVEMSHOP_SUCCESS_CODE = 200

JSON_LD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

IN_STOCK_MARKER = "instock"


class NuvemshopSpider(CatalogApiSpider):
    """Template spider for Nuvemshop storefronts."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""

    FALLBACK_CATEGORIES: tuple[str, ...] = ("produtos",)
    # Listing pages are HTML, so a page yields far fewer items than an API
    # call would; the cap stops a pagination bug from looping forever.
    MAX_PAGES = 60

    def get_headers(self) -> dict[str, str]:
        """Return browser-like headers, since these are rendered HTML pages."""
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }

    def _fetch_categories(self) -> list[str]:
        """Return the configured listing paths.

        Nuvemshop has no category discovery endpoint, and the ``produtos``
        listing already paginates over the whole catalog, so the configured
        paths are the categories.
        """
        return list(self.FALLBACK_CATEGORIES)

    def _crawl_category(
        self,
        category: str,
        processed_ids: set[str],
    ) -> list[object]:
        """Walk one listing path until a page returns no products."""
        logger.info("Crawling category: %s", category)
        products: list[object] = []

        for page in range(1, self.MAX_PAGES + 1):
            items = self._fetch_page_items(category, page)
            if not items:
                break

            for item in items:
                sku = str(item.get("sku") or "")
                if not sku or sku in processed_ids:
                    continue
                processed_ids.add(sku)
                saved = self._process_and_save(item, category)
                if saved:
                    products.append(saved)

            self.sleep_random(0.4, 1.0)

        return products

    def _fetch_page_items(self, category: str, page: int) -> list[dict[str, Any]]:
        """Fetch one listing page and return its JSON-LD products."""
        response = self._request_get(
            f"{self.BASE_URL}/{category}/",
            params={"page": page},
            timeout=self.HTTP_TIMEOUT_SECONDS,
        )
        if response is None:
            return []
        status_code = getattr(response, "status_code", None)
        if status_code != NUVEMSHOP_SUCCESS_CODE:
            logger.warning(
                "Failed category %s page %s: %s",
                category,
                page,
                status_code,
            )
            return []
        return self.extract_products(response.text)

    def extract_products(self, html: str) -> list[dict[str, Any]]:
        """Return the JSON-LD ``Product`` entries embedded in a listing page."""
        products: list[dict[str, Any]] = []

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

    def _offer(self, item: dict[str, Any]) -> dict[str, Any]:
        """Return the first offer of a product entry."""
        offers = item.get("offers")
        if isinstance(offers, list):
            offers = next((o for o in offers if isinstance(o, dict)), None)
        return offers if isinstance(offers, dict) else {}

    def _stock_quantity(self, offer: dict[str, Any]) -> int | None:
        """Return the advertised inventory level, when the offer carries one."""
        level = offer.get("inventoryLevel")
        value = level.get("value") if isinstance(level, dict) else None
        if value is None:
            return None
        try:
            return int(float(value))
        except TypeError, ValueError:
            return None

    def _process_and_save(
        self,
        item: dict[str, Any],
        category_name: str,
    ) -> object | None:
        """Normalize one JSON-LD product and persist it."""
        try:
            sku = str(item.get("sku") or "")
            if not sku:
                return None

            offer = self._offer(item)
            price = parse_positive_price(offer.get("price"))
            if price is None:
                logger.warning("Skipping Nuvemshop item without valid price: %s", sku)
                return None

            availability = str(offer.get("availability") or "").lower()
            is_available = IN_STOCK_MARKER in availability
            stock_quantity = self._stock_quantity(offer) if is_available else 0

            input_data = ScrapedItemIngestionInput(
                store_slug=self.STORE_SLUG,
                external_id=sku,
                url=str(offer.get("url") or item.get("url") or ""),
                name=str(item.get("name") or ""),
                price=price,
                stock_quantity=stock_quantity,
                stock_status=(
                    StockStatus.AVAILABLE if is_available else StockStatus.OUT_OF_STOCK
                ),
                ean=str(item.get("gtin13") or ""),
                sku=sku,
                pid=sku,
                category=category_name,
            )
            saved = ScraperService.save_product(
                input_data,
                api_context=self._build_product_context(item),
            )
        except Exception:
            logger.exception("Error processing item %s", item.get("sku"))
            return None

        return saved

    def process_item(
        self,
        data: dict[str, Any],
        category_name: str,
    ) -> object | None:
        """Normalize and persist one product from a listing page."""
        return self._process_and_save(data, category_name)

    def _build_product_context(self, item: dict[str, Any]) -> str:
        """Build structured context for downstream extraction."""
        return json.dumps(
            {"platform": "nuvemshop", "product": item},
            ensure_ascii=False,
        )
