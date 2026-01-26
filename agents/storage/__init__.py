from .base import StorageBackend
from .local import LocalStorageBackend


def get_storage() -> StorageBackend:
    """
    Factory function to get the configured storage backend.
    Currently defaults to LocalStorageBackend.
    """
    # In the future, this can check environment variables to return S3StorageBackend
    return LocalStorageBackend()
