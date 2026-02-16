"""Dagster code location entrypoint for the agents pipeline."""

from dagster import Definitions, define_asset_job, load_assets_from_modules

from .defs.assets import ASSET_MODULES
from .defs.resources import AgentClientResource, ScraperServiceResource, StorageResource
from .defs.sensors import work_queue_sensor

all_assets = load_assets_from_modules(ASSET_MODULES)
process_item_job = define_asset_job(name="process_item_job", selection=all_assets)

defs = Definitions(
    assets=all_assets,
    jobs=[process_item_job],
    sensors=[work_queue_sensor],
    resources={
        "client": AgentClientResource(),
        "scraper": ScraperServiceResource(),
        "storage": StorageResource(),
    },
)
