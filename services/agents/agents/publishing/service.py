"""Publishing helpers that map analyzed items into backend API calls."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Protocol

from ..contracts.publishing import PublishItemResult, PublishOriginContext
from .payload_utils import (
    build_nutrition_payload,
    slugify,
    to_float,
    to_graphql_stock_status,
    to_int,
)

if TYPE_CHECKING:
    from dagster import AssetExecutionContext

    from ..schemas.product import RawScrapedData


class PublishApi(Protocol):
    """Backend API surface needed by the publish asset helpers."""

    def get_scraped_item(self, item_id: int) -> dict | None:
        """Return one scraped item snapshot."""

    def ensure_source_page(
        self,
        item_id: int,
        url: str,
        store_slug: str,
    ) -> dict | None:
        """Ensure the scraped item is linked to a source page."""

    def update_scraped_item_data(
        self,
        item_id: int,
        name: str | None = None,
        source_page_url: str | None = None,
        store_slug: str | None = None,
    ) -> dict | None:
        """Update the mutable fields of one scraped item."""

    def upsert_scraped_item_variant(
        self,
        origin_item_id: int,
        external_id: str,
        name: str,
        page_url: str,
        store_slug: str,
        price: float | None = None,
        stock_status: str | None = None,
    ) -> dict | None:
        """Create or update a derived scraped-item variant."""

    def create_product(self, product_input: dict) -> dict | None:
        """Create one downstream product record."""


def build_publish_origin_context(
    api: PublishApi,
    *,
    item_id: int,
    url: str,
    store_slug: str,
) -> PublishOriginContext:
    """Ensure the origin item has a source page and return normalized context."""
    origin_item = get_origin_item(api, item_id)
    origin_page_url = (
        origin_item.get("sourcePageUrl") or origin_item.get("productLink") or url
    )
    origin_store_slug = origin_item.get("storeSlug") or store_slug
    ensured_origin = api.ensure_source_page(item_id, origin_page_url, origin_store_slug)
    if not ensured_origin:
        message = f"Failed to ensure source page for item {item_id}"
        raise RuntimeError(message)
    page_url = ensured_origin.get("sourcePageUrl") or origin_page_url
    return PublishOriginContext(
        item_id=int(ensured_origin["id"]),
        page_id=(
            int(ensured_origin["sourcePageId"])
            if ensured_origin.get("sourcePageId") is not None
            else None
        ),
        page_url=page_url,
        store_slug=origin_store_slug,
        item=origin_item,
    )


def get_origin_item(api: PublishApi, item_id: int) -> dict:
    """Fetch the origin scraped item or fail fast."""
    origin_item = api.get_scraped_item(item_id)
    if not origin_item:
        message = f"Scraped item {item_id} not found"
        raise RuntimeError(message)
    return origin_item


def resolve_analysis_items(
    product_analysis: dict,
    scraped_metadata: RawScrapedData,
    origin_item: dict,
) -> list[dict]:
    """Return analyzed items or a single fallback item when analysis is empty."""
    items = product_analysis.get("items") or []
    if items:
        return items
    return [
        {
            "name": scraped_metadata.name
            or origin_item.get("name")
            or "Unknown Product",
        },
    ]


def build_upload_metadata(
    *,
    results: list[dict],
    created_count: int,
    page_id: int | None,
    started: float,
) -> dict:
    """Build output metadata for the publish asset."""
    return {
        "items_uploaded": len(results),
        "additional_scraped_items_created": created_count,
        "page_id": page_id,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def publish_analysis_item(
    *,
    context: AssetExecutionContext,
    api: PublishApi,
    idx: int,
    analysis_data: dict,
    scraped_metadata: RawScrapedData,
    origin: PublishOriginContext,
) -> PublishItemResult:
    """Publish one analyzed item and return result plus bookkeeping."""
    scraped_item, variant_created = resolve_scraped_item_for_analysis(
        api,
        idx,
        analysis_data,
        scraped_metadata,
        origin,
    )

    if should_skip_linked_item(scraped_item):
        context.log.info(
            "Skipping already linked item %s (%s)",
            scraped_item["id"],
            scraped_item.get("externalId"),
        )
        return PublishItemResult(
            result=build_skipped_linked_result(scraped_item),
            variant_created=variant_created,
        )

    if str(scraped_item.get("status") or "").lower() == "linked":
        context.log.warning(
            "Item %s marked LINKED without product_store; reprocessing.",
            scraped_item["id"],
        )

    payload = build_product_payload(
        analysis_data,
        scraped_metadata,
        origin.item,
        scraped_item,
        origin.page_url,
        origin.store_slug,
    )
    context.log.info(
        "Uploading product %s with origin item %s",
        idx + 1,
        scraped_item["id"],
    )
    return PublishItemResult(
        result=api.create_product(payload) or {},
        variant_created=variant_created,
    )


def resolve_scraped_item_for_analysis(
    api: PublishApi,
    idx: int,
    analysis_data: dict,
    scraped_metadata: RawScrapedData,
    origin: PublishOriginContext,
) -> tuple[dict, bool]:
    """Return the scraped item that should back one analyzed product."""
    if idx == 0:
        scraped_item = api.update_scraped_item_data(
            item_id=origin.item_id,
            name=analysis_data.get("name"),
            source_page_url=origin.page_url,
            store_slug=origin.store_slug,
        )
        return scraped_item or origin.item, False

    scraped_item = api.upsert_scraped_item_variant(
        origin_item_id=origin.item_id,
        external_id=build_variant_external_id(
            origin,
            idx,
            analysis_data,
            scraped_metadata,
        ),
        name=analysis_data.get("name") or scraped_metadata.name or "product",
        page_url=origin.page_url,
        store_slug=origin.store_slug,
        price=(
            to_float(origin.item.get("price"), default=0.0)
            if origin.item.get("price") is not None
            else None
        ),
        stock_status=origin.item.get("stockStatus"),
    )
    if not scraped_item:
        message = "Failed to upsert scraped item variant"
        raise RuntimeError(message)
    return scraped_item, True


def build_variant_external_id(
    origin: PublishOriginContext,
    idx: int,
    analysis_data: dict,
    scraped_metadata: RawScrapedData,
) -> str:
    """Build deterministic external id for one derived scraped variant."""
    base_name = analysis_data.get("name") or scraped_metadata.name or "product"
    variant_name = analysis_data.get("variant_name") or f"v{idx + 1}"
    origin_external_id = str(origin.item.get("externalId") or "")
    external_id = (
        f"{origin_external_id}::v{idx + 1}-{slugify(base_name)}-{slugify(variant_name)}"
    )
    return external_id[:100]


def build_skipped_linked_result(scraped_item: dict) -> dict:
    """Build the synthetic result for an already linked scraped item."""
    return {
        "product": {"id": scraped_item.get("linkedProductId")},
        "errors": [],
        "skipped": True,
    }


def should_skip_linked_item(scraped_item: dict) -> bool:
    """Return whether one linked scraped item can be safely skipped."""
    status_value = str(scraped_item.get("status") or "").lower()
    product_store_id = scraped_item.get("productStoreId")
    return status_value == "linked" and bool(product_store_id)


def build_product_payload(
    analysis_data: dict,
    scraped_metadata: RawScrapedData,
    origin_item: dict,
    scraped_item: dict,
    page_url: str,
    origin_store_slug: str,
) -> dict:
    """Map one analyzed item into ProductInput payload."""
    tags_hierarchy = analysis_data.get("tags_hierarchy") or []
    return {
        "name": analysis_data.get("name") or scraped_metadata.name or "Unknown Product",
        "brandName": scraped_metadata.brand_name or "Unknown Brand",
        "weight": to_int(analysis_data.get("weight_grams")),
        "ean": scraped_metadata.ean,
        "description": scraped_metadata.description,
        "packaging": analysis_data.get("packaging") or "CONTAINER",
        "originScrapedItemId": int(scraped_item["id"]),
        "stores": [
            build_product_store_payload(
                scraped_metadata=scraped_metadata,
                origin_item=origin_item,
                scraped_item=scraped_item,
                page_url=page_url,
                origin_store_slug=origin_store_slug,
            ),
        ],
        "nutrition": build_nutrition_payload(analysis_data),
        "categoryPath": analysis_data.get("category_hierarchy") or [],
        "tagPaths": build_tag_paths(tags_hierarchy),
        "tags": [],
        "isCombo": bool(analysis_data.get("is_combo")),
        "components": build_component_payloads(analysis_data.get("components") or []),
        "nutrientClaims": analysis_data.get("nutrient_claims") or [],
        "isPublished": False,
    }


def build_product_store_payload(
    *,
    scraped_metadata: RawScrapedData,
    origin_item: dict,
    scraped_item: dict,
    page_url: str,
    origin_store_slug: str,
) -> dict:
    """Build the single-store payload for one published product."""
    return {
        "storeName": origin_store_slug,
        "productLink": page_url,
        "price": to_float(scraped_metadata.price or origin_item.get("price") or 0.0),
        "externalId": scraped_item.get("externalId"),
        "stockStatus": to_graphql_stock_status(
            scraped_metadata.stock_status or origin_item.get("stockStatus"),
        ),
        "affiliateLink": "",
    }


def build_tag_paths(tags_hierarchy: list[str]) -> list[dict]:
    """Build tag-path payload entries from non-empty hierarchy values."""
    return [{"path": path} for path in tags_hierarchy if path]


def build_component_payloads(components: list[dict]) -> list[dict]:
    """Build component payload entries while filtering unnamed components."""
    return [
        {
            "name": component.get("name"),
            "quantity": to_int(component.get("quantity"), default=1),
            "weightHint": component.get("weight_hint"),
            "packagingHint": component.get("packaging_hint"),
        }
        for component in components
        if component.get("name")
    ]
