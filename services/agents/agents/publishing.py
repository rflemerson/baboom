"""Helpers for the backend publishing half of the pipeline."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .acquisition import ensure_item_source_page

if TYPE_CHECKING:
    from dagster import AssetExecutionContext


NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class PublishOriginContext:
    """Normalized source context used while publishing analyzed items."""

    item_id: int
    page_id: int | None
    page_url: str
    store_slug: str
    item: dict


@dataclass(frozen=True, slots=True)
class PublishItemResult:
    """Result of publishing one analyzed item plus bookkeeping metadata."""

    result: dict
    variant_created: bool


class PublishApi(Protocol):
    """Backend API surface needed by the publish helpers."""

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


def slugify(value: str) -> str:
    """Normalize free text into a stable slug."""
    normalized = NON_ALNUM_PATTERN.sub("-", value.lower()).strip("-")
    return normalized or "item"


def to_graphql_stock_status(status: str | None) -> str:
    """Map scraper stock status values into the GraphQL enum."""
    stock_map = {
        "A": "AVAILABLE",
        "L": "LAST_UNITS",
        "O": "OUT_OF_STOCK",
        "AVAILABLE": "AVAILABLE",
        "LAST_UNITS": "LAST_UNITS",
        "OUT_OF_STOCK": "OUT_OF_STOCK",
    }
    return stock_map.get((status or "").upper(), "AVAILABLE")


def parse_number(value: object) -> float | None:
    """Parse numbers from LLM/API values like '30g', '1,5', or 'N/A'."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    parsed = match.group(0) if match else ""
    if not parsed:
        return None
    try:
        return float(parsed)
    except (TypeError, ValueError):
        return None


def parse_float(value: object, default: float = 0.0) -> float:
    """Parse one numeric value as float with a default fallback."""
    parsed = parse_number(value)
    return parsed if parsed is not None else default


def parse_int(value: object, default: int = 0) -> int:
    """Parse one numeric value as int with a default fallback."""
    parsed = parse_number(value)
    if parsed is None:
        return default
    return int(parsed)


def build_nutrition_payload(analysis_data: dict) -> list[dict]:
    """Map structured analysis nutrition facts into GraphQL payload shape."""
    nutrition = analysis_data.get("nutrition_facts")
    if not nutrition:
        return []

    micronutrients = [
        {
            "name": micronutrient.get("name"),
            "value": parse_float(micronutrient.get("value")),
            "unit": micronutrient.get("unit") or "mg",
        }
        for micronutrient in (nutrition.get("micronutrients") or [])
        if micronutrient.get("name")
    ]

    return [
        {
            "flavorNames": analysis_data.get("flavor_names") or [],
            "nutritionFacts": {
                "description": analysis_data.get("variant_name") or "AI Analysis",
                "servingSizeGrams": parse_float(nutrition.get("serving_size_grams")),
                "energyKcal": parse_int(nutrition.get("energy_kcal")),
                "proteins": parse_float(nutrition.get("proteins")),
                "carbohydrates": parse_float(nutrition.get("carbohydrates")),
                "totalSugars": parse_float(nutrition.get("total_sugars")),
                "addedSugars": parse_float(nutrition.get("added_sugars")),
                "totalFats": parse_float(nutrition.get("total_fats")),
                "saturatedFats": parse_float(nutrition.get("saturated_fats")),
                "transFats": parse_float(nutrition.get("trans_fats")),
                "dietaryFiber": parse_float(nutrition.get("dietary_fiber")),
                "sodium": parse_float(nutrition.get("sodium")),
                "micronutrients": micronutrients,
            },
        },
    ]


def build_publish_origin_context(
    api: PublishApi,
    *,
    item_id: int,
    url: str,
    store_slug: str,
) -> PublishOriginContext:
    """Ensure the origin item has a source page and return normalized context."""
    origin_item, ensured_origin = ensure_item_source_page(
        api,
        item_id=item_id,
        fallback_url=url,
        fallback_store_slug=store_slug,
    )
    origin_store_slug = origin_item.get("storeSlug") or store_slug
    page_url = (
        ensured_origin.get("sourcePageUrl")
        or origin_item.get("sourcePageUrl")
        or origin_item.get("productLink")
        or url
    )
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


def resolve_analysis_items(product_analysis: dict, origin_item: dict) -> list[dict]:
    """Return analyzed items or a single fallback item when analysis is empty."""
    items = product_analysis.get("items") or []
    if items:
        return items
    return [{"name": origin_item.get("name") or "Unknown Product"}]


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
    origin: PublishOriginContext,
) -> PublishItemResult:
    """Publish one analyzed item and return result plus bookkeeping."""
    scraped_item, variant_created = resolve_scraped_item_for_analysis(
        api,
        idx,
        analysis_data,
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
        external_id=build_variant_external_id(origin, idx, analysis_data),
        name=analysis_data.get("name") or origin.item.get("name") or "product",
        page_url=origin.page_url,
        store_slug=origin.store_slug,
        price=(
            parse_float(origin.item.get("price"), default=0.0)
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
) -> str:
    """Build deterministic external id for one derived scraped variant."""
    base_name = analysis_data.get("name") or origin.item.get("name") or "product"
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
    origin_item: dict,
    scraped_item: dict,
    page_url: str,
    origin_store_slug: str,
) -> dict:
    """Map one analyzed item into ProductInput payload."""
    product_name = (
        analysis_data.get("name") or origin_item.get("name") or "Unknown Product"
    )
    return {
        "name": product_name,
        "brandName": analysis_data.get("brand_name") or "Unknown Brand",
        "weight": parse_int(analysis_data.get("weight_grams")),
        "ean": analysis_data.get("ean"),
        "description": analysis_data.get("description"),
        "packaging": analysis_data.get("packaging") or "CONTAINER",
        "originScrapedItemId": int(scraped_item["id"]),
        "stores": [
            build_product_store_payload(
                origin_item=origin_item,
                scraped_item=scraped_item,
                page_url=page_url,
                origin_store_slug=origin_store_slug,
            ),
        ],
        "nutrition": build_nutrition_payload(analysis_data),
        "categoryPath": analysis_data.get("category_hierarchy") or [],
        "tagPaths": build_tag_paths(analysis_data.get("tags_hierarchy") or []),
        "tags": [],
        "isCombo": bool(analysis_data.get("is_combo")),
        "components": build_component_payloads(analysis_data.get("components") or []),
        "isPublished": False,
    }


def build_product_store_payload(
    *,
    origin_item: dict,
    scraped_item: dict,
    page_url: str,
    origin_store_slug: str,
) -> dict:
    """Build the single-store payload for one published product."""
    origin_price = parse_float(origin_item.get("price") or 0.0)
    return {
        "storeName": origin_store_slug,
        "productLink": page_url,
        "price": origin_price,
        "externalId": scraped_item.get("externalId"),
        "stockStatus": to_graphql_stock_status(origin_item.get("stockStatus")),
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
            "ean": component.get("ean"),
            "externalId": component.get("external_id"),
            "quantity": parse_int(component.get("quantity"), default=1),
        }
        for component in components
        if component.get("name")
    ]
