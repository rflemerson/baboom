"""Download product and label images to a caller-provided directory."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import requests

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}


def images_dir(workspace: str | Path) -> Path:
    """Return and create the image directory below ``workspace``."""
    path = Path(workspace).expanduser().resolve() / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extension_from_url(url: str) -> str:
    """Return the URL suffix or the default JPEG extension."""
    return Path(urlparse(url).path).suffix.lower() or ".jpg"


def download_image(url: str, index: int, workspace: str | Path) -> dict[str, str]:
    """Download one image and return its manifest entry."""
    extension = extension_from_url(url)
    filename = f"image_{index:03d}{extension}"
    path = images_dir(workspace) / filename
    response = requests.get(url, timeout=30, headers=REQUEST_HEADERS)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "image" not in content_type.lower():
        message = f"URL did not return an image: {url} ({content_type})"
        raise RuntimeError(message)
    path.write_bytes(response.content)
    return {
        "url": url,
        "path": str(path),
        "filename": filename,
        "contentType": content_type,
    }


def load_image_manifest(workspace: str | Path) -> dict[str, object]:
    """Load the workspace image manifest or return an empty one."""
    path = images_dir(workspace) / "manifest.json"
    if not path.exists():
        return {"downloaded": [], "errors": []}
    return json.loads(path.read_text(encoding="utf-8"))


def download_images(urls: list[str], workspace: str | Path) -> dict[str, object]:
    """Download URLs into ``workspace`` and persist a manifest."""
    manifest = load_image_manifest(workspace)
    downloaded: list[dict[str, str]] = list(manifest.get("downloaded", []))
    errors: list[dict[str, str]] = []
    known = {entry["url"] for entry in downloaded}
    index = len(downloaded)
    for url in urls:
        if url in known:
            continue
        index += 1
        try:
            entry = download_image(url, index, workspace)
        except (OSError, requests.RequestException, RuntimeError, ValueError) as exc:
            index -= 1
            errors.append({"url": url, "error": str(exc)})
        else:
            downloaded.append(entry)
            known.add(url)
    result = {"downloaded": downloaded, "errors": errors}
    manifest_path = images_dir(workspace) / "manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
