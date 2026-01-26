import os
import tempfile

from .base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """
    Storage backend that uses the local filesystem.
    """

    def __init__(self, base_path: str | None = None):
        if base_path is None:
            base_path = os.path.join(tempfile.gettempdir(), "baboom")
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _get_full_path(self, bucket: str, key: str) -> str:
        path = os.path.join(self.base_path, bucket, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def upload(
        self, bucket: str, key: str, data: bytes, content_type: str | None = None
    ) -> str:
        path = self._get_full_path(bucket, key)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def download(self, bucket: str, key: str) -> bytes:
        path = self._get_full_path(bucket, key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "rb") as f:
            return f.read()

    def exists(self, bucket: str, key: str) -> bool:
        path = self._get_full_path(bucket, key)
        return os.path.exists(path)

    def delete(self, bucket: str, key: str) -> None:
        path = self._get_full_path(bucket, key)
        if os.path.exists(path):
            os.remove(path)

    def get_url(self, bucket: str, key: str) -> str:
        return f"file://{self._get_full_path(bucket, key)}"
