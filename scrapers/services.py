import logging
from typing import Any

from django.db import transaction

from .models import ScrapedItem

logger = logging.getLogger(__name__)


class ScraperService:
    @staticmethod
    @transaction.atomic
    def save_product_from_datalayer(
        data: dict[str, Any], store_url_base: str, store_slug: str
    ):
        """
        Saves raw scraped data to ScrapedItem (Pure Ingestion).
        """
        external_id = str(data.get("item_id"))
        sku = str(data.get("sku", ""))
        ean = data.get("ean", data.get("gtin", data.get("barcode", ""))) or ""
        product_url = data.get("url", store_url_base)

        if not external_id:
            logger.warning(f"Skipping item due to missing ID: {data}")
            return None

        # Pure Data Lake Ingestion
        # Update logic: Store + SKU is the unique constraint.
        obj, _ = ScrapedItem.objects.update_or_create(
            store=store_slug,
            sku=sku,
            defaults={
                "url": product_url,  # URL is now just data, not key
                "external_id": external_id,
                "ean": ean,
                "raw_data": data,
            },
        )
        return obj
