"""Mutations for scraper control and item lifecycle operations."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

import strawberry
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.models import ScrapedItem, ScrapedPage

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from .types import ScrapedItemType

MAX_SCRAPED_ITEM_RETRIES = 3


@strawberry.type
class ScrapersMutation:
    """Mutations for scraper management."""

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def checkout_scraped_item(
        self,
        force: bool = False,
        target_item_id: int | None = None,
    ) -> ScrapedItemType | None:
        """Reserves an item for the Agent to process.

        Retrieves NEW items or ERROR items that have rested for 30 minutes.
        If `force` is True, also allows LINKED or REVIEW items.
        If `target_item_id` is provided, only that specific item is checked out.
        """
        now = timezone.now()
        retry_threshold = now - timedelta(minutes=30)

        with transaction.atomic():
            base_query = cast(
                "QuerySet[ScrapedItem]",
                ScrapedItem.objects.select_for_update(skip_locked=True),
            )

            if target_item_id:
                query = base_query.filter(id=target_item_id)
            else:
                q_filters = Q(status=ScrapedItem.Status.NEW) | Q(
                    status=ScrapedItem.Status.ERROR,
                    error_count__lt=MAX_SCRAPED_ITEM_RETRIES,
                    last_attempt_at__lt=retry_threshold,
                )
                if force:
                    q_filters |= Q(status=ScrapedItem.Status.LINKED) | Q(
                        status=ScrapedItem.Status.REVIEW,
                    )

                query = base_query.filter(
                    q_filters,
                    source_page__url__startswith="http",
                )

            item = query.order_by("updated_at").first()

            if item:
                item.status = ScrapedItem.Status.PROCESSING
                item.last_attempt_at = now
                item.save()
                return cast("ScrapedItemType", item)

            return None

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def report_scraped_item_error(
        self,
        item_id: int,
        message: str,
        is_fatal: bool = False,
    ) -> bool:
        """Report an error for a scraped item."""
        try:
            item = ScrapedItem.objects.get(id=item_id)

            if is_fatal:
                item.status = ScrapedItem.Status.REVIEW
                item.last_error_log = f"FATAL: {message}"
            else:
                item.status = ScrapedItem.Status.ERROR
                item.error_count += 1
                item.last_error_log = message

                if item.error_count >= MAX_SCRAPED_ITEM_RETRIES:
                    item.status = ScrapedItem.Status.REVIEW
                    item.last_error_log += " (Max retries reached)"

            item.save()
        except ScrapedItem.DoesNotExist:
            return False

        return True

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def discard_scraped_item(self, item_id: int, reason: str) -> bool:
        """Agent marks item as DISCARDED (e.g., T-shirt, not supplement)."""
        try:
            item = ScrapedItem.objects.get(id=item_id)
            item.status = ScrapedItem.Status.DISCARDED
            item.last_error_log = f"Discarded by Agent: {reason}"
            item.save()
        except ScrapedItem.DoesNotExist:
            return False

        return True

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def ensure_scraped_item_source_page(
        self,
        item_id: int,
        url: str,
        store_slug: str,
    ) -> ScrapedItemType | None:
        """Ensure item has source page linked, creating page by URL when needed."""
        try:
            item = ScrapedItem.objects.get(id=item_id)
            page, _ = ScrapedPage.objects.get_or_create(
                url=url,
                defaults={"store_slug": store_slug},
            )
            changed = False
            if item.source_page_id != page.id:
                item.source_page = page
                changed = True
            if item.store_slug != store_slug:
                item.store_slug = store_slug
                changed = True
            if changed:
                item.save()
            return cast("ScrapedItemType", item)
        except ScrapedItem.DoesNotExist:
            return None

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def update_scraped_item_data(
        self,
        item_id: int,
        name: str | None = None,
        source_page_url: str | None = None,
        store_slug: str | None = None,
    ) -> ScrapedItemType | None:
        """Update mutable fields of a scraped item used by agents pipeline."""
        try:
            item = ScrapedItem.objects.get(id=item_id)
            changed = False
            if name:
                item.name = name
                changed = True
            if source_page_url:
                resolved_store = store_slug or item.store_slug
                page, _ = ScrapedPage.objects.get_or_create(
                    url=source_page_url,
                    defaults={"store_slug": resolved_store},
                )
                if item.source_page_id != page.id:
                    item.source_page = page
                    changed = True
            if store_slug and item.store_slug != store_slug:
                item.store_slug = store_slug
                changed = True
            if changed:
                item.save()
            return cast("ScrapedItemType", item)
        except ScrapedItem.DoesNotExist:
            return None

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def upsert_scraped_item_variant(
        self,
        origin_item_id: int,
        external_id: str,
        name: str,
        page_url: str,
        store_slug: str,
        price: float | None = None,
        stock_status: str | None = None,
    ) -> ScrapedItemType | None:
        """Create or update a variant ScrapedItem linked to the same source page."""
        try:
            origin_item = ScrapedItem.objects.get(id=origin_item_id)
        except ScrapedItem.DoesNotExist:
            return None

        page, _ = ScrapedPage.objects.get_or_create(
            url=page_url,
            defaults={"store_slug": store_slug},
        )

        resolved_price = price if price is not None else origin_item.price
        resolved_stock_status = stock_status or origin_item.stock_status
        valid_stock_values = {choice[0] for choice in ScrapedItem.StockStatus.choices}
        if resolved_stock_status not in valid_stock_values:
            resolved_stock_status = ScrapedItem.StockStatus.AVAILABLE

        item, _ = ScrapedItem.objects.update_or_create(
            store_slug=store_slug,
            external_id=external_id,
            defaults={
                "name": name,
                "source_page": page,
                "price": resolved_price,
                "stock_status": resolved_stock_status,
                "status": ScrapedItem.Status.PROCESSING,
            },
        )
        return cast("ScrapedItemType", item)
