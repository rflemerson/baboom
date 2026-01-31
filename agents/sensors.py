from dagster import DefaultSensorStatus, RunRequest, SkipReason, sensor

from .resources import AgentClientResource


@sensor(
    job_name="process_item_job",
    minimum_interval_seconds=10,
    default_status=DefaultSensorStatus.RUNNING,
)
def work_queue_sensor(context, client: AgentClientResource):
    """Polling na API para ver se tem item novo para processar."""
    api = client.get_client()

    # Checa trabalho (sem force, pega o próximo da fila)
    work = api.checkout_work()

    if not work:
        return SkipReason("Fila vazia. Dormindo...")

    item_id = int(work["id"])

    # Configuração para passar para os Assets
    # No Dagster SDA (Software-Defined Assets), a configuração é passada por asset
    run_config = {
        "ops": {
            "downloaded_assets": {
                "config": {
                    "item_id": item_id,
                    "url": work["productLink"],
                    "store_slug": work.get("storeSlug", "unknown"),
                }
            },
            "scraped_metadata": {
                "config": {
                    "item_id": item_id,
                    "url": work["productLink"],
                    "store_slug": work.get("storeSlug", "unknown"),
                }
            },
            "ocr_extraction": {
                "config": {
                    "item_id": item_id,
                    "url": work["productLink"],
                    "store_slug": work.get("storeSlug", "unknown"),
                }
            },
            "upload_to_api": {
                "config": {
                    "item_id": item_id,
                    "url": work["productLink"],
                    "store_slug": work.get("storeSlug", "unknown"),
                }
            },
        }
    }

    yield RunRequest(
        run_key=f"item_{item_id}",  # Evita processar o mesmo ID duas vezes
        run_config=run_config,
        tags={"item_id": str(item_id), "store": work.get("storeName", "unknown")},
    )
