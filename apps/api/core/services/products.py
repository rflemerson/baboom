"""Product creation and metadata services."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _

from core.models import Brand, Category, Product, Tag
from core.units import to_canonical

from .product_stores import ProductStoreService

if TYPE_CHECKING:
    from core.dtos import ProductCreateInput, ProductMetadataUpdateInput


def _canonical_mass(value: float | None, unit: str) -> Decimal | None:
    """Convert a submitted mass into the canonical unit, or reject the unit."""
    if value is None:
        return None
    canonical = to_canonical(Decimal(str(value)), unit)
    if canonical is None:
        raise ValidationError({"mass_unit": _("Unsupported mass unit.")})
    return canonical


class ProductCreateService:
    """Create products and their related catalog records."""

    def execute(self, data: ProductCreateInput) -> Product:
        """Create a product with all related data."""
        brand = self._get_brand(data.brand_id)

        try:
            with transaction.atomic():
                category = (
                    Category.objects.filter(id=data.category_id).first()
                    if data.category_id
                    else None
                )

                product = Product.objects.create(
                    name=data.name,
                    net_mass=_canonical_mass(data.net_mass, data.mass_unit),
                    brand=brand,
                    category=category,
                    ean=data.ean,
                    description=data.description or "",
                    packaging=data.packaging,
                    is_published=data.is_published,
                )

                if data.tag_ids:
                    product.tags.set(Tag.objects.filter(id__in=data.tag_ids))

                if data.stores:
                    ProductStoreService().replace_listings(product, data.stores)

                return product

        except IntegrityError as error:
            raise ValidationError({"unknown": str(error)}) from error

    def _get_brand(self, brand_id: int) -> Brand:
        """Load the brand or raise a validation error."""
        brand = Brand.objects.filter(id=brand_id).first()
        if brand is None:
            raise ValidationError({"brand_id": _("Brand not found.")})
        return brand


class ProductMetadataUpdateService:
    """Apply metadata-only updates to existing products."""

    def execute(
        self,
        *,
        product_id: int,
        data: ProductMetadataUpdateInput,
    ) -> Product:
        """Update product metadata without modifying price data."""
        try:
            with transaction.atomic():
                product = self._get_product(product_id)
                self._apply(product, data)
                product.save()
                if "tag_ids" in data.model_fields_set:
                    product.tags.set(Tag.objects.filter(id__in=(data.tag_ids or [])))
                return product

        except IntegrityError as error:
            raise ValidationError({"unknown": str(error)}) from error

    def _get_product(self, product_id: int) -> Product:
        """Load the product being updated or raise a validation error."""
        product = Product.objects.filter(id=product_id).first()
        if product is None:
            raise ValidationError({"product_id": _("Product not found")})
        return product

    def _apply(
        self,
        product: Product,
        data: ProductMetadataUpdateInput,
    ) -> None:
        """Apply submitted metadata to the product instance."""
        if data.name is not None:
            product.name = data.name
        if "net_mass" in data.model_fields_set:
            product.net_mass = _canonical_mass(data.net_mass, data.mass_unit)
        if "brand_id" in data.model_fields_set:
            if data.brand_id is None:
                raise ValidationError({"brand_id": _("Brand is required.")})
            product.brand = self._get_brand(data.brand_id)
        if "ean" in data.model_fields_set:
            product.ean = data.ean
        if data.description is not None:
            product.description = data.description
        if data.packaging is not None:
            product.packaging = data.packaging
        if data.is_published is not None:
            product.is_published = data.is_published
        if "category_id" in data.model_fields_set:
            product.category = (
                Category.objects.filter(id=data.category_id).first()
                if data.category_id
                else None
            )

    def _get_brand(self, brand_id: int) -> Brand:
        """Load the brand or raise a validation error."""
        brand = Brand.objects.filter(id=brand_id).first()
        if brand is None:
            raise ValidationError({"brand_id": _("Brand not found.")})
        return brand
