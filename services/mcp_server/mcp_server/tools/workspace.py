import json
import os
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    raw = os.getenv("MCP_WORKSPACE_DIR")
    if not raw:
        raise RuntimeError(
            "MCP_WORKSPACE_DIR não configurado nas variáveis de ambiente."
        )
    return Path(raw).expanduser().resolve()


def current_file() -> Path:
    return workspace_root() / "current.json"


def item_dir(item_id: int) -> Path:
    path = workspace_root() / "scraped-items" / str(item_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def set_current_item(item: dict[str, Any]) -> None:
    item_id = int(item["id"])
    write_json(current_file(), {"item_id": item_id})
    write_json(item_dir(item_id) / "item.json", item)


def get_current_item_id() -> int | None:
    path = current_file()
    if not path.exists():
        return None
    return int(read_json(path)["item_id"])


def get_current_item() -> dict[str, Any]:
    item_id = get_current_item_id()
    if not item_id:
        raise RuntimeError("Nenhum item atual. Use checkout_scraped_item primeiro.")
    return read_json(item_dir(item_id) / "item.json")
