"""Filesystem workspace helpers for checked-out review items."""

import json
import os
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    """Resolve the configured local workspace directory."""
    raw = os.getenv("MCP_WORKSPACE_DIR")
    if not raw:
        message = "MCP_WORKSPACE_DIR is not configured in the environment."
        raise RuntimeError(message)
    return Path(raw).expanduser().resolve()


def current_file() -> Path:
    """Return the path storing the currently checked-out item ID."""
    return workspace_root() / "current.json"


def item_dir(item_id: int) -> Path:
    """Return and create the workspace directory for one item."""
    path = workspace_root() / "scraped-items" / str(item_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON object with stable UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def set_current_item(item: dict[str, Any]) -> None:
    """Persist an item as the current checkout and save its snapshot."""
    item_id = int(item["id"])
    write_json(current_file(), {"item_id": item_id})
    write_json(item_dir(item_id) / "item.json", item)


def get_current_item_id() -> int | None:
    """Return the current item ID, if a checkout exists."""
    path = current_file()
    if not path.exists():
        return None
    return int(read_json(path)["item_id"])


def get_current_item() -> dict[str, Any]:
    """Load the snapshot for the currently checked-out item."""
    item_id = get_current_item_id()
    if not item_id:
        message = "No current item. Run checkout_scraped_item first."
        raise RuntimeError(message)
    return read_json(item_dir(item_id) / "item.json")
