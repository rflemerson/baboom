from dagster import ConfigurableResource

from .client import AgentClient
from .storage import get_storage
from .tools.scraper import ScraperService


class AgentClientResource(ConfigurableResource):
    def get_client(self) -> AgentClient:
        return AgentClient()


class ScraperServiceResource(ConfigurableResource):
    def get_service(self) -> ScraperService:
        return ScraperService()


class StorageResource(ConfigurableResource):
    def get_storage(self):
        return get_storage()
