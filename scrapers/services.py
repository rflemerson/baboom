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
        Saves raw scraped data to ScrapedItem.
        Does NOT attempt to link to products or create them (Pure Ingestion).
        """
        external_id = str(data.get("item_id"))
        product_url = data.get("url", store_url_base)
        ean = data.get("ean", data.get("gtin", data.get("barcode", "")))

        if not external_id:
            logger.warning(f"Skipping item due to missing ID: {data}")
            return None

        # Pure Data Lake Ingestion
        obj, _ = ScrapedItem.objects.update_or_create(
            url=product_url,
            defaults={
                "store": store_slug,
                "external_id": external_id,
                "ean": ean,
                "raw_data": data,
                # Note: We do NOT update status here.
                # If it's NEW/LINKED/IGNORED, we strictly update the data.
            },
        )
        return obj
