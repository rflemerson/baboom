from dagster import Definitions, define_asset_job, load_assets_from_modules

from . import assets
from .resources import AgentClientResource, ScraperServiceResource, StorageResource
from .sensors import work_queue_sensor

# Carrega todos os assets do arquivo assets.py
all_assets = load_assets_from_modules([assets])

# Define um Job que sabe materializar (rodar) todos esses assets em ordem
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
