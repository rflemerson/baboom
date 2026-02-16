"""Dagster resource for scraper service."""

from dagster import ConfigurableResource

from ...tools.scraper import ScraperService


class ScraperServiceResource(ConfigurableResource):
    """Dagster resource for ScraperService."""

    def get_service(self) -> ScraperService:
        """Return scraper service instance."""
        return ScraperService()
