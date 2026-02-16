"""Dagster asset: publish analyzed items into the downstream API."""

import time

from dagster import AssetExecutionContext, asset

from ...schemas.product import RawScrapedData
from ..resources import AgentClientResource
from .shared import (
    ItemConfig,
    _build_nutrition_payload,
    _slugify,
    _to_float,
    _to_graphql_stock_status,
    _to_int,
)


@asset
def upload_to_api(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    product_analysis: dict,
    scraped_metadata: RawScrapedData,
) -> list[dict]:
    """Creates one product per analyzed item and links generated scraped items."""
    api = client.get_client()
    try:
        started = time.perf_counter()
        origin_item = api.get_scraped_item(config.item_id)
        if not origin_item:
            raise Exception(f"Scraped item {config.item_id} not found")

        origin_page_url = (
            origin_item.get("sourcePageUrl")
            or origin_item.get("productLink")
            or config.url
        )
        origin_store_slug = origin_item.get("storeSlug") or config.store_slug
        ensured_origin = api.ensure_source_page(
            config.item_id, origin_page_url, origin_store_slug
        )
        if not ensured_origin:
            raise Exception(f"Failed to ensure source page for item {config.item_id}")

        page_url = ensured_origin.get("sourcePageUrl") or origin_page_url

        items = product_analysis.get("items") or []
        if not items:
            items = [
                {
                    "name": scraped_metadata.name
                    or origin_item.get("name")
                    or "Unknown Product"
                }
            ]

        results: list[dict] = []
        created_count = 0
        for idx, analysis_data in enumerate(items):
            if idx == 0:
                scraped_item = (
                    api.update_scraped_item_data(
                        item_id=int(ensured_origin["id"]),
                        name=analysis_data.get("name"),
                        source_page_url=page_url,
                        store_slug=origin_store_slug,
                    )
                    or ensured_origin
                )
            else:
                base_name = (
                    analysis_data.get("name") or scraped_metadata.name or "product"
                )
                variant_name = analysis_data.get("variant_name") or f"v{idx + 1}"
                origin_external_id = str(ensured_origin.get("externalId") or "")
                ext_id = f"{origin_external_id}::v{idx + 1}-{_slugify(base_name)}-{_slugify(variant_name)}"[
                    :100
                ]
                scraped_item = api.upsert_scraped_item_variant(
                    origin_item_id=int(ensured_origin["id"]),
                    external_id=ext_id,
                    name=base_name,
                    page_url=page_url,
                    store_slug=origin_store_slug,
                    price=(
                        _to_float(origin_item.get("price"), default=0.0)
                        if origin_item.get("price") is not None
                        else None
                    ),
                    stock_status=origin_item.get("stockStatus"),
                )
                if not scraped_item:
                    raise Exception("Failed to upsert scraped item variant")
                created_count += 1

            # Idempotency guard: skip only when LINKED item has a valid ProductStore.
            status_value = str(scraped_item.get("status") or "").lower()
            product_store_id = scraped_item.get("productStoreId")
            if status_value == "linked" and product_store_id:
                context.log.info(
                    f"Skipping already linked item {scraped_item['id']} ({scraped_item.get('externalId')})"
                )
                linked_product_id = scraped_item.get("linkedProductId")
                results.append(
                    {
                        "product": {"id": linked_product_id},
                        "errors": [],
                        "skipped": True,
                    }
                )
                continue
            if status_value == "linked":
                context.log.warning(
                    f"Item {scraped_item['id']} marked LINKED without product_store; reprocessing."
                )

            tags_hierarchy = analysis_data.get("tags_hierarchy") or []
            payload = {
                "name": analysis_data.get("name")
                or scraped_metadata.name
                or "Unknown Product",
                "brandName": scraped_metadata.brand_name or "Unknown Brand",
                "weight": _to_int(analysis_data.get("weight_grams")),
                "ean": scraped_metadata.ean,
                "description": scraped_metadata.description,
                "packaging": analysis_data.get("packaging") or "CONTAINER",
                "originScrapedItemId": int(scraped_item["id"]),
                "stores": [
                    {
                        "storeName": origin_store_slug,
                        "productLink": page_url,
                        "price": _to_float(
                            scraped_metadata.price or origin_item.get("price") or 0.0
                        ),
                        "externalId": scraped_item.get("externalId"),
                        "stockStatus": _to_graphql_stock_status(
                            scraped_metadata.stock_status
                            or origin_item.get("stockStatus")
                        ),
                        "affiliateLink": "",
                    }
                ],
                "nutrition": _build_nutrition_payload(analysis_data),
                "categoryPath": analysis_data.get("category_hierarchy") or [],
                "tagPaths": [{"path": path} for path in tags_hierarchy if path],
                "tags": [],
                "isCombo": bool(analysis_data.get("is_combo")),
                "components": [
                    {
                        "name": c.get("name"),
                        "quantity": _to_int(c.get("quantity"), default=1),
                        "weightHint": c.get("weight_hint"),
                        "packagingHint": c.get("packaging_hint"),
                    }
                    for c in (analysis_data.get("components") or [])
                    if c.get("name")
                ],
                "nutrientClaims": analysis_data.get("nutrient_claims") or [],
                "isPublished": False,
            }

            context.log.info(
                f"Uploading product {idx + 1}/{len(items)} with origin item {scraped_item['id']}"
            )
            result = api.create_product(payload)
            results.append(result or {})

        context.add_output_metadata(
            {
                "items_uploaded": len(results),
                "additional_scraped_items_created": created_count,
                "page_id": ensured_origin.get("sourcePageId"),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        return results
    except Exception as e:
        context.log.error(f"Upload failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise
