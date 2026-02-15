"""Dagster assets for the page-first product ingestion pipeline."""

import json
import os
import re
from typing import Any

from dagster import AssetExecutionContext, Config, MetadataValue, asset
from django.apps import apps

from .brain.raw_extraction_agent import run_raw_extraction
from .brain.structured_agent import run_structured_extraction
from .resources import AgentClientResource, ScraperServiceResource, StorageResource
from .schemas.product import RawScrapedData


def _get_scraper_models() -> tuple[Any, Any]:
    scraped_item = apps.get_model("scrapers", "ScrapedItem")
    scraped_page = apps.get_model("scrapers", "ScrapedPage")
    return scraped_item, scraped_page


class ItemConfig(Config):
    """Configuration for running a specific queued scraped item."""

    item_id: int
    url: str
    store_slug: str = "unknown"


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "item"


def _to_graphql_stock_status(status: str | None) -> str:
    stock_map = {
        "A": "AVAILABLE",
        "L": "LAST_UNITS",
        "O": "OUT_OF_STOCK",
        "AVAILABLE": "AVAILABLE",
        "LAST_UNITS": "LAST_UNITS",
        "OUT_OF_STOCK": "OUT_OF_STOCK",
    }
    return stock_map.get((status or "").upper(), "AVAILABLE")


def _build_nutrition_payload(analysis_data: dict) -> list[dict]:
    nutrition = analysis_data.get("nutrition_facts")
    if not nutrition:
        return []

    micronutrients = [
        {
            "name": m.get("name"),
            "value": float(m.get("value") or 0),
            "unit": m.get("unit") or "mg",
        }
        for m in (nutrition.get("micronutrients") or [])
        if m.get("name")
    ]

    return [
        {
            "flavorNames": analysis_data.get("flavor_names") or [],
            "nutritionFacts": {
                "description": analysis_data.get("variant_name") or "AI Analysis",
                "servingSizeGrams": float(nutrition.get("serving_size_grams") or 0),
                "energyKcal": int(nutrition.get("energy_kcal") or 0),
                "proteins": float(nutrition.get("proteins") or 0),
                "carbohydrates": float(nutrition.get("carbohydrates") or 0),
                "totalSugars": float(nutrition.get("total_sugars") or 0),
                "addedSugars": float(nutrition.get("added_sugars") or 0),
                "totalFats": float(nutrition.get("total_fats") or 0),
                "saturatedFats": float(nutrition.get("saturated_fats") or 0),
                "transFats": float(nutrition.get("trans_fats") or 0),
                "dietaryFiber": float(nutrition.get("dietary_fiber") or 0),
                "sodium": float(nutrition.get("sodium") or 0),
                "micronutrients": micronutrients,
            },
        }
    ]


def _candidate_nutrition_signal(candidate: dict) -> int:
    signal = int(candidate.get("nutrition_signal") or 0)
    metadata = candidate.get("metadata") or {}
    text = " ".join(
        [
            str(metadata.get("alt") or ""),
            str(metadata.get("title") or ""),
            str(metadata.get("class") or ""),
            str(metadata.get("id") or ""),
            str(candidate.get("url") or ""),
        ]
    ).lower()
    nutrition_keywords = [
        "tabela",
        "nutricional",
        "nutrition",
        "facts",
        "label",
        "rotulo",
        "ingrediente",
        "ingredientes",
        "composition",
        "composicao",
    ]
    signal += sum(1 for kw in nutrition_keywords if kw in text)
    return signal


def _select_images_for_ocr(candidates: list[dict], bucket: str) -> list[str]:
    max_total = int(os.getenv("OCR_MAX_IMAGES", "12"))
    max_nutrition = int(os.getenv("OCR_MAX_NUTRITION_IMAGES", "8"))
    max_if_no_nutrition = int(os.getenv("OCR_MAX_IMAGES_NO_NUTRITION", "16"))

    valid = [c for c in candidates if int(c.get("score", 0)) > 0 and c.get("file")]
    valid.sort(key=lambda x: int(x.get("score", 0)), reverse=True)

    nutrition_candidates = [c for c in valid if _candidate_nutrition_signal(c) > 0]
    nutrition_candidates.sort(
        key=lambda x: (_candidate_nutrition_signal(x), int(x.get("score", 0))),
        reverse=True,
    )

    selected_files: list[str] = []
    seen_files: set[str] = set()

    for c in nutrition_candidates[:max_nutrition]:
        file_name = str(c["file"])
        if file_name not in seen_files:
            selected_files.append(file_name)
            seen_files.add(file_name)

    target_total = max_total if selected_files else max_if_no_nutrition
    for c in valid:
        file_name = str(c["file"])
        if file_name in seen_files:
            continue
        selected_files.append(file_name)
        seen_files.add(file_name)
        if len(selected_files) >= target_total:
            break

    return [f"{bucket}/{file_name}" for file_name in selected_files]


@asset
def downloaded_assets(
    context: AssetExecutionContext,
    config: ItemConfig,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
) -> dict:
    """Ensures page assets are downloaded and returns page storage context."""
    service = scraper.get_service()
    api = client.get_client()

    try:
        scraped_item_model, scraped_page_model = _get_scraper_models()

        item = scraped_item_model.objects.get(pk=config.item_id)
        page = item.source_page
        if not page:
            page, _ = scraped_page_model.objects.get_or_create(
                url=config.url,
                defaults={"store_slug": config.store_slug},
            )
            item.source_page = page
            item.save(update_fields=["source_page", "updated_at"])

        storage_path = service.download_assets(page.id, page.url)
        context.add_output_metadata(
            {
                "path": storage_path,
                "url": MetadataValue.url(page.url),
                "page_id": page.id,
                "origin_item_id": item.id,
            }
        )
        return {
            "storage_path": storage_path,
            "url": page.url,
            "page_id": page.id,
            "origin_item_id": item.id,
            "store_slug": item.store_slug or config.store_slug,
        }
    except Exception as e:
        context.log.error(f"Download failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise


@asset
def scraped_metadata(
    context: AssetExecutionContext,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
    downloaded_assets: dict,
) -> RawScrapedData:
    """Reads downloaded HTML and extracts lightweight metadata."""
    service = scraper.get_service()
    api = client.get_client()
    storage_path = downloaded_assets["storage_path"]
    page_url = downloaded_assets["url"]
    store_slug = downloaded_assets["store_slug"]
    origin_item_id = int(downloaded_assets["origin_item_id"])

    try:
        context.log.info(f"Extracting metadata from {storage_path}")
        meta_dict = service.extract_metadata(storage_path, page_url)
        raw_data = service.consolidate(meta_dict, brand_name_override=store_slug)
        context.add_output_metadata({"product_name": raw_data.name or "unknown"})
        return raw_data
    except Exception as e:
        context.log.error(f"Metadata extraction failed: {e}")
        api.report_error(origin_item_id, str(e), is_fatal=False)
        raise


@asset
def ocr_extraction(
    context: AssetExecutionContext,
    storage: StorageResource,
    client: AgentClientResource,
    scraped_metadata: RawScrapedData,
    downloaded_assets: dict,
) -> str:
    """Runs multimodal raw extraction over top-ranked page images."""
    store = storage.get_storage()
    api = client.get_client()
    origin_item_id = int(downloaded_assets["origin_item_id"])
    page_url = downloaded_assets["url"]

    bucket, _ = downloaded_assets["storage_path"].split("/", 1)
    try:
        image_paths: list[str] = []
        candidates_key = "candidates.json"
        if store.exists(bucket, candidates_key):
            candidates = json.loads(store.download(bucket, candidates_key))
            image_paths = _select_images_for_ocr(candidates, bucket)

        raw_text = run_raw_extraction(
            name=scraped_metadata.name or page_url,
            description=scraped_metadata.description or "",
            image_paths=image_paths,
        )

        context.add_output_metadata(
            {
                "images_used": len(image_paths),
                "images_sent": image_paths,
                "text_preview": MetadataValue.md(
                    (raw_text[:500] + "...") if raw_text else ""
                ),
            }
        )
        return raw_text
    except Exception as e:
        context.log.error(f"OCR extraction failed: {e}")
        api.report_error(origin_item_id, str(e), is_fatal=False)
        raise


@asset
def product_analysis(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    ocr_extraction: str,
) -> dict:
    """Converts raw text into structured list of product analyses."""
    api = client.get_client()
    try:
        result = run_structured_extraction(ocr_extraction)
        payload = result.model_dump(by_alias=True)
        context.add_output_metadata({"items_detected": len(payload.get("items", []))})
        return payload
    except Exception as e:
        context.log.error(f"Structured analysis failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise


@asset
def upload_to_api(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    product_analysis: dict,
    scraped_metadata: RawScrapedData,
    downloaded_assets: dict,
) -> list[dict]:
    """Creates one product per analyzed item and links generated scraped items."""
    api = client.get_client()
    try:
        scraped_item_model, scraped_page_model = _get_scraper_models()

        origin_item = scraped_item_model.objects.get(pk=config.item_id)
        page = origin_item.source_page
        if not page:
            page, _ = scraped_page_model.objects.get_or_create(
                url=config.url,
                defaults={"store_slug": config.store_slug},
            )
            origin_item.source_page = page
            origin_item.save(update_fields=["source_page", "updated_at"])

        items = product_analysis.get("items") or []
        if not items:
            items = [
                {"name": scraped_metadata.name or origin_item.name or "Unknown Product"}
            ]

        results: list[dict] = []
        created_count = 0
        for idx, analysis_data in enumerate(items):
            if idx == 0:
                scraped_item = origin_item
                if analysis_data.get("name"):
                    scraped_item.name = analysis_data["name"]
                if scraped_item.source_page_id != page.id:
                    scraped_item.source_page = page
                scraped_item.save(update_fields=["name", "source_page", "updated_at"])
            else:
                base_name = (
                    analysis_data.get("name") or scraped_metadata.name or "product"
                )
                variant_name = analysis_data.get("variant_name") or f"v{idx + 1}"
                ext_id = f"{origin_item.external_id}::v{idx + 1}-{_slugify(base_name)}-{_slugify(variant_name)}"[
                    :100
                ]
                scraped_item, _ = scraped_item_model.objects.update_or_create(
                    store_slug=origin_item.store_slug,
                    external_id=ext_id,
                    defaults={
                        "name": base_name,
                        "source_page": page,
                        "price": origin_item.price,
                        "stock_status": origin_item.stock_status,
                        "status": scraped_item_model.Status.PROCESSING,
                    },
                )
                created_count += 1

            tags_hierarchy = analysis_data.get("tags_hierarchy") or []
            payload = {
                "name": analysis_data.get("name")
                or scraped_metadata.name
                or "Unknown Product",
                "brandName": scraped_metadata.brand_name or "Unknown Brand",
                "weight": int(analysis_data.get("weight_grams") or 0),
                "ean": scraped_metadata.ean,
                "description": scraped_metadata.description,
                "packaging": analysis_data.get("packaging") or "CONTAINER",
                "originScrapedItemId": int(scraped_item.id),
                "stores": [
                    {
                        "storeName": origin_item.store_slug,
                        "productLink": page.url,
                        "price": float(
                            scraped_metadata.price or origin_item.price or 0.0
                        ),
                        "externalId": scraped_item.external_id,
                        "stockStatus": _to_graphql_stock_status(
                            scraped_metadata.stock_status or origin_item.stock_status
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
                        "quantity": int(c.get("quantity") or 1),
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
                f"Uploading product {idx + 1}/{len(items)} with origin item {scraped_item.id}"
            )
            result = api.create_product(payload)
            results.append(result or {})

        context.add_output_metadata(
            {
                "items_uploaded": len(results),
                "additional_scraped_items_created": created_count,
                "page_id": page.id,
            }
        )
        return results
    except Exception as e:
        context.log.error(f"Upload failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise
