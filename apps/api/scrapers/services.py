"""Services for persisting and syncing scraped catalog data."""

from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, NamedTuple

import extruct
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from offers.services import OfferObservationResult, OfferObservationService

from .dtos import AgentExtractionSubmitInput
from .models import ScrapedItem, ScrapedItemExtraction, ScrapedPage

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from .dtos import ScrapedItemIngestionInput

logger = logging.getLogger(__name__)


class RenderResult(NamedTuple):
    """Outcome of a headless render: HTTP status, response headers and HTML."""

    status: int | None
    headers: dict[str, str]
    html: str


SCHEMA_SYNTAXES = ("json-ld", "microdata", "opengraph", "rdfa", "microformat")


def extract_schema_metadata(html: str, url: str) -> dict:
    """Parse schema.org metadata from HTML with extruct.

    Returns the JSON-LD, microdata, opengraph, rdfa and microformat blocks the
    page author embedded. The full page is kept separately as ``raw_html`` (the
    source of truth), so this is just the queryable, semantic view. Stateless,
    so it lives at module level and can be reused without the service.
    """
    try:
        extracted = extruct.extract(
            html,
            base_url=url,
            syntaxes=list(SCHEMA_SYNTAXES),
            uniform=True,
        )
    except Exception:
        logger.exception("Failed to extract schema.org metadata for %s", url)
        return {}
    return extracted if isinstance(extracted, dict) else {}


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

    # Product pages are always captured with a headless browser: it is the only
    # method robust to every store (server-rendered, SPA, or anti-bot challenge).
    HTML_MISSING_STATUSES = (404, 410)

    RENDER_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    RENDER_NAV_TIMEOUT_MS = 60000
    RENDER_SETTLE_MS = 3000
    RENDER_SCROLL_STEPS = 10
    RENDER_SCROLL_PAUSE_MS = 300

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

    @staticmethod
    async def _render_page_async(url: str) -> RenderResult:
        """Render ``url`` in headless Chromium; capture status, headers and HTML."""
        # Imported lazily so the heavy browser dependency only loads where it is
        # used (the enrichment job), not in every process that imports this module.
        from playwright.async_api import async_playwright  # noqa: PLC0415

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=ScraperService.RENDER_USER_AGENT,
                )
                page = await context.new_page()
                response = await page.goto(
                    url,
                    timeout=ScraperService.RENDER_NAV_TIMEOUT_MS,
                    wait_until="load",
                )
                # Let client-side rendering and anti-bot challenges settle, then
                # scroll so sections that mount lazily (e.g. nutrition tables
                # below the fold) are present in the captured HTML.
                await page.wait_for_timeout(ScraperService.RENDER_SETTLE_MS)
                for _ in range(ScraperService.RENDER_SCROLL_STEPS):
                    await page.mouse.wheel(0, 2000)
                    await page.wait_for_timeout(ScraperService.RENDER_SCROLL_PAUSE_MS)
                await page.wait_for_timeout(1000)
                if response is None:
                    return RenderResult(None, {}, await page.content())
                return RenderResult(
                    response.status,
                    await response.all_headers(),
                    await page.content(),
                )
            finally:
                await browser.close()

    @staticmethod
    def _render_page(url: str) -> RenderResult | None:
        """Render a page in a headless browser; ``None`` if rendering fails."""
        try:
            return asyncio.run(ScraperService._render_page_async(url))
        except Exception:
            logger.exception("Failed to render %s in a headless browser", url)
            return None

    @staticmethod
    def enrich_pages(
        *,
        store_slug: str | None = None,
        limit: int | None = None,
    ) -> dict[str, int]:
        """Heavy, on-demand pass: refresh the captured HTML for scraped pages.

        Each page is rendered in a headless browser. Rendering is the only
        capture method robust to every store (server-rendered, SPA, or anti-bot
        challenge), so it is always used. The full HTML, the parsed schema.org
        metadata and the HTTP response metadata are all stored. Runs
        independently of the light catalog crawl.
        """
        if limit is not None and limit < 1:
            msg = "limit must be a positive integer."
            raise ValueError(msg)

        pages = ScrapedPage.objects.all()
        if store_slug:
            pages = pages.filter(store_slug=store_slug)
        if limit:
            pages = pages[:limit]

        stats = {"checked": 0, "updated": 0, "failed": 0}
        for page in pages.iterator():
            stats["checked"] += 1
            stats[ScraperService._enrich_page(page)] += 1
        logger.info("Enrichment finished (store=%s): %s", store_slug or "all", stats)
        return stats

    @staticmethod
    def _enrich_page(page: ScrapedPage) -> str:
        """Render and store one page's HTML, metadata and response info."""
        result = ScraperService._render_page(page.url)
        if result is None:
            # Transient failure: keep whatever was captured before.
            return "failed"

        if result.status in ScraperService.HTML_MISSING_STATUSES:
            # Page is gone: drop stale captures instead of keeping them.
            page.raw_html = ""
            page.html_structured_data = {}
        else:
            page.raw_html = result.html
            page.html_structured_data = extract_schema_metadata(result.html, page.url)
        page.response_meta = {"status": result.status, "headers": result.headers}

        page.save(
            update_fields=[
                "raw_html",
                "html_structured_data",
                "response_meta",
                "updated_at",
            ],
        )
        return "updated"
