"""Dagster sensor polling the work queue and launching the item pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dagster import DefaultSensorStatus, RunRequest, SkipReason, sensor

from ..client import AgentClient
from .pipeline import PROCESS_ITEM_JOB_NAME, QueueWorkItem, build_item_run_request

if TYPE_CHECKING:
    from collections.abc import Iterator


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
    minimum_interval_seconds=10,
    default_status=DefaultSensorStatus.RUNNING,
)
def work_queue_sensor(
    _context: object,
) -> Iterator[RunRequest | SkipReason]:
    """Poll API for new items to process."""
    api = AgentClient()
    work = api.checkout_work()
    item = _parse_work_item(work)
    if not work:
        yield SkipReason("Queue empty. Sleeping...")
        return
    if item is None:
        yield SkipReason(f"Item {int(work['id'])} has no source URL.")
        return
    yield build_item_run_request(item)
