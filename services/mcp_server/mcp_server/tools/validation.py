from typing import Any

ALLOWED_PRODUCT_FIELDS = {
    "name",
    "brandName",
    "ean",
    "weightGrams",
    "packaging",
    "quantity",
    "description",
    "categoryHierarchy",
    "tagsHierarchy",
    "flavorNames",
    "variantName",
    "nutritionFacts",
    "children",
}


def validate_product_draft(draft: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    unknown = sorted(set(draft.keys()) - ALLOWED_PRODUCT_FIELDS)
    if unknown:
        errors.append("Campos desconhecidos: " + ", ".join(unknown))

    if draft.get("weightGrams") is not None and not isinstance(
        draft["weightGrams"], int
    ):
        errors.append("weightGrams deve ser inteiro ou null.")

    if draft.get("quantity") is not None and not isinstance(draft["quantity"], int):
        errors.append("quantity deve ser inteiro ou null.")

    for field in ["categoryHierarchy", "tagsHierarchy", "flavorNames", "children"]:
        if (
            field in draft
            and draft[field] is not None
            and not isinstance(draft[field], list)
        ):
            errors.append(f"{field} deve ser lista.")

    return {
        "ok": not errors,
        "errors": errors,
    }
