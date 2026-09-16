"""Small Scrapy extensions used by the Celery runner."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from scrapy import signals

if TYPE_CHECKING:
    from scrapy.crawler import Crawler
    from scrapy.spiders import Spider


class _LastErrorHandler(logging.Handler):
    """Keep the most recent error so the run record can name what broke."""

    def __init__(self) -> None:
        """Start with no error recorded."""
        super().__init__(level=logging.ERROR)
        self.last_error = ""

    def emit(self, record: logging.LogRecord) -> None:
        """Remember the formatted message of the latest error record."""
        self.last_error = record.getMessage()


class StatsDumpExtension:
    """Write Scrapy statistics to the path supplied by the task runner.

    The runner reads the crawl outcome from this file rather than from the
    child's output, which it no longer captures.
    """

    def __init__(self, crawler: Crawler, output_path: str) -> None:
        """Hold the crawler and the path its statistics are written to."""
        self.crawler = crawler
        self.output_path = output_path
        self.handler = _LastErrorHandler()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> StatsDumpExtension:
        """Build the extension from the process settings."""
        output_path = crawler.settings.get("SCRAPER_STATS_FILE", "")
        extension = cls(crawler, output_path)
        crawler.signals.connect(extension.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(extension.spider_closed, signal=signals.spider_closed)
        return extension

    def spider_opened(self, spider: Spider) -> None:
        """Start listening for errors anywhere in the crawl."""
        _ = spider
        logging.getLogger().addHandler(self.handler)

    @staticmethod
    def _catalog_is_complete(stats: dict[str, object], reason: str) -> bool:
        """Whether this crawl read the whole catalog, not merely ended.

        Only a complete reading can turn an absence into evidence. A crawl that
        stopped early, skipped a page, raised in a callback, or collected
        nothing says where products are, never where they no longer are.
        """
        if reason != "finished" or stats.get("scraper/pages_failed"):
            return False
        if any(str(key).startswith("spider_exceptions") for key in stats):
            return False
        try:
            collected = int(stats.get("item_scraped_count", 0) or 0)
        except TypeError, ValueError:
            return False
        return collected > 0

    def spider_closed(self, spider: Spider, reason: str) -> None:
        """Persist stats, the close reason, and the last error seen."""
        _ = spider
        logging.getLogger().removeHandler(self.handler)
        if not self.output_path:
            return
        payload = dict(self.crawler.stats.get_stats())
        payload["finish_reason"] = reason
        payload["last_error"] = self.handler.last_error
        payload["scraper/catalog_complete"] = self._catalog_is_complete(payload, reason)
        Path(self.output_path).write_text(
            json.dumps(payload, default=str),
            encoding="utf-8",
        )
