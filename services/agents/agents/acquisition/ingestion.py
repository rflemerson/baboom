"""Pure helpers backing the Dagster ingestion asset."""

from __future__ import annotations

from typing import Protocol

from ..contracts.acquisition import SourcePageContext


class ItemInput(Protocol):
    """Minimal item config contract needed by acquisition helpers."""

    item_id: int
    url: str
    store_slug: str


class IngestionApi(Protocol):
    """Backend API surface needed by the ingestion asset helpers."""

    def get_scraped_item(self, item_id: int) -> dict | None:
        """Return one scraped item snapshot."""

    def ensure_source_page(
        self,
        item_id: int,
        url: str,
        store_slug: str,
    ) -> dict | None:
        """Ensure the scraped item is linked to a source page."""


def get_item_or_raise(api: IngestionApi, item_id: int) -> dict:
    """Load the queued item or fail fast."""
    item = api.get_scraped_item(item_id)
    if not item:
        message = f"Scraped item {item_id} not found"
        raise RuntimeError(message)
    return item


def resolve_source_page_context(
    api: IngestionApi,
    config: ItemInput,
    item: dict,
) -> SourcePageContext:
    """Ensure source page exists and return normalized page context."""
    page_url = item.get("sourcePageUrl") or item.get("productLink") or config.url
    store_slug = item.get("storeSlug") or config.store_slug
    ensured_item = api.ensure_source_page(config.item_id, page_url, store_slug)
    if not ensured_item:
        message = f"Failed to ensure source page for item {config.item_id}"
        raise RuntimeError(message)

    page_id = ensured_item.get("sourcePageId")
    ensured_page_url = ensured_item.get("sourcePageUrl") or page_url
    if not page_id:
        message = f"Missing sourcePageId for item {config.item_id}"
        raise RuntimeError(message)

    return SourcePageContext(
        item_id=int(ensured_item["id"]),
        page_id=int(page_id),
        page_url=ensured_page_url,
        store_slug=ensured_item.get("storeSlug") or store_slug,
        source_page_raw_content=item.get("sourcePageRawContent") or "",
        source_page_content_type=item.get("sourcePageContentType") or "",
    )


def build_download_result(storage_path: str, page: SourcePageContext) -> dict:
    """Build the asset output payload from normalized page context."""
    return {
        "storage_path": storage_path,
        "url": page.page_url,
        "page_id": page.page_id,
        "origin_item_id": page.item_id,
        "store_slug": page.store_slug,
        "source_page_raw_content": page.source_page_raw_content,
        "source_page_content_type": page.source_page_content_type,
    }
