"""Dagster config objects shared across pipeline assets."""

from dagster import Config


class ItemConfig(Config):
    """Configuration for running a specific queued scraped item."""

    item_id: int
    url: str
    store_slug: str = "unknown"
