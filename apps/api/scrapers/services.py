"""Services for persisting and syncing scraped catalog data."""

from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, NamedTuple

import extruct
from bs4 import BeautifulSoup
from django.db import transaction

from offers.services import OfferObservationResult, OfferObservationService

from .models import ScrapedItem, ScrapedPage

if TYPE_CHECKING:
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


def _visible_text(soup: BeautifulSoup) -> str:
    """Return the visible text with one node per line.

    The line breaks are the point: a nutrition table laid out in divs is only
    readable if each label and value keeps its own line. Collapsing the page
    into one space-separated run loses the row structure that makes those
    values parseable at all.
    """
    for element in soup.find_all(["script", "style", "noscript", "template"]):
        element.decompose()
    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)


def extract_page_evidence(html: str, url: str) -> dict:
    """Extract semantic metadata, tables, and visible text from a page.

    The three live under their own keys because they are different kinds of
    evidence: what the page author declared, what it tabulated, and what it
    simply shows. Stores keep nutrition in all three places.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        rows = []
        for row in table.find_all("tr"):
            cells = [
                cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])
            ]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)

    return {
        "schema": extract_schema_metadata(html, url),
        "tables": tables,
        "text": _visible_text(soup),
    }


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
        """Record the merchant offer and its captured source-page link.

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
        page_ids: list[int] | None = None,
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
        if page_ids is not None:
            pages = pages.filter(pk__in=page_ids)
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
            page.html_structured_data = extract_page_evidence(result.html, page.url)
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
