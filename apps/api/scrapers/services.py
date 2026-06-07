"""Services for persisting and syncing scraped catalog data."""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal, InvalidOperation
from secrets import SystemRandom
from typing import TYPE_CHECKING

import extruct
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from offers.services import OfferObservationResult, OfferObservationService

from .dtos import AgentExtractionSubmitInput
from .models import ScrapedItem, ScrapedItemExtraction, ScrapedPage
from .spiders.http_client import HttpClient, HttpRequestOptions, parse_retry_after

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from .dtos import ScrapedItemIngestionInput

logger = logging.getLogger(__name__)
JITTER_RANDOM = SystemRandom()


class ScrapedItemCheckoutService:
    """Reserve one scraped item for agent processing."""

    def execute(self) -> ScrapedItem | None:
        """Select and lock the next scraped item for checkout."""
        with transaction.atomic():
            item = self._selected_item()
            if item is None:
                return None

            item.status = ScrapedItem.Status.PROCESSING
            item.last_attempt_at = timezone.now()
            item.save(update_fields=["status", "last_attempt_at", "updated_at"])
            return item

    def _checkout_base_query(self) -> QuerySet[ScrapedItem]:
        """Return the lockable base queryset used for item checkout."""
        return ScrapedItem.objects.select_for_update(skip_locked=True)

    def _eligible_items(self) -> QuerySet[ScrapedItem]:
        """Return eligible scraped items ordered by checkout priority."""
        return (
            self._checkout_base_query()
            .filter(
                status=ScrapedItem.Status.QUEUED,
                source_page__url__startswith="http",
            )
            .order_by("updated_at", "id")
        )

    def _selected_item(self) -> ScrapedItem | None:
        """Return the single scraped item selected for checkout."""
        return self._eligible_items().first()


class ScrapedItemErrorService:
    """Report agent-side processing failures for scraped items."""

    def execute(self, *, item_id: int, message: str, is_fatal: bool) -> bool:
        """Persist retry or review state for a processing scraped item."""
        item = ScrapedItem.objects.filter(id=item_id).first()
        if item is None or item.status != ScrapedItem.Status.PROCESSING:
            return False

        item.last_attempt_at = timezone.now()
        if is_fatal:
            item.status = ScrapedItem.Status.REVIEW
            item.last_error_log = f"FATAL: {message}"
        else:
            item.error_count += 1
            item.last_error_log = message
            item.status = ScrapedItem.Status.ERROR

        item.save(
            update_fields=[
                "status",
                "error_count",
                "last_error_log",
                "last_attempt_at",
                "updated_at",
            ],
        )
        return True


class ScrapedItemExtractionSubmitService:
    """Stage one agent extraction for review without creating catalog products."""

    @transaction.atomic
    def execute(self, data: AgentExtractionSubmitInput) -> ScrapedItemExtraction:
        """Persist the agent output and move the origin item to review."""
        item = self._get_item(data.origin_scraped_item_id)
        if item.status != ScrapedItem.Status.PROCESSING:
            raise DjangoValidationError(
                {"originScrapedItemId": ["Scraped item is not processing."]},
            )
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
            ScrapedItem.objects.select_related("source_page", "offer")
            .filter(id=item_id)
            .first()
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
                defaults={"store_slug": data.store_slug or item.offer.store_slug},
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
    HTML_EXTRACTION_THROTTLE_SECONDS = (0.5, 1.5)
    # Jittered backoff windows applied after each 429 before retrying.
    HTML_EXTRACTION_RETRY_BACKOFFS = ((0.5, 1.5), (5.0, 10.0), (15.0, 25.0))
    HTML_EXTRACTION_RATE_LIMITED_STATUS = 429
    HTML_EXTRACTION_MISSING_STATUSES = (404, 410)
    HTML_EXTRACTION_OK_STATUS = 200
    HTML_NOT_MODIFIED_STATUS = 304

    # Reused across the many per-product fetches of a weekly run so connections
    # to the same store are kept alive (faster + steadier fingerprint).
    _html_client: HttpClient | None = None

    @classmethod
    def _get_html_client(cls) -> HttpClient:
        """Return the shared keep-alive HTTP client for HTML enrichment."""
        if cls._html_client is None:
            cls._html_client = HttpClient(timeout=cls.HTML_EXTRACTION_TIMEOUT_SECONDS)
        return cls._html_client

    @staticmethod
    @transaction.atomic
    def save_product(
        data: ScrapedItemIngestionInput,
        *,
        api_context: str | dict | None = None,
    ) -> ScrapedItem:
        """Record the merchant offer and ensure its pipeline record exists.

        This is the light path: the offer (identity, price, stock) is upserted
        on every run and the page's ``api_context`` keeps the latest raw catalog
        payload. The heavy product-page HTML lives entirely in
        :meth:`enrich_pages`, run on demand.
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
        except (InvalidOperation, ValueError):
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

    @staticmethod
    def _fetch_html_for_extraction(
        url: str,
        headers: dict[str, str] | None,
    ) -> object | None:
        """Fetch a product page using browser TLS impersonation.

        Uses ``HttpClient`` (curl_cffi) plus jittered throttling and 429-aware
        backoff so stores that rate-limit plain ``requests`` traffic keep
        serving the product HTML. Returns the response, or ``None`` on failure.
        """
        client = ScraperService._get_html_client()
        request_headers = headers or {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        backoffs = ScraperService.HTML_EXTRACTION_RETRY_BACKOFFS
        response = None
        for attempt, backoff in enumerate(backoffs):
            time.sleep(
                JITTER_RANDOM.uniform(*ScraperService.HTML_EXTRACTION_THROTTLE_SECONDS),
            )
            response = client.get(
                url,
                options=HttpRequestOptions(
                    headers=request_headers,
                    try_all_impersonations=attempt > 0,
                ),
            )
            if response is None:
                logger.warning("No response fetching HTML for extraction: %s", url)
                return None
            if (
                response.status_code
                != ScraperService.HTML_EXTRACTION_RATE_LIMITED_STATUS
            ):
                return response
            # Honor the server's own pacing when it tells us; else jittered backoff.
            wait = parse_retry_after(response) or JITTER_RANDOM.uniform(*backoff)
            logger.warning(
                "Rate limited (429) fetching %s; waiting %.1fs (retry %s/%s)",
                url,
                wait,
                attempt + 1,
                len(backoffs),
            )
            time.sleep(wait)
        return response

    @staticmethod
    def _parse_structured_html(response: object, url: str) -> dict:
        """Run extruct over a fetched HTML response body."""
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
    def _conditional_headers(page: ScrapedPage) -> dict[str, str]:
        """Build HTML headers with ETag/Last-Modified validators for a 304 GET."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if page.http_etag:
            headers["If-None-Match"] = page.http_etag
        if page.http_last_modified:
            headers["If-Modified-Since"] = page.http_last_modified
        return headers

    @staticmethod
    def _apply_html_response(page: ScrapedPage, response: object | None) -> str:
        """Update ``page`` HTML fields from a response and return an outcome.

        A ``304 Not Modified`` keeps the stored data untouched (the whole point of
        the conditional GET); a missing page clears it; a good page re-parses and
        records the fresh ETag/Last-Modified validators.
        """
        if response is None:
            return "failed"
        status = response.status_code
        if status == ScraperService.HTML_NOT_MODIFIED_STATUS:
            logger.info("HTML unchanged (304) for %s; keeping stored data", page.url)
            return "unchanged"
        if status in ScraperService.HTML_EXTRACTION_MISSING_STATUSES:
            page.html_structured_data = {}
            page.http_etag = ""
            page.http_last_modified = ""
            return "updated"
        if status != ScraperService.HTML_EXTRACTION_OK_STATUS:
            logger.error("Failed to enrich HTML (%s) for %s", status, page.url)
            return "failed"

        page.html_structured_data = ScraperService._parse_structured_html(
            response,
            page.url,
        )
        response_headers = getattr(response, "headers", None) or {}
        page.http_etag = str(response_headers.get("ETag", "") or "")[:250]
        page.http_last_modified = str(
            response_headers.get("Last-Modified", "") or "",
        )[:100]
        return "updated"

    @staticmethod
    def enrich_pages(
        *,
        store_slug: str | None = None,
        limit: int | None = None,
    ) -> dict[str, int]:
        """Heavy, on-demand pass: refresh HTML structured data for scraped pages.

        Each page is fetched with a conditional GET (its stored ETag /
        Last-Modified). Pages the store reports as unchanged (``304``) are skipped
        without re-parsing, so this only does real work where the product page
        actually moved. Runs independently of the light catalog crawl.
        """
        if limit is not None and limit < 1:
            msg = "limit must be a positive integer."
            raise ValueError(msg)

        pages = ScrapedPage.objects.all()
        if store_slug:
            pages = pages.filter(store_slug=store_slug)
        if limit:
            pages = pages[:limit]

        stats = {"checked": 0, "updated": 0, "unchanged": 0, "failed": 0}
        for page in pages.iterator():
            stats["checked"] += 1
            stats[ScraperService._enrich_page(page)] += 1
        logger.info("Enrichment finished (store=%s): %s", store_slug or "all", stats)
        return stats

    @staticmethod
    def _enrich_page(page: ScrapedPage) -> str:
        """Conditionally refresh one page's HTML data; return the outcome key."""
        response = ScraperService._fetch_html_for_extraction(
            page.url,
            ScraperService._conditional_headers(page),
        )
        outcome = ScraperService._apply_html_response(page, response)
        if outcome != "updated":
            return outcome
        page.save(
            update_fields=["html_structured_data", "http_etag", "http_last_modified"],
        )
        return outcome
