import logging
from decimal import Decimal

from django.db import transaction

from .models import ScrapedItem

logger = logging.getLogger(__name__)


class ScraperService:
    @staticmethod
    @transaction.atomic
    def save_product(
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
    ) -> ScrapedItem | None:
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
            },
        )

        action = "Created" if created else "Updated"
        logger.debug(f"{action} item {external_id} for {store_slug}")

        return obj
