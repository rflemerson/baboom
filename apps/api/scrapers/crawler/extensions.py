"""Small Scrapy extensions used by the Celery subprocess runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scrapy.crawler import Crawler
    from scrapy.spiders import Spider

from scrapy import signals


class StatsDumpExtension:
    """Write Scrapy statistics to the path supplied by the task runner."""

    def __init__(self, crawler: Crawler, output_path: str) -> None:
        """Hold the crawler and the path its statistics are written to."""
        self.crawler = crawler
        self.output_path = output_path

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> StatsDumpExtension:
        """Build the extension from the process settings."""
        output_path = crawler.settings.get("SCRAPER_STATS_FILE", "")
        extension = cls(crawler, output_path)
        crawler.signals.connect(extension.spider_closed, signal=signals.spider_closed)
        return extension

    def spider_closed(self, spider: Spider, reason: str) -> None:
        """Persist stats after the spider has closed."""
        _ = spider, reason
        if not self.output_path:
            return
        Path(self.output_path).write_text(
            json.dumps(self.crawler.stats.get_stats(), default=str),
            encoding="utf-8",
        )
