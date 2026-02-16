"""Dagster resource for storage backend."""

from dagster import ConfigurableResource

from ...storage import get_storage


class StorageResource(ConfigurableResource):
    """Dagster resource for storage backend."""

    def get_storage(self):
        """Return configured storage backend."""
        return get_storage()
