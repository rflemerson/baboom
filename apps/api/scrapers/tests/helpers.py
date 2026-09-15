"""Shared helpers for scraper tests."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from offers.models import Offer, StockStatus
from scrapers.models import ScrapedItem, ScrapedPage

if TYPE_CHECKING:
    from collections.abc import Callable

    from scrapers.contracts import ScrapedProductInput
    from scrapers.crawler.base import CatalogSpider

EXPECTED_EXTERNAL_STOCK_QUANTITY = 100
EXPECTED_PRICE_HISTORY_RECORDS_AFTER_UPDATE = 2
EXPECTED_COMMA_DECIMAL_PRICE = 149.9
EXPECTED_SHOPIFY_JS_PRICE = 13.9
EXPECTED_GROWTH_DECIMAL_PRICE = 139.9
EXPECTED_GROWTH_CURRENCY_PRICE = 89.5
EXPECTED_VTEX_DECIMAL_PRICE = 99.9
EXPECTED_VTEX_INTEGER_PRICE = 55.0
DUX_EXPECTED_STOCK = 42
EXPECTED_MONITOR_ITEMS = 2
EXPECTED_FALLBACK_CATEGORY_COUNT = 2
EXPECTED_SCRAPER_RUN_ITEMS = 2

type ScrapedJsonObject = dict[str, object]

logging.getLogger("scrapers").setLevel(logging.CRITICAL)


def _raised(operation: Callable[[], object], expected: type[Exception]) -> Exception:
    """Return the exception an operation is expected to raise."""
    try:
        operation()
    except expected as error:
        return error
    message = f"Expected {expected.__name__} to be raised."
    raise AssertionError(message)


def _scraped_item(**kwargs: object) -> ScrapedItem:
    """Create a scraped item backed by a merchant offer for tests."""
    store_slug = cast("str", kwargs["store_slug"])
    external_id = cast("str", kwargs["external_id"])
    name = cast("str", kwargs.get("name", ""))
    price = cast("Decimal | float | None", kwargs.get("price"))
    stock_status = cast("str", kwargs.get("stock_status", StockStatus.AVAILABLE))
    source_page = cast("ScrapedPage | None", kwargs.get("source_page"))
    resolved_price = Decimal(str(price)) if price is not None else None
    offer = Offer.objects.create(
        store_slug=store_slug,
        external_id=external_id,
        name=name,
        url=source_page.url if source_page else "",
        current_price=resolved_price,
        current_stock_status=stock_status,
    )
    return ScrapedItem.objects.create(offer=offer, source_page=source_page)


def _normalize_spider_item(
    spider: CatalogSpider,
    item: ScrapedJsonObject,
    category: str,
) -> ScrapedProductInput | None:
    """Normalize a fixture without crossing the persistence boundary."""
    return spider.normalizer.normalize(
        item,
        store_slug=spider.STORE_SLUG,
        base_url=spider.BASE_URL,
        category=category,
    )
