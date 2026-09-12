"""Tests for local image downloading and manifest persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_server.tools import images

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class FakeResponse:
    """Minimal requests response double used by image tests."""

    def __init__(self, content_type: str = "image/jpeg") -> None:
        """Initialize a response with image bytes and a content type."""
        self.content = b"fake-bytes"
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        """Match the successful requests response API."""


def test_download_images_writes_files_and_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Write downloaded image files and their manifest."""
    monkeypatch.setattr(images.requests, "get", lambda *_a, **_kw: FakeResponse())

    manifest = images.download_images(
        ["https://x.com/a.jpg", "https://x.com/b.png"],
        tmp_path,
    )

    assert [entry["filename"] for entry in manifest["downloaded"]] == [
        "image_001.jpg",
        "image_002.png",
    ]
    assert manifest["errors"] == []
    assert images.load_image_manifest(tmp_path) == manifest


def test_download_images_accumulates_and_skips_known(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Append new downloads while skipping URLs already recorded."""
    monkeypatch.setattr(images.requests, "get", lambda *_a, **_kw: FakeResponse())

    images.download_images(["https://x.com/a.jpg"], tmp_path)
    manifest = images.download_images(
        ["https://x.com/a.jpg", "https://x.com/b.png"],
        tmp_path,
    )

    assert [entry["filename"] for entry in manifest["downloaded"]] == [
        "image_001.jpg",
        "image_002.png",
    ]


def test_download_images_records_non_image_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Record a useful error when a URL returns non-image content."""
    monkeypatch.setattr(
        images.requests,
        "get",
        lambda *_a, **_kw: FakeResponse(content_type="text/html"),
    )

    manifest = images.download_images(["https://x.com/page"], tmp_path)

    assert manifest["downloaded"] == []
    assert manifest["errors"][0]["url"] == "https://x.com/page"
