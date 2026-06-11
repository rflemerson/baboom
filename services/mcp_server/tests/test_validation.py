from mcp_server.tools.drafts import EMPTY_PRODUCT_DRAFT
from mcp_server.tools.validation import validate_product_draft


def test_empty_draft_is_valid():
    assert validate_product_draft(dict(EMPTY_PRODUCT_DRAFT)) == {
        "ok": True,
        "errors": [],
    }


def test_unknown_fields():
    result = validate_product_draft({"name": "Whey", "foo": 1})

    assert result["ok"] is False
    assert result["errors"] == ["Campos desconhecidos: foo"]


def test_non_integer_numbers():
    result = validate_product_draft({"weightGrams": "1000", "quantity": 1.5})

    assert result["ok"] is False
    assert "weightGrams deve ser inteiro ou null." in result["errors"]
    assert "quantity deve ser inteiro ou null." in result["errors"]


def test_list_fields():
    result = validate_product_draft({"flavorNames": "Chocolate"})

    assert result["ok"] is False
    assert result["errors"] == ["flavorNames deve ser lista."]
