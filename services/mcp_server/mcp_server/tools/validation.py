from pydantic import ValidationError

from ..schemas import ProductDraft

ALLOWED_PRODUCT_FIELDS = {
    field.alias or name for name, field in ProductDraft.model_fields.items()
}


def validate_product_draft(draft: dict) -> dict:
    """Validate the complete recursive draft before any remote submission."""
    try:
        ProductDraft.model_validate(draft, strict=True)
    except ValidationError as exc:
        return {
            "ok": False,
            "errors": [
                f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
                for error in exc.errors()
            ],
        }
    return {"ok": True, "errors": []}
