"""Dagster code location entrypoint for the agents pipeline."""

from dagster import Definitions, load_assets_from_modules

from .defs import assets as assets_module
from .defs.pipeline import build_process_item_job
from .defs.sensors import work_queue_sensor

all_assets = load_assets_from_modules([assets_module])


process_item_job = build_process_item_job(selection=all_assets)

defs = Definitions(
    assets=all_assets,
    jobs=[process_item_job],
    sensors=[work_queue_sensor],
)
