"""GraphQL entrypoints for scraper-specific queries and mutations."""

from .mutations import ScrapersMutation
from .queries import ScrapersQuery

__all__ = ["ScrapersMutation", "ScrapersQuery"]
