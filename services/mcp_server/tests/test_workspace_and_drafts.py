import pytest

from mcp_server.tools.drafts import EMPTY_PRODUCT_DRAFT, load_draft, update_draft
from mcp_server.tools.workspace import (
    get_current_item,
    get_current_item_id,
    set_current_item,
)

ITEM = {"id": "42", "name": "Whey", "storeSlug": "growth"}


def test_current_item_roundtrip():
    assert get_current_item_id() is None

    set_current_item(ITEM)

    assert get_current_item_id() == 42
    assert get_current_item() == ITEM


def test_get_current_item_without_checkout():
    with pytest.raises(RuntimeError, match="Nenhum item atual"):
        get_current_item()


def test_draft_lifecycle():
    set_current_item(ITEM)

    assert load_draft() == EMPTY_PRODUCT_DRAFT

    draft = update_draft({"name": "Whey 1kg", "flavorNames": ["Chocolate"]})

    assert draft["name"] == "Whey 1kg"
    assert draft["flavorNames"] == ["Chocolate"]
    assert load_draft() == draft


def test_update_draft_rejects_unknown_fields():
    set_current_item(ITEM)

    with pytest.raises(ValueError, match="Campos desconhecidos"):
        update_draft({"foo": 1})
