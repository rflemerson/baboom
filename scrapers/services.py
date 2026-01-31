import logging
from decimal import Decimal

from django.db import transaction

from core.models import ProductPriceHistory

from .models import ScrapedItem

logger = logging.getLogger(__name__)


class ScraperService:
    """Service for handling scraped data."""

    @staticmethod
    @transaction.atomic
    def save_product(  # noqa: PLR0913
        store_slug: str,
        external_id: str,
        *,
        url: str = "",
        name: str = "",
        price: str | float | Decimal | None = None,
        stock_quantity: int | None = None,
        stock_status: ScrapedItem.StockStatus = ScrapedItem.StockStatus.AVAILABLE,
        ean: str = "",
        sku: str = "",
        pid: str = "",
        category: str = "",
    ) -> ScrapedItem | None:
        """Create or update a ScrapedItem."""
        # 1. Save raw data (staging)
        obj, created = ScrapedItem.objects.update_or_create(
            store_slug=store_slug,
            external_id=external_id,
            defaults={
                "product_link": url,
                "name": name,
                "price": price,
                "stock_quantity": stock_quantity,
                "stock_status": stock_status,
                "ean": ean,
                "sku": sku,
                "pid": pid,
                "category": category,
            },
        )

        action = "Created" if created else "Updated"
        logger.debug(f"{action} item {external_id} for {store_slug}")

        if obj.product_store_id:
            ScraperService.sync_price_to_core(obj)

        return obj

    @staticmethod
    def sync_price_to_core(scraped_item: ScrapedItem) -> bool:
        """Syncs price/stock from a LINKED ScrapedItem to ProductPriceHistory."""
        if not scraped_item.product_store_id:
            return False

        if scraped_item.price is None:
            return False

        product_store = scraped_item.product_store
        if product_store is None:
            return False

        last_history = product_store.price_history.values(
            "price", "stock_status"
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
            f"Synced Price for {scraped_item.store_slug}: R${scraped_item.price}"
        )
        return True
