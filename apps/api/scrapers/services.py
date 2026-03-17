"""Services for persisting and syncing scraped catalog data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

from core.models import ProductPriceHistory

from .models import ScrapedItem, ScrapedPage

if TYPE_CHECKING:
    from .types import ProductIngestionInput

logger = logging.getLogger(__name__)


class ScraperService:
    """Service for handling scraped data."""

    @staticmethod
    @transaction.atomic
    def save_product(data: ProductIngestionInput) -> ScrapedItem | None:
        """Create or update a ScrapedItem."""
        # Ensure ScrapedPage exists
        page, _ = ScrapedPage.objects.get_or_create(
            url=data.url,
            defaults={"store_slug": data.store_slug},
        )

        obj, created = ScrapedItem.objects.update_or_create(
            store_slug=data.store_slug,
            external_id=data.external_id,
            defaults={
                "name": data.name,
                "price": data.price,
                "stock_quantity": data.stock_quantity,
                "stock_status": data.stock_status,
                "ean": data.ean,
                "sku": data.sku,
                "pid": data.pid,
                "category": data.category,
                "source_page": page,
            },
        )

        action = "Created" if created else "Updated"
        logger.debug("%s item %s for %s", action, data.external_id, data.store_slug)

        if obj.product_store_id:
            ScraperService.sync_price_to_core(obj)

        return obj

    @staticmethod
    def sync_price_to_core(scraped_item: ScrapedItem) -> bool:
        """Sync price and stock from a linked scraped item to price history."""
        if not scraped_item.product_store_id:
            return False

        if scraped_item.price is None:
            return False

        product_store = scraped_item.product_store
        if product_store is None:
            return False

        last_history = product_store.price_history.values(
            "price",
            "stock_status",
        ).first()

        price_changed = (
            last_history is None or last_history["price"] != scraped_item.price
        )
        stock_changed = (
            last_history is None
            or last_history["stock_status"] != scraped_item.stock_status
        )

        if not price_changed and not stock_changed:
            return False

        ProductPriceHistory.objects.create(
            store_product_link=product_store,
            price=scraped_item.price,
            stock_status=scraped_item.stock_status,
        )

        logger.info(
            "Synced price for %s: R$%s",
            scraped_item.store_slug,
            scraped_item.price,
        )
        return True

    @staticmethod
    def persist_item_context(
        saved_item: object | None,
        context_payload: str,
    ) -> None:
        """Persist structured scraper context into source page when available."""
        if not saved_item or not saved_item.source_page_id:
            return
        page = saved_item.source_page
        if page is None:
            return
        page.raw_content = context_payload
        page.content_type = "JSON"
        page.save(update_fields=["raw_content", "content_type"])
