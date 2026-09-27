"""Typed DTOs shared by core services and ingestion workflows."""

from decimal import Decimal

from pydantic import BaseModel

from .models import Product

# Keep Decimal in runtime globals: Pydantic resolves this annotation at import time.
_PYDANTIC_RUNTIME_TYPES = (Decimal,)


class ProductCreateInput(BaseModel):
    """DTO for product creation service; ``net_mass`` is in grams, as printed."""

    name: str
    net_mass: Decimal | None = None
    brand_id: int
    category_id: int | None = None
    ean: str | None = None
    description: str | None = ""
    packaging: str = Product.Packaging.CONTAINER
    is_published: bool = False
    tag_ids: list[int] | None = None


class ProductMetadataUpdateInput(BaseModel):
    """DTO for metadata-only product updates."""

    name: str | None = None
    net_mass: Decimal | None = None
    brand_id: int | None = None
    ean: str | None = None
    description: str | None = None
    category_id: int | None = None
    packaging: str | None = None
    is_published: bool | None = None
    tag_ids: list[int] | None = None


class CatalogProductsFilters(BaseModel):
    """DTO for public catalog filtering and sorting."""

    search: str | None = None
    brand: str | None = None
    active: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    price_per_active_min: float | None = None
    price_per_active_max: float | None = None
    concentration_min: float | None = None
    concentration_max: float | None = None
    sort_by: str = "price_per_active"
    sort_dir: str = "asc"
