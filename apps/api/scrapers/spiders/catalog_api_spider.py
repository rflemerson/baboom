"""Shared template base for category-driven API spiders."""

from __future__ import annotations

import logging
import time

from .base_spider import BaseSpider
from .http_client import (
    RETRYABLE_STATUS_CODES,
    HttpClient,
    HttpRequestOptions,
    parse_retry_after,
)

logger = logging.getLogger(__name__)


class CatalogApiSpider(BaseSpider):
    """Template method for category-based API crawlers."""

    BRAND_NAME = ""
    FALLBACK_CATEGORIES: tuple[str, ...] = ()
    HTTP_TIMEOUT_SECONDS = 30
    HTTP_RETRIES = 3
    HTTP_RETRY_BACKOFF_SECONDS = 0.6
    # Stop hitting an origin once this many requests in a row come back blocked
    # or failed: hammering a host that is already refusing us is exactly what
    # turns a temporary throttle into a hard ban.
    HTTP_FAILURE_LIMIT = 8
    # Random delay before a scheduled full run starts, so the eight store tasks
    # firing on the same beat tick do not all hit their targets simultaneously.
    STARTUP_JITTER_SECONDS = (0.0, 5.0)

    def __init__(self, categories: list[str] | None = None) -> None:
        """Initialize the light catalog spider (price/stock/basic only).

        The heavy product-page HTML enrichment is a separate, on-demand pass
        (:meth:`ScraperService.enrich_pages`) and never runs from the crawl.
        """
        super().__init__(categories)
        self.http_client = HttpClient(timeout=self.HTTP_TIMEOUT_SECONDS)
        self._consecutive_failures = 0
        self.metrics: dict[str, int | float] = {
            "categories_discovered": 0,
            "categories_crawled": 0,
            "products_collected": 0,
        }

    def _new_processed_registry(self) -> set[str]:
        """Create the dedupe registry used across categories."""
        return set()

    def _fetch_categories(self) -> list[str]:
        """Fetch categories dynamically from the target platform."""
        raise NotImplementedError

    def fetch_categories(self) -> list[str]:
        """Return categories using the spider discovery strategy."""
        return self._fetch_categories()

    def _crawl_category(
        self,
        category: str,
        processed_ids: set[str],
    ) -> list[object]:
        """Crawl one category and return saved product objects."""
        raise NotImplementedError

    def _resolve_categories(self) -> list[str]:
        if self.categories_to_crawl:
            categories = list(self.categories_to_crawl)
            logger.info(
                "Using explicit categories for %s: %s",
                self.BRAND_NAME,
                categories,
            )
            self.metrics["categories_discovered"] = len(categories)
            return categories

        categories = self._fetch_categories()
        self.check_category_discrepancy(categories, self.FALLBACK_CATEGORIES)
        if not categories:
            logger.info("No dynamic categories found, using fallback/config.")
            categories = list(self.FALLBACK_CATEGORIES)
        self.metrics["categories_discovered"] = len(categories)
        return categories

    def crawl(self) -> list[object]:
        """Template crawl flow for category-based API sources."""
        started = time.perf_counter()
        # Spread scheduled runs that fire on the same beat tick (explicit
        # category runs — manual/tests — start immediately).
        if not self.categories_to_crawl:
            self.sleep_random(*self.STARTUP_JITTER_SECONDS)
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
        verify: bool = True,
    ) -> object | None:
        """HTTP GET via browser TLS impersonation, with polite retries.

        This is the single HTTP entry point for every catalog spider. It routes
        through ``HttpClient`` (curl_cffi keep-alive session) so the TLS/JA3
        fingerprint matches a real browser and Sucuri/Cloudflare soft blocks are
        detected. On a transient failure it honors ``Retry-After``, backs off
        with jitter, and rotates to a fresh identity; after too many consecutive
        blocks a circuit breaker stops hammering the origin.
        """
        if self._consecutive_failures >= self.HTTP_FAILURE_LIMIT:
            logger.error(
                "Circuit breaker open for %s after %s consecutive failures; "
                "skipping %s",
                self.BRAND_NAME,
                self._consecutive_failures,
                url,
            )
            return None

        attempts = max(1, int(self.HTTP_RETRIES))
        timeout_value = timeout or self.HTTP_TIMEOUT_SECONDS
        response = None
        for attempt in range(1, attempts + 1):
            request_headers = {**(headers or self.get_headers())}
            request_headers["User-Agent"] = self.user_agent

            response = self.http_client.get(
                url,
                options=HttpRequestOptions(
                    headers=request_headers,
                    params=params,
                    impersonate=self.impersonation,
                    timeout=timeout_value,
                    verify=verify,
                ),
            )

            if (
                response is not None
                and response.status_code not in RETRYABLE_STATUS_CODES
            ):
                self._consecutive_failures = 0
                return response
            if attempt == attempts:
                break
            # Blocked or transient: wait politely, then switch to a new identity.
            self._sleep_before_retry(response, attempt)
            self.rotate_fingerprint()

        self._consecutive_failures += 1
        if response is None:
            logger.warning("HTTP GET blocked/failed for %s", url)
        return response

    def _sleep_before_retry(self, response: object | None, attempt: int) -> None:
        """Wait before a retry, honoring ``Retry-After`` when the server sends it."""
        retry_after = parse_retry_after(response) if response is not None else None
        if retry_after is not None:
            logger.info(
                "Honoring Retry-After=%.1fs for %s",
                retry_after,
                self.BRAND_NAME,
            )
            time.sleep(retry_after)
            return
        backoff = self.HTTP_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
        self.sleep_random(backoff, backoff + 1.0)
