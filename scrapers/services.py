import logging
from decimal import Decimal

from django.db import transaction

from core.models import ProductPriceHistory

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
        category: str = "",
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
                "category": category,
            },
        )

        action = "Created" if created else "Updated"
        logger.debug(f"{action} item {external_id} for {store_slug}")

        return obj

    @staticmethod
    def sync_price_to_core(scraped_item: ScrapedItem) -> bool:
        """
        Sincroniza preço/estoque de um ScrapedItem linkado para ProductPriceHistory.

        Só cria novo registro se:
        1. Item está LINKED
        2. Preço OU estoque mudou desde último registro

        Returns:
            True se criou novo registro, False caso contrário
        """
        if scraped_item.status != ScrapedItem.Status.LINKED:
            logger.debug(f"Item {scraped_item} not LINKED, skipping sync")
            return False

        if not scraped_item.product_store:
            logger.warning(f"Item {scraped_item} is LINKED but has no product_store")
            return False

        if scraped_item.price is None:
            logger.warning(f"Item {scraped_item} has no price, skipping sync")
            return False

        last_price = scraped_item.product_store.price_history.first()

        price_changed = last_price is None or last_price.price != scraped_item.price
        stock_changed = (
            last_price is None or last_price.stock_status != scraped_item.stock_status
        )

        if not price_changed and not stock_changed:
            logger.debug(f"No price/stock change for {scraped_item}, skipping sync")
            return False

        ProductPriceHistory.objects.create(
            store_product_link=scraped_item.product_store,
            price=scraped_item.price,
            stock_status=scraped_item.stock_status,
        )
        logger.info(
            f"Created PriceHistory for {scraped_item.product_store}: "
            f"R${scraped_item.price} ({scraped_item.get_stock_status_display()})"
        )
        return True
