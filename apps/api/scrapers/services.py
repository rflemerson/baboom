"""Services for persisting and syncing scraped catalog data."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Case, IntegerField, Q, QuerySet, Value, When
from django.utils import timezone

from core.models import ProductPriceHistory

from .models import ScrapedItem, ScrapedPage

if TYPE_CHECKING:
    from .dtos import ScrapedItemIngestionInput
    from .graphql.inputs import ScrapedItemCheckoutInput, ScrapedItemVariantInput

logger = logging.getLogger(__name__)


class ScrapedItemCheckoutService:
    """Reserve one scraped item for agent processing."""

    MAX_RETRIES = 3
    RETRY_COOLDOWN = timedelta(minutes=30)
    FORCED_ELIGIBLE_STATUSES = (
        ScrapedItem.Status.LINKED,
        ScrapedItem.Status.REVIEW,
    )

    def execute(self, data: ScrapedItemCheckoutInput) -> ScrapedItem | None:
        """Select and lock the next scraped item for checkout."""
        now = timezone.now()

        with transaction.atomic():
            item = self._selected_item(data=data, now=now)
            if item is None:
                return None

            item.status = ScrapedItem.Status.PROCESSING
            item.last_attempt_at = now
            item.save(update_fields=["status", "last_attempt_at", "updated_at"])
            return item

    def _checkout_base_query(self) -> QuerySet[ScrapedItem]:
        """Return the lockable base queryset used for item checkout."""
        return ScrapedItem.objects.select_for_update(skip_locked=True)

    def _eligible_filters(
        self,
        *,
        now: datetime,
        force: bool,
    ) -> Q:
        """Build the checkout eligibility rules for scraped items."""
        retry_threshold = now - self.RETRY_COOLDOWN
        eligible_filters = Q(status=ScrapedItem.Status.NEW) | Q(
            status=ScrapedItem.Status.ERROR,
            error_count__lt=self.MAX_RETRIES,
            last_attempt_at__lt=retry_threshold,
        )

        if force:
            eligible_filters |= Q(status__in=self.FORCED_ELIGIBLE_STATUSES)

        return eligible_filters

    def _eligible_items(
        self,
        *,
        now: datetime,
        force: bool,
    ) -> QuerySet[ScrapedItem]:
        """Return eligible scraped items ordered by checkout priority."""
        return (
            self._checkout_base_query()
            .filter(
                self._eligible_filters(now=now, force=force),
                source_page__url__startswith="http",
            )
            .annotate(
                checkout_priority=Case(
                    When(status=ScrapedItem.Status.NEW, then=Value(0)),
                    When(status=ScrapedItem.Status.ERROR, then=Value(1)),
                    When(status=ScrapedItem.Status.REVIEW, then=Value(2)),
                    When(status=ScrapedItem.Status.LINKED, then=Value(3)),
                    default=Value(99),
                    output_field=IntegerField(),
                ),
            )
            .order_by("checkout_priority", "updated_at", "id")
        )

    def _selected_item(
        self,
        *,
        data: ScrapedItemCheckoutInput,
        now: datetime,
    ) -> ScrapedItem | None:
        """Return the single scraped item selected for checkout."""
        if data.target_item_id:
            return self._checkout_base_query().filter(id=data.target_item_id).first()
        return self._eligible_items(now=now, force=data.force).first()


class ScrapedItemErrorService:
    """Report agent-side processing failures for scraped items."""

    def execute(self, *, item_id: int, message: str, is_fatal: bool) -> bool:
        """Persist retry or review state for a scraped item error."""
        try:
            item = ScrapedItem.objects.get(id=item_id)
        except ScrapedItem.DoesNotExist:
            return False

        if is_fatal:
            item.status = ScrapedItem.Status.REVIEW
            item.last_error_log = f"FATAL: {message}"
        else:
            item.status = ScrapedItem.Status.ERROR
            item.error_count += 1
            item.last_error_log = message

            if item.error_count >= ScrapedItemCheckoutService.MAX_RETRIES:
                item.status = ScrapedItem.Status.REVIEW
                item.last_error_log += " (Max retries reached)"

        item.save()
        return True


class ScrapedItemDiscardService:
    """Discard scraped items that should not enter the catalog."""

    def execute(self, *, item_id: int, reason: str) -> bool:
        """Mark a scraped item as discarded with an explicit reason."""
        try:
            item = ScrapedItem.objects.get(id=item_id)
        except ScrapedItem.DoesNotExist:
            return False

        item.status = ScrapedItem.Status.DISCARDED
        item.last_error_log = f"Discarded by Agent: {reason}"
        item.save()
        return True


class ScrapedItemSourcePageService:
    """Maintain source-page associations for scraped items."""

    def ensure(
        self,
        *,
        item_id: int,
        url: str,
        store_slug: str,
    ) -> ScrapedItem | None:
        """Ensure a scraped item is linked to a source page by URL."""
        try:
            item = ScrapedItem.objects.get(id=item_id)
        except ScrapedItem.DoesNotExist:
            return None

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
        return item

    def update_item_data(
        self,
        *,
        item_id: int,
        name: str | None = None,
        source_page_url: str | None = None,
        store_slug: str | None = None,
    ) -> ScrapedItem | None:
        """Update mutable scraped item fields used by agent workflows."""
        try:
            item = ScrapedItem.objects.get(id=item_id)
        except ScrapedItem.DoesNotExist:
            return None

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
        return item


class ScrapedItemVariantService:
    """Create or update scraped item variants discovered by the agent."""

    def execute(self, data: ScrapedItemVariantInput) -> ScrapedItem | None:
        """Create or update a variant linked to the origin source page."""
        try:
            origin_item = ScrapedItem.objects.get(id=data.origin_item_id)
        except ScrapedItem.DoesNotExist:
            return None

        page, _ = ScrapedPage.objects.get_or_create(
            url=data.page_url,
            defaults={"store_slug": data.store_slug},
        )

        resolved_price = data.price if data.price is not None else origin_item.price
        resolved_stock_status = data.stock_status or origin_item.stock_status
        valid_stock_values = {choice[0] for choice in ScrapedItem.StockStatus.choices}
        if resolved_stock_status not in valid_stock_values:
            resolved_stock_status = ScrapedItem.StockStatus.AVAILABLE

        item, _ = ScrapedItem.objects.update_or_create(
            store_slug=data.store_slug,
            external_id=data.external_id,
            defaults={
                "name": data.name,
                "source_page": page,
                "price": resolved_price,
                "stock_status": resolved_stock_status,
                "status": ScrapedItem.Status.PROCESSING,
            },
        )
        return item


class ScraperService:
    """Service for handling scraped data."""

    @staticmethod
    @transaction.atomic
    def save_product(data: ScrapedItemIngestionInput) -> ScrapedItem | None:
        """Create or update a ScrapedItem."""
        page, _ = ScrapedPage.objects.get_or_create(
            url=data.url,
            defaults={"store_slug": data.store_slug},
        )
        if page.store_slug != data.store_slug:
            page.store_slug = data.store_slug
            page.save(update_fields=["store_slug"])

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

        if obj.product_store_id and obj.status == ScrapedItem.Status.LINKED:
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
        saved_item: ScrapedItem | None,
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
