from dagster import ConfigurableResource

from .client import AgentClient
from .storage import get_storage
from .tools.scraper import ScraperService


class AgentClientResource(ConfigurableResource):
    """Dagster resource for AgentClient."""

    def get_client(self) -> AgentClient:
        """Get the authenticated AgentClient."""
        return AgentClient()


class ScraperServiceResource(ConfigurableResource):
    """Dagster resource for ScraperService."""

    def get_service(self) -> ScraperService:
        """Get the ScraperService instance."""
        return ScraperService()


class StorageResource(ConfigurableResource):
    """Dagster resource for StorageBackend."""

    def get_storage(self):
        """Get the configured storage backend."""
        return get_storage()
