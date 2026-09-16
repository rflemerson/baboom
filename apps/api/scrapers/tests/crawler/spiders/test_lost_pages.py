"""A lost page has to be recorded, on every platform."""

from __future__ import annotations

from operator import attrgetter
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from scrapy import Request
from scrapy.http import TextResponse

from scrapers.stores.dark_lab import DarkLabSpider
from scrapers.stores.dux import DuxSpider
from scrapers.stores.growth import GrowthSpider
from scrapers.stores.max_titanium import MaxTitaniumSpider


def _response(url: str, body: str, status: int, meta: dict) -> TextResponse:
    request = Request(url, meta=meta)
    return TextResponse(url, body=body.encode(), status=status, request=request)


class LostPageTests(SimpleTestCase):
    """A page the spider could not read marks the crawl incomplete."""

    def _spider(self, spider_class: type) -> object:
        spider = spider_class()
        spider.crawler = MagicMock()
        spider.crawler.stats.get_value = MagicMock(return_value=None)
        return spider

    def _failed_pages(self, spider: object) -> int:
        calls = [
            call.args
            for call in spider.crawler.stats.inc_value.call_args_list
            if call.args and call.args[0] == "scraper/pages_failed"
        ]
        return len(calls)

    def test_shopify_category_http_error_is_recorded(self) -> None:
        """A collection page answering 500 is a page the crawl did not read."""
        spider = self._spider(DarkLabSpider)
        response = _response(
            "https://example.com/collections/whey/products.json",
            "{}",
            500,
            {"category": "whey", "page": 1},
        )

        list(attrgetter("_parse_category")(spider)(response))

        assert self._failed_pages(spider) == 1

    def test_nuvemshop_category_http_error_is_recorded(self) -> None:
        """Nuvemshop answering 503 for a listing page is a lost page."""
        spider = self._spider(DuxSpider)
        response = _response(
            "https://example.com/whey",
            "",
            503,
            {"category": "whey", "page": 1},
        )

        list(attrgetter("_parse_category")(spider)(response))

        assert self._failed_pages(spider) == 1

    def test_wapstore_category_http_error_is_recorded(self) -> None:
        """Wap.Store answering 502 for a listing page is a lost page."""
        spider = self._spider(GrowthSpider)
        response = _response(
            "https://example.com/api/produtos",
            "",
            502,
            {"category": "whey", "offset": 0},
        )

        list(attrgetter("_parse_category")(spider)(response))

        assert self._failed_pages(spider) == 1

    def test_vtex_search_unreadable_payload_is_recorded(self) -> None:
        """A category page that is not JSON is a page the crawl did not read."""
        spider = self._spider(MaxTitaniumSpider)
        response = _response(
            "https://example.com/api/catalog_system/pub/products/search",
            "<html>nope</html>",
            200,
            {"category": "whey", "start": 0},
        )

        list(attrgetter("_parse_category")(spider)(response))

        assert self._failed_pages(spider) == 1
