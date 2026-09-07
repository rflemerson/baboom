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
    assert result["errors"] == ["foo: Extra inputs are not permitted"]


def test_non_integer_numbers():
    result = validate_product_draft({"weightGrams": "1000", "quantity": 1.5})

    assert result["ok"] is False
    assert any(error.startswith("weightGrams:") for error in result["errors"])
    assert any(error.startswith("quantity:") for error in result["errors"])


def test_list_fields():
    result = validate_product_draft({"flavorNames": "Chocolate"})

    assert result["ok"] is False
    assert any(error.startswith("flavorNames:") for error in result["errors"])


def test_nested_validation_rejects_unknown_fields_and_boolean_numbers():
    result = validate_product_draft(
        {
            "children": [{"weightGrams": True, "invented": "value"}],
            "nutritionFacts": {"proteins": "unknown"},
        }
    )
    assert not result["ok"]
    assert any("children.0.weightGrams" in error for error in result["errors"])
    assert any("children.0.invented" in error for error in result["errors"])
    assert any("nutritionFacts.proteins" in error for error in result["errors"])
