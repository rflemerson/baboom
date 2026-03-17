"""Typed DTOs shared by core services and ingestion workflows."""

from typing import Any

from pydantic import BaseModel

from .models import Product


class ProductComponentInput(BaseModel):
    """DTO for combo component input."""

    name: str
    quantity: int = 1
    weight_hint: int | None = None
    packaging_hint: str | None = None


class ProductCreateInput(BaseModel):
    """DTO for product creation service."""

    name: str
    weight: int
    brand_name: str
    category_name: str | list[str] | None = None
    ean: str | None = None
    description: str | None = ""
    packaging: str = Product.Packaging.CONTAINER
    is_published: bool = False
    tags: list[str] | list[list[str]] | None = None
    stores: list[dict[str, Any]] | None = None
    nutrition: list[dict[str, Any]] | None = None

    # Combo fields
    is_combo: bool = False
    components: list[ProductComponentInput] | None = None
    nutrient_claims: list[str] | None = None
