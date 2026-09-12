"""Services for persisting and syncing scraped catalog data."""

from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from django.db import transaction

from offers.services import OfferObservationResult, OfferObservationService

from .models import ScrapedItem, ScrapedPage

if TYPE_CHECKING:
    from .dtos import ScrapedItemIngestionInput

logger = logging.getLogger(__name__)


class ScraperService:
    """Service for handling scraped data."""

    @staticmethod
    @transaction.atomic
    def save_product(
        data: ScrapedItemIngestionInput,
        *,
        api_context: str | dict | None = None,
    ) -> ScrapedItem:
        """Record the merchant offer and its captured source-page link.

        The offer (identity, price, stock) is upserted on every run and the
        page's ``api_context`` keeps the latest raw catalog payload. The
        product page itself is never fetched here, or anywhere else.
        """
        normalized_context = (
            ScraperService._normalize_api_context_payload(api_context)
            if api_context is not None
            else None
        )
        page, _created = ScrapedPage.objects.get_or_create(
            url=data.url,
            defaults={
                "store_slug": data.store_slug,
                "api_context": normalized_context or {},
            },
        )

        page_updates: list[str] = []
        if page.store_slug != data.store_slug:
            page.store_slug = data.store_slug
            page_updates.append("store_slug")

        observation = ScraperService.record_offer_observation(data)

        item, item_created = ScrapedItem.objects.get_or_create(
            offer=observation.offer,
            defaults={"source_page": page},
        )
        if not item_created and item.source_page_id != page.id:
            item.source_page = page
            item.save(update_fields=["source_page", "updated_at"])

        if normalized_context is not None and page.api_context != normalized_context:
            page.api_context = normalized_context
            page_updates.append("api_context")
        if page_updates:
            page.save(update_fields=page_updates)

        action = "Created" if item_created else "Updated"
        logger.debug("%s item %s for %s", action, data.external_id, data.store_slug)

        return item

    @staticmethod
    def record_offer_observation(
        data: ScrapedItemIngestionInput,
    ) -> OfferObservationResult:
        """Record the merchant offer and its price via the offers domain service.

        This is the price source of truth for the pricing domain. It is written
        from the first time the scraper sees an offer, independent of whether the
        offer has been linked to a catalog product yet.
        """
        return OfferObservationService().record(
            store_slug=data.store_slug,
            external_id=data.external_id,
            price=ScraperService._normalize_price(data.price),
            stock_status=data.stock_status,
            snapshot={
                "name": data.name,
                "category": data.category,
                "url": data.url,
                "ean": data.ean,
                "sku": data.sku,
                "pid": data.pid,
                "current_stock_quantity": data.stock_quantity,
            },
        )

    @staticmethod
    def _normalize_price(value: str | float | Decimal | None) -> Decimal | None:
        """Convert a raw scraped price into a Decimal, or None when absent."""
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value))
        except InvalidOperation, ValueError:
            logger.warning("Could not parse scraped price value: %r", value)
            return None

    @staticmethod
    def _normalize_api_context_payload(context_payload: str | dict) -> dict:
        """Convert scraper context payloads into a JSON-serializable dict."""
        if isinstance(context_payload, dict):
            return context_payload
        if not context_payload:
            return {}
        try:
            parsed = json.loads(context_payload)
        except json.JSONDecodeError:
            logger.warning("Could not decode scraper API context payload as JSON")
            return {}
        return parsed if isinstance(parsed, dict) else {}
