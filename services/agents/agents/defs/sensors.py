"""Dagster sensor polling the work queue and launching the item pipeline."""

from typing import Any

from dagster import DefaultSensorStatus, SkipReason, sensor

from ..client import AgentClient
from .pipeline import PROCESS_ITEM_JOB_NAME, QueueWorkItem, build_item_run_request


def _parse_work_item(work: dict[str, Any] | None) -> QueueWorkItem | None:
    """Normalize raw API queue payload into the minimum launchable shape."""
    if not work:
        return None

    item_id = int(work["id"])
    url = work.get("productLink") or work.get("sourcePageUrl")
    if not url:
        return None

    return QueueWorkItem(
        item_id=item_id,
        url=url,
        store_name=work.get("storeName", "unknown"),
        store_slug=work.get("storeSlug", "unknown"),
    )


@sensor(
    job_name=PROCESS_ITEM_JOB_NAME,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.STOPPED,
)
def work_queue_sensor(
    context: object,
) -> object:
    """Poll API for new items to process."""
    _ = context
    api = AgentClient()
    work = api.checkout_work()
    if not work:
        yield SkipReason("Queue empty. Sleeping...")
        return
    item = _parse_work_item(work)
    if item is None:
        yield SkipReason(f"Item {int(work['id'])} has no source URL.")
        return
    yield build_item_run_request(item)
