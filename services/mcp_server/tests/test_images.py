"""Tests for image downloading and manifest persistence."""

import pytest

from mcp_server.tools import images
from mcp_server.tools.workspace import set_current_item


class FakeResponse:
    """Minimal requests response double used by image tests."""

    def __init__(self, content_type: str = "image/jpeg") -> None:
        """Initialize a response with image bytes and a content type."""
        self.content = b"fake-bytes"
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        """Match the successful requests response API."""
        if self.content is None:
            raise RuntimeError


@pytest.fixture(autouse=True)
def current_item() -> None:
    """Set a current item before each image test."""
    set_current_item({"id": "1", "name": "Whey"})


def test_download_images_writes_files_and_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Write downloaded image files and their manifest."""
    monkeypatch.setattr(images.requests, "get", lambda *_a, **_kw: FakeResponse())

    manifest = images.download_images(["https://x.com/a.jpg", "https://x.com/b.png"])

    assert [entry["filename"] for entry in manifest["downloaded"]] == [
        "image_001.jpg",
        "image_002.png",
    ]
    assert manifest["errors"] == []
    assert images.load_image_manifest() == manifest


def test_download_images_accumulates_and_skips_known(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Append new downloads while skipping URLs already recorded."""
    monkeypatch.setattr(images.requests, "get", lambda *_a, **_kw: FakeResponse())

    images.download_images(["https://x.com/a.jpg"])
    manifest = images.download_images(["https://x.com/a.jpg", "https://x.com/b.png"])

    assert [entry["filename"] for entry in manifest["downloaded"]] == [
        "image_001.jpg",
        "image_002.png",
    ]


def test_download_images_records_non_image_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Record a useful error when a URL returns non-image content."""
    monkeypatch.setattr(
        images.requests,
        "get",
        lambda *_a, **_kw: FakeResponse(content_type="text/html"),
    )

    manifest = images.download_images(["https://x.com/page"])

    assert manifest["downloaded"] == []
    assert manifest["errors"][0]["url"] == "https://x.com/page"
