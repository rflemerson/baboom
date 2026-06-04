"""Product creation, combo, and metadata services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.dtos import ProductCreateInput
from core.models import Brand, Product, ProductComponent, Tag

from .nutrition import ProductNutritionService
from .product_stores import ProductStoreService
from .taxonomy import TaxonomyResolutionService

if TYPE_CHECKING:
    from core.dtos import ComboComponentInput, ProductMetadataUpdateInput
    from core.models import Category


class ComboResolutionService:
    """Resolve combo components to existing products or placeholders."""

    @transaction.atomic
    def resolve_combo_components(
        self,
        parent_product: Product,
        components_data: list[ComboComponentInput],
    ) -> list[ProductComponent]:
        """Resolve component DTOs to concrete component links."""
        if parent_product.type != Product.Type.COMBO:
            raise ValidationError(
                {"type": _("Only combo products can have component links.")},
            )

        created_links = []
        links_by_component_id: dict[int, ProductComponent] = {}
        parent_product.component_links.all().delete()

        for component_data in components_data:
            component_product = self._find_best_match(parent_product, component_data)
            if component_product is None:
                component_product = self._create_component_product(
                    component_data,
                    parent_product,
                )

            existing_link = links_by_component_id.get(component_product.id)
            if existing_link is not None:
                existing_link.quantity += component_data.quantity
                existing_link.save(update_fields=["quantity", "updated_at"])
                continue

            link = ProductComponent.objects.create(
                parent=parent_product,
                component=component_product,
                quantity=component_data.quantity,
            )
            links_by_component_id[component_product.id] = link
            created_links.append(link)

        return created_links

    def _find_best_match(
        self,
        parent_product: Product,
        component_data: ComboComponentInput,
    ) -> Product | None:
        """Resolve a component using exact identifiers only."""
        return self._match_by_ean(component_data.ean) or self._match_by_external_id(
            parent_product,
            component_data.external_id,
        )

    def _match_by_ean(self, ean: str | None) -> Product | None:
        """Match a simple product by its global identifier."""
        if not ean:
            return None

        return Product.objects.filter(
            ean=ean,
            type=Product.Type.SIMPLE,
        ).first()

    def _match_by_external_id(
        self,
        parent_product: Product,
        external_id: str | None,
    ) -> Product | None:
        """Match a simple product by store identifier within the combo context."""
        if not external_id:
            return None

        store_ids = list(
            parent_product.store_links.values_list("store_id", flat=True),
        )
        if not store_ids:
            return None

        return (
            Product.objects.filter(
                type=Product.Type.SIMPLE,
                brand_id=parent_product.brand_id,
                store_links__offer__external_id=external_id,
                store_links__store_id__in=store_ids,
            )
            .distinct()
            .first()
        )

    def _create_component_product(
        self,
        component_data: ComboComponentInput,
        parent_product: Product,
    ) -> Product:
        """Create one unpublished simple product using the standard create flow."""
        return ProductCreateService().execute(
            self._build_component_create_input(
                component_data=component_data,
                parent_product=parent_product,
            ),
        )

    def _build_component_create_input(
        self,
        *,
        component_data: ComboComponentInput,
        parent_product: Product,
    ) -> ProductCreateInput:
        """Map one combo component into the standard product-create DTO."""
        return ProductCreateInput(
            name=component_data.name,
            weight=component_data.weight,
            brand_name=component_data.brand_name or parent_product.brand.display_name,
            category_name=component_data.category_name,
            ean=component_data.ean,
            description=component_data.description or "",
            packaging=component_data.packaging,
            is_published=False,
            tags=component_data.tags,
            stores=component_data.stores or [],
            nutrition=component_data.nutrition or [],
        )


class ProductCreateService:
    """Create products and their related catalog records."""

    def __init__(self) -> None:
        """Initialize collaborators used by the create workflow."""
        self.taxonomy_resolution = TaxonomyResolutionService()

    def execute(self, data: ProductCreateInput) -> Product:
        """Create a product with all related data."""
        self._validate_unique_ean(data.ean)

        try:
            with transaction.atomic():
                brand = self._resolve_brand(data.brand_name)
                category = self.taxonomy_resolution.resolve_category(data.category_name)

                product = Product.objects.create(
                    name=data.name,
                    weight=data.weight,
                    brand=brand,
                    category=category,
                    ean=data.ean,
                    description=data.description or "",
                    packaging=data.packaging,
                    is_published=data.is_published,
                    type=Product.Type.COMBO if data.is_combo else Product.Type.SIMPLE,
                )

                if data.tags:
                    product.tags.set(self.taxonomy_resolution.resolve_tags(data.tags))

                if data.stores:
                    ProductStoreService().replace_listings(product, data.stores)

                if data.is_combo and data.components:
                    ComboResolutionService().resolve_combo_components(
                        product,
                        data.components,
                    )
                elif data.nutrition:
                    ProductNutritionService().attach_profiles(product, data.nutrition)

                return product

        except IntegrityError as error:
            raise ValidationError({"unknown": str(error)}) from error

    def _validate_unique_ean(self, ean: str | None) -> None:
        """Reject duplicate EAN values before creating the product."""
        if ean and Product.objects.filter(ean=ean).exists():
            raise ValidationError({"ean": _("A product with this EAN already exists.")})

    def _resolve_brand(self, brand_name: str) -> Brand:
        """Find or create the brand associated with the product."""
        brand_slug = slugify(brand_name)
        brand = (
            Brand.objects.filter(display_name=brand_name).first()
            or Brand.objects.filter(name=brand_slug).first()
        )
        if brand is not None:
            return brand
        return Brand.objects.create(name=brand_slug, display_name=brand_name)


@dataclass(slots=True)
class ProductMetadataUpdateResolved:
    """Resolved metadata updates ready to be applied to a product."""

    name: str | None
    description: str | None
    packaging: str | None
    is_published: bool | None
    category: Category | None
    replace_category: bool
    tags: list[Tag] | None


class ProductMetadataUpdateService:
    """Apply metadata-only updates to existing products."""

    def __init__(self) -> None:
        """Initialize collaborators used by the metadata update workflow."""
        self.taxonomy_resolution = TaxonomyResolutionService()

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
                resolved = self._resolve(data)
                self._apply(product, resolved)
                product.save()
                return product

        except IntegrityError as error:
            raise ValidationError({"unknown": str(error)}) from error

    def _resolve(
        self,
        data: ProductMetadataUpdateInput,
    ) -> ProductMetadataUpdateResolved:
        """Resolve category and tag references for a product content update."""
        category, replace_category = self.taxonomy_resolution.resolve_update_category(
            data.category_name,
        )
        return ProductMetadataUpdateResolved(
            name=data.name,
            description=data.description,
            packaging=data.packaging,
            is_published=data.is_published,
            category=category,
            replace_category=replace_category,
            tags=self.taxonomy_resolution.resolve_update_tags(data.tags),
        )

    def _get_product(self, product_id: int) -> Product:
        """Load the product being updated or raise a validation error."""
        product = Product.objects.filter(id=product_id).first()
        if product is None:
            raise ValidationError({"product_id": _("Product not found")})
        return product

    def _apply(
        self,
        product: Product,
        resolved: ProductMetadataUpdateResolved,
    ) -> None:
        """Apply resolved metadata updates to the product instance."""
        if resolved.name is not None:
            product.name = resolved.name
        if resolved.description is not None:
            product.description = resolved.description
        if resolved.packaging is not None:
            product.packaging = resolved.packaging
        if resolved.is_published is not None:
            product.is_published = resolved.is_published
        if resolved.replace_category:
            product.category = resolved.category
        if resolved.tags is not None:
            product.tags.set(resolved.tags)
