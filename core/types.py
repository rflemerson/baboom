from dataclasses import dataclass
from typing import Any

from .models import Product


@dataclass
class ProductCreateInput:
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
