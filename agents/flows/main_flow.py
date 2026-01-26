import json

from prefect import flow, get_run_logger, task

from ..brain.metadata_agent import run_metadata_extraction
from ..brain.nutrition_agent import run_nutrition_extraction
from ..client import AgentClient
from ..schemas.metadata import ProductMetadata
from ..schemas.nutrition import ProductNutritionProfile
from ..schemas.product import RawScrapedData, ScrapedProductData
from ..storage import get_storage
from ..tools.scraper import ScraperService


@task(retries=3, retry_delay_seconds=10)
def download_product_assets(item_id: int, url: str) -> str:
    service = ScraperService()
    return service.download_assets(item_id, url)


@task
def extract_metadata_task(html_storage_path: str, url: str) -> dict:
    service = ScraperService()
    return service.extract_metadata(html_storage_path, url)


@task
def extract_nutrition_data(storage_context_path: str) -> list[ProductNutritionProfile]:
    """
    storage_context_path is the bucket/key to the HTML or base folder.
    """
    logger = get_run_logger()
    storage = get_storage()

    try:
        bucket, _ = storage_context_path.split("/", 1)
    except ValueError:
        logger.error(f"Invalid storage context path: {storage_context_path}")
        return []

    candidates_key = "candidates.json"

    if not storage.exists(bucket, candidates_key):
        logger.warning(f"No {candidates_key} found in storage for bucket {bucket}.")
        return []

    try:
        candidates_data = storage.download(bucket, candidates_key)
        candidates = json.loads(candidates_data.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to load candidates from storage: {e}")
        return []

    if not candidates:
        logger.warning("No image candidates found.")
        return []

    top_candidate = candidates[0]
    image_key = top_candidate["file"]
    storage_image_path = f"{bucket}/{image_key}"

    logger.info(
        f"Extracting nutrition from {storage_image_path} (Score: {top_candidate['score']})"
    )

    return run_nutrition_extraction(storage_image_path)


@task
def enrich_metadata_task(raw_data: RawScrapedData) -> ProductMetadata:
    """
    Calls Metadata Agent to enrich raw data with category, weight, and tags.
    """
    logger = get_run_logger()
    logger.info(f"Enriching metadata for: {raw_data.name}")
    return run_metadata_extraction(raw_data.name, raw_data.description or "")


@task(retries=3, retry_delay_seconds=30)
def upload_product_task(
    item_id: int,
    url: str,
    raw_data: RawScrapedData,
    ai_metadata: ProductMetadata,
    nutrition_data: list[ProductNutritionProfile],
    store_name: str | None = None,
    external_id: str | None = None,
) -> None:
    """
    Final consolidation and upload to the database via GraphQL.
    """
    logger = get_run_logger()
    client = AgentClient()

    try:
        final_product = ScrapedProductData(
            name=raw_data.name,
            brand_name=raw_data.brand_name,
            ean=raw_data.ean,
            description=raw_data.description,
            image_url=raw_data.image_url,
            nutrition=nutrition_data,
            origin_scraped_item_id=item_id,
            weight=ai_metadata.weight_grams or 0,
            packaging=ai_metadata.packaging or "CONTAINER",
            category_name=ai_metadata.category or "General",
            tags=ai_metadata.tags or [],
        )

        logger.info(
            f"Uploading Product: {final_product.name} ({final_product.weight}g)"
        )

        # Prepare payload with correct field names for GraphQL Input
        packaging_map = {
            "REFILL": "REFILL",
            "CONTAINER": "CONTAINER",
            "BAR": "BAR",
            "OTHER": "OTHER",
        }
        stock_map = {
            "A": "AVAILABLE",
            "L": "LAST_UNITS",
            "O": "OUT_OF_STOCK",
        }

        # Prepare payload with correct field names for GraphQL Input
        payload = {
            "name": final_product.name,
            "brandName": final_product.brand_name,
            "weight": int(final_product.weight),
            "categoryName": final_product.category_name,
            "ean": final_product.ean,
            "description": final_product.description,
            "packaging": packaging_map.get(final_product.packaging, "CONTAINER"),
            "originScrapedItemId": int(final_product.origin_scraped_item_id),
            "stores": [
                {
                    "storeName": store_name or raw_data.brand_name,
                    "productLink": url,
                    "price": float(raw_data.price or 0),
                    "externalId": external_id or "",
                    "stockStatus": stock_map.get(
                        raw_data.stock_status or "A", "AVAILABLE"
                    ),
                }
            ]
            if raw_data.price
            else [],
            "nutrition": [
                {
                    "nutritionFacts": n.nutrition_facts.model_dump(
                        exclude_none=True, by_alias=True
                    ),
                    "flavorNames": n.flavor_names,
                }
                for n in (final_product.nutrition or [])
            ],
            "tags": final_product.tags,
            "isPublished": False,
        }

        client.create_product(payload)
        logger.info("Product created successfully!")

    except Exception as e:
        logger.error(f"Failed to upload: {e}")
        raise


@flow(name="Baboom Product Ingestion")
def product_ingestion_flow():
    logger = get_run_logger()
    client = AgentClient()

    logger.info("Checking for work...")
    item = client.checkout_work()
    if not item:
        logger.info("Queue empty. Finished.")
        return

    logger.info(f"Processing Item {item['id']}: {item['productLink']}")

    try:
        # 1. Download HTML and images to storage
        html_storage_path = download_product_assets(item["id"], item["productLink"])

        # 2. Extract raw metadata from HTML in storage
        raw_metadata_dict = extract_metadata_task(
            html_storage_path, item["productLink"]
        )
        service = ScraperService()
        raw_scraped_data = service.consolidate(
            raw_metadata_dict,
            brand_name_override=item.get("storeName"),
            price=item.get("price"),
            stock_status=item.get("stockStatus"),
        )

        # 3. AI Enrichment (Text Agent)
        ai_metadata = enrich_metadata_task(raw_scraped_data)

        # 4. AI Nutrition Extraction (Vision Agent)
        nutrition = extract_nutrition_data(html_storage_path)

        # 5. Final Upload
        upload_product_task(
            item["id"],
            item["productLink"],
            raw_scraped_data,
            ai_metadata,
            nutrition,
            store_name=item.get("storeName"),
            external_id=item.get("externalId"),
        )

    except Exception as e:
        logger.error(f"Flow failed for item {item['id']}: {e}")
        client.report_error(item["id"], str(e), is_fatal=True)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    product_ingestion_flow()
