"""Image download and manifest persistence helpers."""

from pathlib import Path
from urllib.parse import urlparse

import requests

from .workspace import get_current_item_id, item_dir, read_json, write_json

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}
NO_CURRENT_ITEM = "No current item."
NOT_AN_IMAGE = "URL did not return an image: {url} ({content_type})"


def images_dir() -> Path:
    """Return and create the current item's image directory."""
    item_id = get_current_item_id()
    if not item_id:
        raise RuntimeError(NO_CURRENT_ITEM)
    path = item_dir(item_id) / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extension_from_url(url: str) -> str:
    """Return the URL suffix or the default JPEG extension."""
    path = urlparse(url).path.lower()
    suffix = Path(path).suffix
    return suffix or ".jpg"


def download_image(url: str, index: int) -> dict[str, str]:
    """Download one image and return its manifest entry."""
    ext = extension_from_url(url)
    filename = f"image_{index:03d}{ext}"
    path = images_dir() / filename

    response = requests.get(url, timeout=30, headers=REQUEST_HEADERS)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "image" not in content_type.lower():
        message = NOT_AN_IMAGE.format(url=url, content_type=content_type)
        raise RuntimeError(message)

    path.write_bytes(response.content)

    return {
        "url": url,
        "path": str(path),
        "filename": filename,
        "contentType": content_type,
    }


def download_images(urls: list[str]) -> dict[str, object]:
    """Download the given URLs into the current item's workspace.

    Appends to the existing manifest, skipping URLs already downloaded.
    """
    manifest = load_image_manifest()
    downloaded: list[dict[str, str]] = list(manifest.get("downloaded", []))
    errors = []

    known = {entry["url"] for entry in downloaded}
    index = len(downloaded)

    for url in urls:
        if url in known:
            continue
        index += 1
        try:
            entry = download_image(url, index=index)
            downloaded.append(entry)
            known.add(url)
        except (OSError, requests.RequestException, RuntimeError, ValueError) as exc:
            index -= 1
            errors.append({"url": url, "error": str(exc)})

    manifest = {
        "downloaded": downloaded,
        "errors": errors,
    }

    write_json(images_dir() / "manifest.json", manifest)
    return manifest


def load_image_manifest() -> dict[str, object]:
    """Load the current image manifest or return an empty one."""
    path = images_dir() / "manifest.json"
    if not path.exists():
        return {"downloaded": [], "errors": []}
    return read_json(path)
