from typing import Any

from .validation import ALLOWED_PRODUCT_FIELDS
from .workspace import get_current_item_id, item_dir, read_json, write_json

EMPTY_PRODUCT_DRAFT = {
    "name": None,
    "brandName": None,
    "ean": None,
    "weightGrams": None,
    "packaging": None,
    "quantity": None,
    "description": None,
    "categoryHierarchy": [],
    "tagsHierarchy": [],
    "flavorNames": [],
    "variantName": None,
    "nutritionFacts": None,
    "children": [],
}


def draft_path():
    item_id = get_current_item_id()
    if not item_id:
        raise RuntimeError("Nenhum item atual.")
    return item_dir(item_id) / "draft.json"


def ensure_draft() -> dict[str, Any]:
    path = draft_path()
    if not path.exists():
        write_json(path, dict(EMPTY_PRODUCT_DRAFT))
    return read_json(path)


def load_draft() -> dict[str, Any]:
    return ensure_draft()


def update_draft(patch: dict[str, Any]) -> dict[str, Any]:
    unknown = set(patch.keys()) - ALLOWED_PRODUCT_FIELDS
    if unknown:
        raise ValueError(f"Campos desconhecidos no patch: {', '.join(sorted(unknown))}")
    draft = ensure_draft()
    draft.update(patch)
    write_json(draft_path(), draft)
    return draft
