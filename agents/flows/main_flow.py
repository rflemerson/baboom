import json

from prefect import flow, get_run_logger, task

from ..brain.product_agent import run_product_analysis
from ..client import AgentClient
from ..schemas.analysis import ProductAnalysisResult
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


@task(name="analyze_product_task", retries=2, retry_delay_seconds=30)
def analyze_product_task(
    raw_data: RawScrapedData,
    storage_base_path: str,
    existing_categories: list[str] | None = None,
    existing_tags: list[str] | None = None,
) -> ProductAnalysisResult:
    """
    Calls the unified ProductAnalysisAgent to extract hierarchy, metadata, nutrition, and flavors
    using both text and images.
    """
    logger = get_run_logger()
    logger.info(f"Analyzing product: {raw_data.name}")

    # 1. Gather images
    storage = get_storage()
    try:
        bucket, _ = storage_base_path.split("/", 1)
        candidates_key = "candidates.json"

        image_paths = []
        if storage.exists(bucket, candidates_key):
            candidates_data = storage.download(bucket, candidates_key)
            candidates = json.loads(candidates_data.decode("utf-8"))

            # Use top 3 images for analysis to give context (front, nutrition, back)
            # Filter for images with reasonable score
            valid_candidates = [c for c in candidates if c["score"] > 0]
            # Sort by score descending
            valid_candidates.sort(key=lambda x: x["score"], reverse=True)

            # Take top 3
            for c in valid_candidates[:3]:
                image_paths.append(f"{bucket}/{c['file']}")

    except Exception as e:
        logger.warning(f"Failed to load image candidates: {e}")
        image_paths = []

    # 2. Call Agent
    return run_product_analysis(
        name=raw_data.name,
        description=raw_data.description or "",
        image_paths=image_paths,
        existing_categories=existing_categories,
        existing_tags=existing_tags,
    )


@task(retries=3, retry_delay_seconds=30)
def upload_product_task(
    item_id: int,
    url: str,
    raw_data: RawScrapedData,
    analysis_result: ProductAnalysisResult,
    store_name: str | None = None,
    external_id: str | None = None,
) -> None:
    """
    Final consolidation and upload to the database via GraphQL.
    """
    logger = get_run_logger()
    client = AgentClient()

    try:
        # Convert Analysis Result to Nutrition Profile format
        nutrition_profiles = []
        if analysis_result.nutrition_facts:
            # Inject identified flavors into the nutrition facts wrapper if valid
            nutrition_profiles.append(
                ProductNutritionProfile(
                    nutrition_facts=analysis_result.nutrition_facts,
                    flavor_names=analysis_result.flavor_names,
                )
            )

        final_product = ScrapedProductData(
            name=raw_data.name,
            brand_name=raw_data.brand_name,
            ean=raw_data.ean,
            description=raw_data.description,
            image_url=raw_data.image_url,
            nutrition=nutrition_profiles,
            origin_scraped_item_id=item_id,
            weight=analysis_result.weight_grams or 0,
            packaging=analysis_result.packaging or "CONTAINER",
            category_path=analysis_result.category_hierarchy or [],
            tag_paths=analysis_result.tags_hierarchy or [],
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
                    "price": float(raw_data.price or 0.0),
                    "externalId": external_id or "",
                    "stockStatus": stock_map.get(
                        raw_data.stock_status or "A", "AVAILABLE"
                    ),
                }
            ],
            "nutrition": [
                {
                    "nutritionFacts": n.nutrition_facts.model_dump(
                        exclude={"flavor_names"}, exclude_none=True, by_alias=True
                    ),
                    "flavorNames": n.flavor_names,
                }
                for n in (final_product.nutrition or [])
            ],
            "categoryPath": final_product.category_path,
            "tagPaths": [{"path": tp} for tp in final_product.tag_paths],
            "isPublished": True,
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
    work = client.checkout_work()
    if not work:
        logger.info("Queue empty. Finished.")
        return

    logger.info(f"Processing Item {work['id']}: {work['productLink']}")

    try:
        # Step 0: Fetch Taxonomy Context
        existing_categories, existing_tags = client.get_taxonomy()

        # Step 1: Download HTML and images to storage
        html_storage_path = download_product_assets(work["id"], work["productLink"])

        # Step 2: Extract raw metadata from HTML in storage
        raw_metadata_dict = extract_metadata_task(
            html_storage_path, work["productLink"]
        )
        service = ScraperService()
        raw_scraped_data = service.consolidate(
            raw_metadata_dict,
            brand_name_override=work.get("storeName"),
            price=work.get("price"),
            stock_status=work.get("stockStatus"),
        )

        # Step 3: Unified AI Analysis (Multimodal)
        analysis_result = analyze_product_task(
            raw_scraped_data, html_storage_path, existing_categories, existing_tags
        )

        # Step 4: Final Upload
        upload_product_task(
            work["id"],
            work["productLink"],
            raw_scraped_data,
            analysis_result,
            store_name=work.get("storeName"),
            external_id=work.get("externalId"),
        )

    except Exception as e:
        logger.error(f"Flow failed for item {work['id']}: {e}")
        client.report_error(work["id"], str(e), is_fatal=True)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    product_ingestion_flow()
