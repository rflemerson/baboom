"""Shared template base for category-driven API spiders."""

from __future__ import annotations

import logging
import time

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)

HTTP_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class CatalogApiSpider(BaseSpider):
    """Template method for category-based API crawlers."""

    BRAND_NAME = ""
    FALLBACK_CATEGORIES: tuple[str, ...] = ()
    HTTP_TIMEOUT_SECONDS = 30
    HTTP_RETRIES = 3
    HTTP_RETRY_BACKOFF_SECONDS = 0.6

    def __init__(self, categories: list[str] | None = None) -> None:
        """Initialize shared metrics for category-driven API spiders."""
        super().__init__(categories)
        self.metrics: dict[str, int | float] = {
            "categories_discovered": 0,
            "categories_crawled": 0,
            "products_collected": 0,
            "crawl_duration_ms": 0.0,
        }

    def _new_processed_registry(self) -> set[str]:
        """Create the dedupe registry used across categories."""
        return set()

    def _fetch_categories(self) -> list[str]:
        """Fetch categories dynamically from the target platform."""
        raise NotImplementedError

    def _crawl_category(
        self,
        category: str,
        processed_ids: set[str],
    ) -> list[object]:
        """Crawl one category and return saved product objects."""
        raise NotImplementedError

    def _resolve_categories(self) -> list[str]:
        categories = self._fetch_categories()
        self.check_category_discrepancy(categories, self.FALLBACK_CATEGORIES)
        if not categories:
            logger.info("No dynamic categories found, using fallback/config.")
            categories = self.categories_to_crawl or self.FALLBACK_CATEGORIES
        self.metrics["categories_discovered"] = len(categories)
        return categories

    def crawl(self) -> list[object]:
        """Template crawl flow for category-based API sources."""
        started = time.perf_counter()
        logger.info("Starting API crawl for %s...", self.BRAND_NAME)
        all_products: list[object] = []
        processed_ids = self._new_processed_registry()
        categories = self._resolve_categories()
        logger.info("Discovered %s categories to crawl.", len(categories))

        for category in categories:
            results = self._crawl_category(category, processed_ids)
            self.metrics["categories_crawled"] = (
                int(self.metrics["categories_crawled"]) + 1
            )
            self.metrics["products_collected"] = int(
                self.metrics["products_collected"],
            ) + len(results)
            all_products.extend(results)

        self.metrics["crawl_duration_ms"] = round(
            (time.perf_counter() - started) * 1000,
            2,
        )
        logger.info(
            "Crawl finished. Total products: %s | metrics=%s",
            len(all_products),
            self.metrics,
        )
        return all_products

    def _request_get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> requests.Response | None:
        """HTTP GET with retries for transient errors."""
        attempts = max(1, int(self.HTTP_RETRIES))
        timeout_value = timeout or self.HTTP_TIMEOUT_SECONDS
        for attempt in range(1, attempts + 1):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers or self.get_headers(),
                    timeout=timeout_value,
                )
                if response.status_code not in HTTP_RETRYABLE_STATUS_CODES:
                    return response
                if attempt == attempts:
                    return response
                backoff = self.HTTP_RETRY_BACKOFF_SECONDS * attempt
                self.sleep_random(backoff, backoff + 0.2)
            except Exception:
                if attempt == attempts:
                    logger.exception("HTTP GET failed for %s", url)
                    return None
                backoff = self.HTTP_RETRY_BACKOFF_SECONDS * attempt
                self.sleep_random(backoff, backoff + 0.2)
        return None
