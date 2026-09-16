"""Tests for the Scrapy extensions used by the crawler runner."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from scrapers.crawler.extensions import StatsDumpExtension

EXPECTED_ITEM_COUNT = 3
EXPECTED_REQUEST_COUNT = 4


class StatsDumpExtensionTests(SimpleTestCase):
    """The stats extension persists crawl state without leaking handlers."""

    def test_close_writes_stats_reason_and_latest_error(self) -> None:
        """Closing a crawl writes its stats and the most recent error message."""
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "stats.json"
            crawler = SimpleNamespace(
                settings=MagicMock(
                    get=MagicMock(return_value=str(output_path)),
                ),
                signals=MagicMock(),
                stats=MagicMock(
                    get_stats=MagicMock(
                        return_value={
                            "item_scraped_count": EXPECTED_ITEM_COUNT,
                            "downloader/request_count": EXPECTED_REQUEST_COUNT,
                        },
                    ),
                ),
            )
            extension = StatsDumpExtension.from_crawler(crawler)
            root_logger = logging.getLogger()

            extension.spider_opened(SimpleNamespace())
            logging.getLogger("stats_extension_test").error("first failure")
            logging.getLogger("stats_extension_test").error("latest failure")
            extension.spider_closed(SimpleNamespace(), "finished")

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            assert payload == {
                "item_scraped_count": EXPECTED_ITEM_COUNT,
                "downloader/request_count": EXPECTED_REQUEST_COUNT,
                "finish_reason": "finished",
                "last_error": "latest failure",
                "scraper/catalog_complete": True,
            }
            assert extension.handler not in root_logger.handlers

    def test_close_without_output_path_only_removes_the_handler(self) -> None:
        """A disabled stats file still cleans up its root logging handler."""
        crawler = SimpleNamespace(
            settings=MagicMock(get=MagicMock(return_value="")),
            signals=MagicMock(),
            stats=MagicMock(),
        )
        extension = StatsDumpExtension.from_crawler(crawler)
        root_logger = logging.getLogger()

        extension.spider_opened(SimpleNamespace())
        extension.spider_closed(SimpleNamespace(), "finished")

        assert extension.handler not in root_logger.handlers
        crawler.stats.get_stats.assert_not_called()


class CatalogCompletenessTests(SimpleTestCase):
    """Finishing is not the same as having read the whole catalog."""

    def _closed_payload(self, stats: dict[str, object], reason: str) -> dict:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "stats.json"
            crawler = SimpleNamespace(
                settings=MagicMock(get=MagicMock(return_value=str(output_path))),
                signals=MagicMock(),
                stats=MagicMock(get_stats=MagicMock(return_value=stats)),
            )
            extension = StatsDumpExtension.from_crawler(crawler)
            extension.spider_opened(SimpleNamespace())
            extension.spider_closed(SimpleNamespace(), reason)
            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_a_clean_finish_with_items_is_complete(self) -> None:
        """Every page read, items collected, nothing failed."""
        payload = self._closed_payload({"item_scraped_count": 1}, "finished")

        assert payload["scraper/catalog_complete"] is True

    def test_a_failed_page_makes_the_catalog_incomplete(self) -> None:
        """One category that could not be read leaves the catalog unproven."""
        payload = self._closed_payload(
            {"item_scraped_count": 1, "scraper/pages_failed": 1},
            "finished",
        )

        assert payload["scraper/catalog_complete"] is False

    def test_a_crawl_without_items_is_incomplete(self) -> None:
        """Collecting nothing is never evidence that a store emptied."""
        payload = self._closed_payload({"item_scraped_count": 0}, "finished")

        assert payload["scraper/catalog_complete"] is False

    def test_a_spider_exception_makes_the_catalog_incomplete(self) -> None:
        """A callback that raised leaves part of the catalog unread."""
        payload = self._closed_payload(
            {"item_scraped_count": 2, "spider_exceptions/KeyError": 1},
            "finished",
        )

        assert payload["scraper/catalog_complete"] is False

    def test_a_closed_crawl_is_incomplete(self) -> None:
        """A crawl stopped early read only part of the catalog."""
        payload = self._closed_payload(
            {"item_scraped_count": 9},
            "closespider_timeout",
        )

        assert payload["scraper/catalog_complete"] is False
