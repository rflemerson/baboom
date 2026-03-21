"""Shared pipeline contract for the agents Dagster code location."""

from __future__ import annotations

from dataclasses import dataclass

from dagster import RunRequest, define_asset_job

PROCESS_ITEM_JOB_NAME = "process_item_job"
PROCESS_ITEM_OP_NAMES = (
    "downloaded_assets",
    "product_analysis",
    "upload_to_api",
)


@dataclass(frozen=True, slots=True)
class QueueWorkItem:
    """Normalized queue item required to launch one Dagster run."""

    item_id: int
    url: str
    store_name: str
    store_slug: str


def build_item_run_config(item: QueueWorkItem) -> dict:
    """Build the Dagster run config for one normalized queue item."""
    op_config = {
        "item_id": item.item_id,
        "url": item.url,
        "store_slug": item.store_slug,
    }
    return {
        "ops": {
            op_name: {"config": dict(op_config)} for op_name in PROCESS_ITEM_OP_NAMES
        },
    }


def build_item_run_request(item: QueueWorkItem) -> RunRequest:
    """Create the Dagster run request for one normalized queue item."""
    return RunRequest(
        run_key=str(item.item_id),
        run_config=build_item_run_config(item),
        tags={"item_id": str(item.item_id), "store": item.store_name},
    )


def build_process_item_job(*, selection: object) -> object:
    """Create the shared asset job for one queue item processing run."""
    return define_asset_job(name=PROCESS_ITEM_JOB_NAME, selection=selection)
