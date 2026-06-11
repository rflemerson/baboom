import pytest

from mcp_server.tools import images
from mcp_server.tools.workspace import set_current_item


class FakeResponse:
    def __init__(self, content_type="image/jpeg"):
        self.content = b"fake-bytes"
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def current_item():
    set_current_item({"id": "1", "name": "Whey"})


def test_download_images_writes_files_and_manifest(monkeypatch):
    monkeypatch.setattr(images.requests, "get", lambda *_a, **_kw: FakeResponse())

    manifest = images.download_images(["https://x.com/a.jpg", "https://x.com/b.png"])

    assert [entry["filename"] for entry in manifest["downloaded"]] == [
        "image_001.jpg",
        "image_002.png",
    ]
    assert manifest["errors"] == []
    assert images.load_image_manifest() == manifest


def test_download_images_accumulates_and_skips_known(monkeypatch):
    monkeypatch.setattr(images.requests, "get", lambda *_a, **_kw: FakeResponse())

    images.download_images(["https://x.com/a.jpg"])
    manifest = images.download_images(["https://x.com/a.jpg", "https://x.com/b.png"])

    assert [entry["filename"] for entry in manifest["downloaded"]] == [
        "image_001.jpg",
        "image_002.png",
    ]


def test_download_images_records_non_image_errors(monkeypatch):
    monkeypatch.setattr(
        images.requests,
        "get",
        lambda *_a, **_kw: FakeResponse(content_type="text/html"),
    )

    manifest = images.download_images(["https://x.com/page"])

    assert manifest["downloaded"] == []
    assert manifest["errors"][0]["url"] == "https://x.com/page"
