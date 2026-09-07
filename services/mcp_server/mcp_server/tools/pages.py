"""Source-page capture shared by the MCP and command-line clients."""

from .dynamic_crawler import fetch_page_data
from .images import download_images as download_images_to_workspace
from .workspace import get_current_item, item_dir, write_json


def fetch_source_page(url: str | None = None) -> dict:
    """Render the current item's source page and store its structured data.

    Stores that only assemble the page in the browser -- or that answer a plain
    request with a challenge -- hand back nothing usable otherwise, so the page
    is rendered and its title, meta tags, JSON-LD, tables and images are saved
    alongside the raw HTML in the item's workspace.
    """
    item = get_current_item()
    target = url or item.get("sourcePageUrl") or item.get("productLink")
    if not target:
        return {"ok": False, "error": "Item não tem URL de origem."}

    fetched = fetch_page_data(target)
    item_path = item_dir(int(item["id"]))
    html_path = item_path / "page.html"
    data_path = item_path / "page_data.json"
    html_path.write_text(fetched.pop("html"), encoding="utf-8")
    write_json(data_path, fetched)

    # Structured extraction reaches JSON-LD, tables and visible text, but stores
    # that keep their catalog in an embedded application payload put nutrition
    # somewhere none of those look. The saved page is the fallback, so its path
    # travels with the result instead of having to be guessed.
    return {
        "ok": True,
        "url": target,
        "htmlPath": str(html_path),
        "pageDataPath": str(data_path),
        "pageData": fetched,
    }


def download_images(urls: list[str]) -> dict:
    """Download the chosen image URLs into the current item's workspace."""
    manifest = download_images_to_workspace(urls)
    return {
        "ok": True,
        "downloaded": manifest.get("downloaded", []),
        "errors": manifest.get("errors", []),
    }
