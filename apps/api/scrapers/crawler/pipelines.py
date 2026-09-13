"""Scrapy item pipelines for catalog persistence."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable
from typing import TYPE_CHECKING

from ..services import ScraperService

if TYPE_CHECKING:
    from ..contracts import ScrapedProductInput


class CatalogPipeline:
    """Persist normalized pages through the existing scraper service."""

    _save_lock = threading.Lock()

    def process_item(
        self,
        item: ScrapedProductInput,
        spider: object,
    ) -> ScrapedProductInput | Awaitable[ScrapedProductInput]:
        """Save one normalized product page and pass it onward unchanged."""
        _ = spider
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            ScraperService.save_product_snapshot(item)
            return item
        return self._process_item_async(item)

    async def _process_item_async(self, item: ScrapedProductInput) -> ScrapedProductInput:
        """Move synchronous Django writes off Scrapy's asyncio event loop."""
        await asyncio.to_thread(self._save, item)
        return item

    def _save(self, item: ScrapedProductInput) -> list[object]:
        """Serialize writes across worker threads while keeping Scrapy non-blocking."""
        with self._save_lock:
            return ScraperService.save_product_snapshot(item)
