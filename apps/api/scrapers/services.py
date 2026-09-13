"""Services for persisting and syncing scraped catalog data."""

from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from django.db import transaction

from offers.services import OfferObservationResult, OfferObservationService

from .contracts import ScrapedItemIngestionInput
from .models import ScrapedItem, ScrapedPage

if TYPE_CHECKING:
    from .contracts import ScrapedProductInput, VariantContext

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
            url=data.page_url,
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

        item, item_created = ScraperService._upsert_scraped_item(
            observation,
            page,
            data.variant_context,
        )

        if normalized_context is not None and page.api_context != normalized_context:
            page.api_context = normalized_context
            page_updates.append("api_context")
        if page_updates:
            page.save(update_fields=page_updates)

        action = "Created" if item_created else "Updated"
        logger.debug("%s item %s for %s", action, data.external_id, data.store_slug)

        return item

    @staticmethod
    @transaction.atomic
    def save_product_snapshot(product: ScrapedProductInput) -> list[ScrapedItem]:
        """Persist one normalized page and all of its independently priced units."""
        normalized_context = ScraperService._normalize_api_context_payload(
            product.api_context,
        )
        page, _created = ScrapedPage.objects.get_or_create(
            url=product.page_url,
            defaults={
                "store_slug": product.store_slug,
                "api_context": normalized_context,
            },
        )

        page_updates: list[str] = []
        if page.store_slug != product.store_slug:
            page.store_slug = product.store_slug
            page_updates.append("store_slug")
        if page.api_context != normalized_context:
            page.api_context = normalized_context
            page_updates.append("api_context")
        if page_updates:
            page.save(update_fields=page_updates)

        saved: list[ScrapedItem] = []
        for offer in product.offers:
            data = ScrapedItemIngestionInput(
                store_slug=product.store_slug,
                external_id=offer.external_id,
                page_url=product.page_url,
                offer_url=offer.offer_url,
                variant_context=offer.variant_context,
                name=offer.name,
                price=offer.price,
                stock_quantity=offer.stock_quantity,
                stock_status=offer.stock_status,
                ean=offer.ean,
                sku=offer.sku,
                pid=product.provider_product_id,
                category=product.category,
            )
            observation = ScraperService.record_offer_observation(data)
            item, _created = ScraperService._upsert_scraped_item(
                observation,
                page,
                offer.variant_context,
            )
            saved.append(item)

        return saved

    @staticmethod
    def _upsert_scraped_item(
        observation: OfferObservationResult,
        page: ScrapedPage,
        variant_context: VariantContext,
    ) -> tuple[ScrapedItem, bool]:
        """Bind an observed offer to its source page and variant context."""
        serialized_context = variant_context.model_dump(mode="json")
        item, item_created = ScrapedItem.objects.get_or_create(
            offer=observation.offer,
            defaults={
                "source_page": page,
                "variant_context": serialized_context,
            },
        )
        item_updates: list[str] = []
        if item.source_page_id != page.id:
            item.source_page = page
            item_updates.append("source_page")
        if item.variant_context != serialized_context:
            item.variant_context = serialized_context
            item_updates.append("variant_context")
        if not item_created and item_updates:
            item.save(update_fields=[*item_updates, "updated_at"])
        return item, item_created

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
                "url": data.offer_url,
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
