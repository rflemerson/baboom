"""Scrapy spider template for a structured JSON feed of listings."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ...normalizers.feed import FeedNormalizer
from ..base import CatalogSpider

if TYPE_CHECKING:
    from collections.abc import Iterator

    from scrapy import Request
    from scrapy.http import Response

    from ...contracts import ScrapedProductInput

FEED_SUCCESS_CODE = 200


class FeedSpider(CatalogSpider):
    """Read a paged JSON feed: ``{"listings": [...], "next": url | null}``.

    A store or marketplace on this adapter is configuration only: its slug,
    name, feed URL and market. A page that fails marks the crawl incomplete.
    """

    normalizer = FeedNormalizer()
    FEED_URL = ""
    CATEGORY = "feed"

    def category_discovery_request(self) -> Request:
        """Start at the first feed page."""
        return self.request(self.FEED_URL, callback=self.parse_feed)

    def category_request(self, category: str) -> Request:
        """Read the feed: it has no categories."""
        _ = category
        return self.category_discovery_request()

    def parse_feed(self, response: Response) -> Iterator[ScrapedProductInput | Request]:
        """Emit every listing of one page, then follow the next page."""
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.mark_incomplete(f"feed page {response.url} is not JSON")
            return
        if response.status != FEED_SUCCESS_CODE or not isinstance(payload, dict):
            self.mark_incomplete(f"feed page {response.url} answered {response.status}")
            return
        yield from self.emit_products(payload.get("listings") or [], self.CATEGORY)
        if next_url := payload.get("next"):
            yield self.request(str(next_url), callback=self.parse_feed)

    def product_id(self, raw: dict) -> str:
        """Feed listings are unique by id."""
        return str(raw.get("id") or "")
