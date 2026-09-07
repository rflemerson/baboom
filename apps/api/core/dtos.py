"""Typed DTOs shared by core services and ingestion workflows."""

from pydantic import BaseModel

from offers.models import StockStatus

from .models import Product
from .units import DISPLAY_MASS_UNIT


class StoreListingPayload(BaseModel):
    """DTO for a store listing attached to a product."""

    store_id: int
    product_link: str
    price: float
    external_id: str | None = ""
    affiliate_link: str | None = None
    stock_status: str = StockStatus.AVAILABLE


class ProductCreateInput(BaseModel):
    """DTO for product creation service.

    ``net_mass`` is expressed in ``mass_unit``; the service converts it to the
    canonical unit before it reaches the model.
    """

    name: str
    net_mass: float | None = None
    mass_unit: str = DISPLAY_MASS_UNIT
    brand_id: int
    category_id: int | None = None
    ean: str | None = None
    description: str | None = ""
    packaging: str = Product.Packaging.CONTAINER
    is_published: bool = False
    tag_ids: list[int] | None = None
    stores: list[StoreListingPayload] | None = None


class ProductMetadataUpdateInput(BaseModel):
    """DTO for metadata-only product updates."""

    name: str | None = None
    net_mass: float | None = None
    mass_unit: str = DISPLAY_MASS_UNIT
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
