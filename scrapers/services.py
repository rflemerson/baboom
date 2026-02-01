import logging

from django.db import transaction

from core.models import ProductPriceHistory

from .models import ScrapedItem
from .types import ProductIngestionInput

logger = logging.getLogger(__name__)


class ScraperService:
    """Service for handling scraped data."""

    @staticmethod
    @transaction.atomic
    def save_product(data: ProductIngestionInput) -> ScrapedItem | None:
        """Create or update a ScrapedItem."""
        obj, created = ScrapedItem.objects.update_or_create(
            store_slug=data.store_slug,
            external_id=data.external_id,
            defaults={
                "product_link": data.url,
                "name": data.name,
                "price": data.price,
                "stock_quantity": data.stock_quantity,
                "stock_status": data.stock_status,
                "ean": data.ean,
                "sku": data.sku,
                "pid": data.pid,
                "category": data.category,
            },
        )

        action = "Created" if created else "Updated"
        logger.debug(f"{action} item {data.external_id} for {data.store_slug}")

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
