"""Services for persisting and syncing scraped catalog data."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import extruct
import requests
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Case, IntegerField, Q, QuerySet, Value, When
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from core.models import ProductPriceHistory, ProductStore

from .dtos import AgentExtractionSubmitInput
from .models import ScrapedItem, ScrapedItemExtraction, ScrapedPage

if TYPE_CHECKING:
    from .dtos import ScrapedItemIngestionInput
    from .graphql.inputs import ScrapedItemCheckoutInput

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


class ScrapedItemLinkService:
    """Link a scraped item to an explicitly selected product store listing."""

    def execute(
        self,
        *,
        scraped_item_id: int,
        product_store_id: int,
    ) -> ScrapedItem | None:
        """Link and sync a scraped item using an explicit target listing."""
        product_store = ProductStore.objects.filter(id=product_store_id).first()
        if product_store is None:
            return None

        item = ScrapedItem.objects.filter(id=scraped_item_id).first()
        if item is None:
            return None

        item.product_store = product_store
        item.status = ScrapedItem.Status.LINKED
        item.save(update_fields=["product_store", "status"])
        ScraperService.sync_price_to_core(item)
        return item


class ScrapedItemExtractionSubmitService:
    """Stage one agent extraction for review without creating catalog products."""

    @transaction.atomic
    def execute(self, data: AgentExtractionSubmitInput) -> ScrapedItemExtraction:
        """Persist the agent output and move the origin item to review."""
        item = self._get_item(data.origin_scraped_item_id)
        source_page = self._resolve_source_page(item=item, data=data)
        extraction, _ = ScrapedItemExtraction.objects.update_or_create(
            scraped_item=item,
            defaults={
                "source_page": source_page,
                "image_report": data.image_report,
                "extracted_product": data.product_payload(),
            },
        )

        item.source_page = source_page
        item.status = ScrapedItem.Status.REVIEW
        item.error_count = 0
        item.last_error_log = ""
        item.last_attempt_at = timezone.now()
        item.save(
            update_fields=[
                "source_page",
                "status",
                "error_count",
                "last_error_log",
                "last_attempt_at",
                "updated_at",
            ],
        )
        return extraction

    def _get_item(self, item_id: int) -> ScrapedItem:
        """Return the origin item or raise a GraphQL-friendly validation error."""
        item = (
            ScrapedItem.objects.select_related("source_page").filter(id=item_id).first()
        )
        if item is None:
            raise DjangoValidationError(
                {"originScrapedItemId": ["Scraped item does not exist."]},
            )
        return item

    def _resolve_source_page(
        self,
        *,
        item: ScrapedItem,
        data: AgentExtractionSubmitInput,
    ) -> ScrapedPage:
        """Resolve the source page used by this extraction."""
        if data.source_page_id:
            page = ScrapedPage.objects.filter(id=data.source_page_id).first()
            if page is None:
                raise DjangoValidationError(
                    {"sourcePageId": ["Source page does not exist."]},
                )
            return page

        if item.source_page_id and item.source_page:
            return item.source_page

        if data.source_page_url:
            page, _ = ScrapedPage.objects.get_or_create(
                url=data.source_page_url,
                defaults={"store_slug": data.store_slug or item.store_slug},
            )
            return page

        raise DjangoValidationError(
            {"sourcePageId": ["A source page id or URL is required."]},
        )


def build_agent_extraction_submit_input(payload: object) -> AgentExtractionSubmitInput:
    """Validate a raw GraphQL JSON payload into the staging DTO."""
    try:
        return AgentExtractionSubmitInput.model_validate(payload)
    except PydanticValidationError as exc:
        errors = {str(error["loc"]): [error["msg"]] for error in exc.errors()}
        raise DjangoValidationError(errors) from exc


class ScraperService:
    """Service for handling scraped data."""

    HTML_EXTRACTION_TIMEOUT_SECONDS = 20

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

    @staticmethod
    def extract_html_structured_data(
        *,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict:
        """Fetch one product page and extract structured metadata from the HTML."""
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=ScraperService.HTML_EXTRACTION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to fetch HTML for structured extraction: %s", url)
            return {}

        try:
            extracted = extruct.extract(
                response.text,
                base_url=url,
                syntaxes=["json-ld", "microdata", "opengraph", "rdfa", "microformat"],
                uniform=True,
            )
        except Exception:
            logger.exception("Failed to extract structured HTML data for %s", url)
            return {}

        return extracted if isinstance(extracted, dict) else {}

    @staticmethod
    def persist_page_context(
        saved_item: ScrapedItem | None,
        api_context_payload: str | dict,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Persist API context and HTML-structured data into source page."""
        if not saved_item or not saved_item.source_page_id:
            return
        page = saved_item.source_page
        if page is None:
            return
        page.api_context = ScraperService._normalize_api_context_payload(
            api_context_payload,
        )
        page.html_structured_data = ScraperService.extract_html_structured_data(
            url=page.url,
            headers=headers,
        )
        page.save(update_fields=["api_context", "html_structured_data"])
