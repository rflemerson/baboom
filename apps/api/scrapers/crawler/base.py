"""Shared Scrapy behavior for category-driven catalog spiders."""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from scrapy import Request, Spider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

    from ..contracts import ScrapedProductInput
    from ..normalizers.base import ProductNormalizer

logger = logging.getLogger(__name__)

# SystemRandom so the jitter is not a pseudo-random sequence a store could
# predict across runs.
_jitter = secrets.SystemRandom()


class CatalogSpider(Spider):
    """Schedule platform requests and emit normalized pages for the pipeline."""

    normalizer: ProductNormalizer
    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    FALLBACK_CATEGORIES: tuple[str, ...] = ()
    STARTUP_JITTER_SECONDS = (0.0, 5.0)

    def __init__(
        self, categories: list[str] | str | None = None, **kwargs: object
    ) -> None:
        """Initialize a spider with an optional comma-separated category filter."""
        super().__init__(**kwargs)
        if isinstance(categories, str):
            self.categories_to_crawl = [
                value.strip() for value in categories.split(",") if value.strip()
            ]
        else:
            self.categories_to_crawl = categories
        self.processed_ids: set[str] = set()

    async def start(self) -> AsyncIterator[Request]:
        """Spread full runs before scheduling the first request."""
        # The task reads this to know whose unseen offers a successful run
        # speaks for.
        crawler = getattr(self, "crawler", None)
        if crawler is not None:
            crawler.stats.set_value("scraper/store_slug", self.STORE_SLUG)
        if not self.categories_to_crawl:
            await asyncio.sleep(_jitter.uniform(*self.STARTUP_JITTER_SECONDS))
        for request in self.start_category_requests():
            yield request

    def start_category_requests(self) -> Iterable[Request]:
        """Start configured categories or the platform discovery request."""
        if self.categories_to_crawl:
            yield from self._requests_for_categories(self.categories_to_crawl)
            return
        yield self.category_discovery_request()

    def category_discovery_request(self) -> Request:
        """Return the platform-specific category discovery request."""
        raise NotImplementedError

    def requests_for_categories(self, categories: Iterable[str]) -> Iterable[Request]:
        """Expose category scheduling for platform callbacks and tests."""
        yield from self._requests_for_categories(categories)

    def _requests_for_categories(self, categories: Iterable[str]) -> Iterable[Request]:
        resolved = [str(category) for category in categories if str(category)]
        if not resolved:
            resolved = list(self.FALLBACK_CATEGORIES)
            logger.info("No dynamic categories found, using configured fallback.")
        self._set_stat("categories_discovered", len(resolved))
        for category in resolved:
            self._set_stat("categories_scheduled")
            yield self.category_request(category)

    def categories_or_fallback(self, categories: Iterable[str]) -> list[str]:
        """Choose discovered categories, with the configured fallback if empty."""
        resolved = [str(category) for category in categories if str(category)]
        self.check_category_discrepancy(resolved, self.FALLBACK_CATEGORIES)
        return resolved or list(self.FALLBACK_CATEGORIES)

    def check_category_discrepancy(
        self,
        dynamic_categories: Iterable[str],
        fallback_categories: Iterable[str],
    ) -> None:
        """Log differences between dynamic and configured category sources."""
        dynamic = set(dynamic_categories)
        fallback = set(fallback_categories)
        if not dynamic or not fallback:
            return
        if missing := fallback - dynamic:
            logger.warning(
                "[%s] Categories in FALLBACK but not in Dynamic: %s",
                self.__class__.__name__,
                missing,
            )
        if extra := dynamic - fallback:
            logger.warning(
                "[%s] Categories in Dynamic but not in FALLBACK: %s",
                self.__class__.__name__,
                extra,
            )

    def category_request(self, category: str) -> Request:
        """Return the platform-specific first page request for a category."""
        raise NotImplementedError

    def request(
        self,
        url: str,
        *,
        callback: object,
        params: dict[str, object] | None = None,
        handle_httpstatus_list: list[int] | None = None,
        **kwargs: object,
    ) -> Request:
        """Fold params into the query string and forward the rest to Request."""
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params)}"
        request_meta = dict(kwargs.pop("meta", None) or {})
        if handle_httpstatus_list:
            request_meta["handle_httpstatus_list"] = handle_httpstatus_list
        return Request(url, callback=callback, meta=request_meta, **kwargs)

    def process_raw_product(
        self,
        raw: dict,
        category: str,
        *,
        claim_id: bool = True,
    ) -> list[ScrapedProductInput]:
        """Normalize one source object into a pipeline item without database I/O."""
        product_id = self.product_id(raw)
        if claim_id and (not product_id or product_id in self.processed_ids):
            return []
        product = self.normalizer.normalize(
            raw,
            store_slug=self.STORE_SLUG,
            base_url=self.BASE_URL,
            category=category,
        )
        if product is not None:
            if claim_id:
                self.processed_ids.add(product_id)
            self._set_stat("offers_collected", len(product.offers))
        return [product] if product is not None else []

    def product_id(self, raw: dict) -> str:
        """Return the platform product identifier used for cross-category dedupe."""
        return str(raw.get("id") or raw.get("productId") or raw.get("sku") or "")

    def emit_products(
        self,
        raw_products: Iterable[object],
        category: str,
    ) -> Iterable[ScrapedProductInput]:
        """Normalize valid dictionaries and count pages' emitted products."""
        emitted = 0
        for raw in raw_products:
            if not isinstance(raw, dict):
                continue
            for product in self.process_raw_product(raw, category):
                emitted += 1
                yield product
        self._set_stat("products_collected", emitted)
        self._set_stat("categories_crawled")

    def _set_stat(self, key: str, increment: int = 1) -> None:
        """Increment a Scrapy statistic when the engine is available."""
        crawler = getattr(self, "crawler", None)
        if crawler is not None:
            crawler.stats.inc_value(f"scraper/{key}", increment)
