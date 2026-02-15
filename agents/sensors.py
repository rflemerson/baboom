from dagster import DefaultSensorStatus, RunRequest, SkipReason, sensor

from .resources import AgentClientResource


@sensor(
    job_name="process_item_job",
    minimum_interval_seconds=10,
    default_status=DefaultSensorStatus.RUNNING,
)
def work_queue_sensor(context, client: AgentClientResource):
    """Poll API for new items to process."""
    api = client.get_client()

    # Check for work (no force, get next in queue)
    work = api.checkout_work()

    if not work:
        yield SkipReason("Queue empty. Sleeping...")
        return

    item_id = int(work["id"])
    url = work.get("productLink") or work.get("sourcePageUrl")
    if not url:
        yield SkipReason(f"Item {item_id} has no source URL.")
        return

    # Configuration passed to Assets
    # In Dagster SDA (Software-Defined Assets), config is passed per asset.
    run_config = {
        "ops": {
            "downloaded_assets": {
                "config": {
                    "item_id": item_id,
                    "url": url,
                    "store_slug": work.get("storeSlug", "unknown"),
                }
            },
            "product_analysis": {
                "config": {
                    "item_id": item_id,
                    "url": url,
                    "store_slug": work.get("storeSlug", "unknown"),
                }
            },
            "upload_to_api": {
                "config": {
                    "item_id": item_id,
                    "url": url,
                    "store_slug": work.get("storeSlug", "unknown"),
                }
            },
        }
    }

    yield RunRequest(
        run_config=run_config,
        tags={"item_id": str(item_id), "store": work.get("storeName", "unknown")},
    )
