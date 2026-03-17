"""GraphQL schema package for scraper automation workflows."""

from .mutations import ScrapersMutation
from .queries import ScrapersQuery

__all__ = ["ScrapersMutation", "ScrapersQuery"]
