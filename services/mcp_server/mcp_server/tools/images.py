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


def images_dir() -> Path:
    item_id = get_current_item_id()
    if not item_id:
        raise RuntimeError("Nenhum item atual.")
    path = item_dir(item_id) / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extension_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    suffix = Path(path).suffix
    return suffix or ".jpg"


def download_image(url: str, index: int) -> dict[str, str]:
    ext = extension_from_url(url)
    filename = f"image_{index:03d}{ext}"
    path = images_dir() / filename

    response = requests.get(url, timeout=30, headers=REQUEST_HEADERS)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "image" not in content_type.lower():
        raise RuntimeError(f"URL não retornou imagem: {url} ({content_type})")

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
        except Exception as exc:
            index -= 1
            errors.append({"url": url, "error": str(exc)})

    manifest = {
        "downloaded": downloaded,
        "errors": errors,
    }

    write_json(images_dir() / "manifest.json", manifest)
    return manifest


def load_image_manifest() -> dict[str, object]:
    path = images_dir() / "manifest.json"
    if not path.exists():
        return {"downloaded": [], "errors": []}
    return read_json(path)
