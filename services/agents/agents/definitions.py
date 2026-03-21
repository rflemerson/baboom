"""Dagster code location entrypoint for the agents pipeline."""

from dagster import Definitions, load_assets_from_modules

from .defs.assets import ASSET_MODULES
from .defs.pipeline import build_process_item_job
from .defs.resources import AgentClientResource, ScraperServiceResource, StorageResource
from .defs.sensors import work_queue_sensor

all_assets = load_assets_from_modules(ASSET_MODULES)


def _build_resources() -> dict[str, object]:
    """Return shared Dagster resources for the code location."""
    return {
        "client": AgentClientResource(),
        "scraper": ScraperServiceResource(),
        "storage": StorageResource(),
    }


process_item_job = build_process_item_job(selection=all_assets)

defs = Definitions(
    assets=all_assets,
    jobs=[process_item_job],
    sensors=[work_queue_sensor],
    resources=_build_resources(),
)
