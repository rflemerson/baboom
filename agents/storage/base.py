"""Base storage backend definition."""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def upload(
        self, bucket: str, key: str, data: bytes, content_type: str | None = None
    ) -> str:
        """
        Uploads data to the storage backend.

        Returns the public URL or identifier of the uploaded object.
        """
        pass

    @abstractmethod
    def download(self, bucket: str, key: str) -> bytes:
        """Downloads data from the storage backend."""
        pass

    @abstractmethod
    def exists(self, bucket: str, key: str) -> bool:
        """Checks if an object exists in the storage backend."""
        pass

    @abstractmethod
    def delete(self, bucket: str, key: str) -> None:
        """Deletes an object from the storage backend."""
        pass

    @abstractmethod
    def get_url(self, bucket: str, key: str) -> str:
        """Returns the URL for a given key."""
        pass
